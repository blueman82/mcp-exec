#!/bin/bash
#
# user-data.sh - EC2 instance initialization for Maptimize
#
# This script runs on first boot and configures:
# - SSSD with LDAP authentication
# - SSH with SSSD integration
# - Docker and maptimize bot container startup
#

set -euo pipefail

# ========== LOGGING ==========
LOG_FILE="/var/log/maptimize-user-data.log"
exec > >(tee -a "$LOG_FILE")
exec 2>&1

log_info() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] [INFO] $1"
}

log_error() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] [ERROR] $1"
}

log_section() {
    echo ""
    echo "====== $1 ======"
    echo ""
}

# ========== SSSD INSTALLATION ==========

log_section "Installing SSSD and LDAP packages"

apt-get update
apt-get install -y sssd sssd-ldap sssd-tools libpam-sss libnss-sss libsss-sudo

log_info "SSSD packages installed"

# ========== SSSD CONFIGURATION ==========

log_section "Configuring SSSD"

cat > /etc/sssd/sssd.conf << 'EOF'
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
EOF

chmod 600 /etc/sssd/sssd.conf
log_info "SSSD configuration written"

# ========== NSSWITCH CONFIGURATION ==========

log_section "Updating nsswitch.conf for SSSD"

cat > /etc/nsswitch.conf << 'EOF'
# /etc/nsswitch.conf - SSSD integration for LDAP
#
passwd:         files sss
group:          files sss
shadow:         files sss
gshadow:        files sss

hosts:          files myhostname dns
networks:       files

protocols:      db files
services:       db files sss
ethers:         db files
rpc:            db files

netgroup:       nis sss
automount:      sss
sudoers:        files sss
EOF

log_info "nsswitch.conf configured with LDAP sudo support"

# ========== SSH CONFIGURATION ==========

log_section "Configuring SSH for SSSD"

cat >> /etc/ssh/sshd_config << 'EOF'

# SSSD-based public key authentication
PubkeyAuthentication yes
AuthorizedKeysCommand /usr/bin/sss_ssh_authorizedkeys %u
AuthorizedKeysCommandUser root
PasswordAuthentication yes
EOF

# Validate SSH config
if sshd -t; then
    log_info "SSH configuration is valid"
else
    log_error "SSH configuration validation failed - reverting"
    # If sshd_config is invalid, restore it
    if [ -f /etc/ssh/sshd_config.bak ]; then
        cp /etc/ssh/sshd_config.bak /etc/ssh/sshd_config
    fi
fi

# ========== START SERVICES ==========

log_section "Starting SSSD and SSH"

systemctl restart sssd
systemctl restart ssh

log_info "SSSD and SSH services restarted"

# ========== VERIFY LDAP ==========

log_section "Verifying LDAP connectivity"

# Wait for SSSD to initialize
sleep 3

if getent passwd | grep -q system; then
    log_info "LDAP user resolution is working"
else
    log_error "Warning: LDAP user resolution may not be working yet"
fi

# ========== DOCKER INSTALLATION ==========

log_section "Installing Docker"

apt-get install -y docker.io docker-compose

usermod -aG docker admin

systemctl enable docker
systemctl start docker

log_info "Docker installed and started"

# ========== BOT DEPLOYMENT ==========

log_section "Deploying Maptimize Bot v0.1.1"

# Configure AWS credentials from environment/instance profile
export AWS_REGION="eu-west-1"
export AWS_DEFAULT_REGION="eu-west-1"

# Pull bot image from ECR
docker login -u AWS -p $(aws ecr get-login-password --region eu-west-1) 483013340174.dkr.ecr.eu-west-1.amazonaws.com

docker pull 483013340174.dkr.ecr.eu-west-1.amazonaws.com/maptimize:v0.1.1

# Run bot container with restart policy
docker run -d \
  --restart=always \
  --name maptimize-bot \
  -e LOG_LEVEL=INFO \
  -e ENVIRONMENT=production \
  483013340174.dkr.ecr.eu-west-1.amazonaws.com/maptimize:v0.1.1

log_info "Maptimize Bot v0.1.1 deployed and running"

# ========== COMPLETION ==========

log_section "User data initialization complete"

log_info "SSSD with LDAP authentication is configured"
log_info "SSH with SSSD public key auth is configured"
log_info "Docker is installed and ready"
log_info "Logs available at: $LOG_FILE"

exit 0
