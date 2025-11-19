#!/bin/bash
set -e

# EC2 User Data Script
# This script runs on EC2 instance launch to configure the system
# It installs Docker, docker-compose, SSSD for LDAP, and hardens SSH

LOG_FILE="/var/log/user-data.log"

log_message() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log_message "Starting EC2 initialization script"

# Update system packages
log_message "Updating system packages"
apt-get update
apt-get upgrade -y

# Install Docker
log_message "Installing Docker"
apt-get install -y docker.io
systemctl start docker
systemctl enable docker
log_message "Docker installed and started"

# Install docker-compose
log_message "Installing docker-compose"
curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose
log_message "docker-compose installed"

# Add admin to docker group (Debian default user)
log_message "Adding admin to docker group"
usermod -aG docker admin

# Install SSSD with libsss-sudo (matching asksplunk-prod configuration)
log_message "Installing SSSD for LDAP authentication"
apt-get install -y sssd sssd-ldap libsss-sudo sssd-tools ldap-utils

# Deploy SSSD configuration (matching asksplunk-prod)
log_message "Deploying SSSD configuration"
cat > /etc/sssd/sssd.conf <<'SSSDEOF'
[sssd]
debug_level = 0
config_file_version = 2
services = nss, pam, ssh, sudo
domains = default

[domain/default]
debug_level = 0
ldap_disable_paging = True
ldap_id_use_start_tls = True
ldap_schema = rfc2307bis
ldap_search_base = o=adbe
ldap_deref_threshold = 0
id_provider = ldap
auth_provider = ldap
chpass_provider = ldap

ldap_uri = ldaps://ldap-proxy.camp-infra.adobe.net:10636
ldap_backup_uri = ldaps://camp-infra.adobe.net:636

ldap_tls_cacert = /etc/ssl/certs/ca-certificates.crt
cache_credentials = True
ldap_tls_reqcert = demand
ldap_group_member = uniqueMember
enumerate = False
ldap_enumeration_refresh_timeout = 18000
entry_cache_timeout = 14400
entry_cache_user_timeout = 14400
entry_cache_group_timeout = 14400
entry_cache_netgroup_timeout = 14400
entry_cache_service_timeout = 14400

sudo_provider = ldap
ldap_sudo_search_base = ou=SUDOers,o=adbe
ldap_user_ssh_public_key = sshPublicKey

access_provider = simple
ignore_group_members = True
simple_allow_groups = campaign, Campaign_LB_Admin, campaignbastionhosts, Campaign_Temp_Users, campaign_sustenance, campaign_cc

[nss]
filter_users = root,neolane,nobody,ntp,named,smtp,postgres,postfix,nagios,nrpe,httpd,hadoop,nssagent,ssh-authkeys,asc-bkaccess,asc-oit,asc-setup,asc-rundeck,asc-airflow,mbplc,mabadhoc,mabRelay
filter_groups = chrooted,asc-users
default_shell = /bin/bash

[pam]

[ssh]

[sudo]
SSSDEOF

chmod 600 /etc/sssd/sssd.conf
chown root:root /etc/sssd/sssd.conf
log_message "SSSD configuration deployed"

# Configure nsswitch.conf for SSSD sudo integration
log_message "Configuring nsswitch.conf for SSSD sudo responder"
if ! grep -q "^sudoers:" /etc/nsswitch.conf; then
    echo 'sudoers:        files sss' >> /etc/nsswitch.conf
    log_message "Added sudoers entry to nsswitch.conf"
fi

# Enable and start SSSD service
log_message "Enabling and starting SSSD service"
systemctl enable sssd
systemctl start sssd
log_message "SSSD service started"

# Set up SSH key for admin user (from EC2 instance metadata)
log_message "Setting up SSH key for admin user"
mkdir -p /home/admin/.ssh
chmod 700 /home/admin/.ssh

# Get public key from instance metadata
PUBLIC_KEY=$(curl -s http://169.254.169.254/latest/meta-data/public-keys/0/openssh-key/)
if [ -n "$PUBLIC_KEY" ]; then
    echo "$PUBLIC_KEY" > /home/admin/.ssh/authorized_keys
    chmod 600 /home/admin/.ssh/authorized_keys
    chown admin:admin /home/admin/.ssh/authorized_keys
    log_message "SSH public key installed for admin user"
else
    log_message "WARNING: Could not retrieve SSH public key from instance metadata"
fi

# Apply minimal SSH configuration (matching asksplunk-prod)
log_message "Configuring SSH to disable password authentication"
cp /etc/ssh/sshd_config /etc/ssh/sshd_config.backup

# Only set PasswordAuthentication no (asksplunk-prod config)
sed -i 's/^#PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config
if ! grep -q "^PasswordAuthentication no" /etc/ssh/sshd_config; then
    echo "PasswordAuthentication no" >> /etc/ssh/sshd_config
fi

# Test SSH configuration
if sshd -t; then
    log_message "SSH configuration valid"
    systemctl restart sshd
else
    log_message "ERROR: SSH configuration invalid, reverting"
    cp /etc/ssh/sshd_config.backup /etc/ssh/sshd_config
    systemctl restart sshd
fi

# Create application directory structure
log_message "Creating application directory structure"
mkdir -p /opt/maptimize/app
mkdir -p /opt/maptimize/config
mkdir -p /opt/maptimize/logs
mkdir -p /opt/maptimize/data

# Set proper permissions
chown -R admin:admin /opt/maptimize
chmod 755 /opt/maptimize
chmod 755 /opt/maptimize/app
chmod 755 /opt/maptimize/config
chmod 755 /opt/maptimize/logs
chmod 755 /opt/maptimize/data

# Create deploy script directory
mkdir -p /opt/maptimize/scripts
cp /opt/maptimize/scripts/deploy.sh /opt/maptimize/scripts/deploy.sh 2>/dev/null || log_message "Deploy script will be added via deployment"

log_message "EC2 initialization complete"
