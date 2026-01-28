---
name: campaign-ebs-rescue
description: EBS rescue disk procedure for full root volumes
---

# Campaign EBS Rescue Procedure

Recover from full root volume by attaching to rescue instance.

## Arguments

```
/campaign-ebs-rescue <instance> [--container=<n>]
```

- `instance`: Campaign instance name (required)
- `--container`: Container number (default: 1)

## Instructions

### When to Use

- Root volume 100% full
- Instance won't boot/SSH
- Core dumps filling disk

### ⚠️ Requirements

- Rescue instance MUST be in SAME Availability Zone
- Have instance ID and volume ID ready

### Step 1: Get Instance and Volume Info

```bash
aws ec2 describe-instances \
  --profile campaign_prod_v8 \
  --region <region> \
  --filters "Name=tag:Name,Values=<instance>-<container>" \
  --query 'Reservations[0].Instances[0].[InstanceId,Placement.AvailabilityZone,BlockDeviceMappings[0].Ebs.VolumeId]'
```

### Step 2: Stop Affected Instance

```bash
aws ec2 stop-instances \
  --profile campaign_prod_v8 \
  --region <region> \
  --instance-ids <instance-id>

aws ec2 wait instance-stopped \
  --profile campaign_prod_v8 \
  --region <region> \
  --instance-ids <instance-id>
```

### Step 3: Detach Root Volume

```bash
aws ec2 detach-volume \
  --profile campaign_prod_v8 \
  --region <region> \
  --volume-id <vol-id>

aws ec2 wait volume-available \
  --profile campaign_prod_v8 \
  --region <region> \
  --volume-ids <vol-id>
```

### Step 4: Attach to Rescue Instance

**Must be same AZ!**

```bash
aws ec2 attach-volume \
  --profile campaign_prod_v8 \
  --region <region> \
  --volume-id <vol-id> \
  --instance-id <rescue-instance-id> \
  --device /dev/xvdf
```

### Step 5: Mount and Clean

On rescue instance:
```bash
sudo mkdir -p /mnt/rescue
sudo mount /dev/xvdf1 /mnt/rescue

# Find large files
du -sh /mnt/rescue/* | sort -hr | head -20

# Delete core dumps (handle many files)
find /mnt/rescue -maxdepth 1 -name "core*" -type f -print0 | xargs -0 rm -f

# Check space recovered
df -h /mnt/rescue

sudo umount /mnt/rescue
```

### Step 6: Reattach to Original

```bash
aws ec2 detach-volume \
  --profile campaign_prod_v8 \
  --region <region> \
  --volume-id <vol-id>

aws ec2 wait volume-available \
  --profile campaign_prod_v8 \
  --region <region> \
  --volume-ids <vol-id>

aws ec2 attach-volume \
  --profile campaign_prod_v8 \
  --region <region> \
  --volume-id <vol-id> \
  --instance-id <original-instance-id> \
  --device /dev/xvda
```

### Step 7: Start Instance

```bash
aws ec2 start-instances \
  --profile campaign_prod_v8 \
  --region <region> \
  --instance-ids <instance-id>
```

### Common Causes of Full Disk

- Core dumps from crashing services
- Log files not rotated
- Temp files accumulation
