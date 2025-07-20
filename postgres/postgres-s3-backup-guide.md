# PostgreSQL Daily Backups to Amazon S3

Setting up automated daily backups to Amazon S3 is an excellent and common industry practice. It provides a secure, off-site location for your data, protecting you from server-specific failures.

Here's a complete step-by-step guide to get it done.

## Step 1: Create Your S3 Bucket

First, you need a secure place in AWS to store your backup files.

1. Navigate to S3 in your AWS Console.

2. Click **Create bucket**.

3. Give it a globally unique name (e.g., `my-app-db-backups-unique-name`).

4. Select the AWS Region where you want to store the backups. It's often a good idea to choose a different region from your EC2 instance for better disaster recovery.

5. Under **Block Public Access settings for this bucket**, ensure **Block all public access** is checked. Your backups are sensitive and should never be public.

6. Click **Create bucket**.

## Step 2: Create Custom Policy for S3 Access

### Create Policy First:

1. In IAM console, click **Policies** in left sidebar
2. Click **Create policy**
3. Choose **JSON** tab
4. Paste this policy (replace bucket name):

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject",
        "s3:DeleteObject",
        "s3:PutObjectAcl"
      ],
      "Resource": "arn:aws:s3:::your-app-db-backups/*"
    },
    {
      "Effect": "Allow",
      "Action": ["s3:ListBucket", "s3:GetBucketLocation"],
      "Resource": "arn:aws:s3:::your-app-db-backups"
    }
  ]
}
```

### Name the Policy:

1. Click **Next**
2. Name it something like: `EC2-S3-DB-Backup-Policy`
3. Add description: "Allows EC2 to backup databases to S3"
4. Click **Create policy**

## Step 3: Create the IAM Role

After the policy is created:

### Go to IAM Console:

1. Log into AWS Console
2. Navigate to IAM service
3. Click **Roles** in the left sidebar

### Create Role:

1. Click **Create role**
2. Select **AWS service** as the trusted entity type
3. Choose **EC2** from the service list
4. Click **Next**

## Step 4: Attach the IAM Role to Your EC2 Instance

### Go to EC2 Console:

1. Open AWS Console → EC2 service
2. Click **Instances** in the left sidebar

### Find Your Instance:

1. Look for your instance (ip-172-31-26-175)
2. Select it by clicking the checkbox

### Attach the Role:

1. Click **Actions** button at the top
2. Go to **Security** → **Modify IAM role**
3. In the dropdown, select the role you created (`EC2-DB-Backup-Role`)
4. Click **Update IAM role**

### Verify After Attachment

Once you've attached the role, wait about 30 seconds, then test again on your EC2 instance:

```bash
# This should now show your role information
aws sts get-caller-identity
```

## Step 5: Configure PostgreSQL Authentication (Updated Method)

For automated backups, using the `PGPASSWORD` environment variable is more reliable than `.pgpass`:

**Method 1: Using PGPASSWORD (Recommended for scripts)**
This method will be included directly in the backup script below.

**Method 2: Using .pgpass file (Alternative)**

```bash
# Create .pgpass file in home directory
echo "localhost:5432:your_database_name:your_db_user:your_actual_password" > ~/.pgpass

# Set proper permissions (important for security)
chmod 600 ~/.pgpass
```

## Step 6: Create the Production-Ready Backup Script

### Set Up Log File First

```bash
sudo touch /var/log/db-backup.log
sudo chown ubuntu:ubuntu /var/log/db-backup.log
sudo chmod 644 /var/log/db-backup.log
```

### Create the Backup Script

Create an improved script with error handling, logging, and cron compatibility (`backup-db-s3.sh`):

```bash
#!/bin/bash

# Log start time
echo "=== Backup started at $(date) ===" >> /var/log/db-backup.log 2>&1

# Set full PATH for cron environment
export PATH=/usr/local/bin:/usr/bin:/bin:/usr/local/sbin:/usr/sbin:/sbin

# Configuration
DB_NAME="your_database_name"
DB_USER="your_db_user"
export PGPASSWORD="your_db_password"
S3_BUCKET="your-s3-bucket-name"
BACKUP_DIR="/tmp/db-backups"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="backup_${DB_NAME}_${DATE}.sql"

# Create backup directory
mkdir -p $BACKUP_DIR

# Create backup with full paths
/usr/bin/pg_dump -U $DB_USER -h localhost $DB_NAME > $BACKUP_DIR/$BACKUP_FILE 2>> /var/log/db-backup.log

# Check if backup was created
if [ ! -f "$BACKUP_DIR/$BACKUP_FILE" ]; then
    echo "ERROR: Backup file not created" >> /var/log/db-backup.log 2>&1
    exit 1
fi

# Compress backup
gzip $BACKUP_DIR/$BACKUP_FILE
BACKUP_FILE="${BACKUP_FILE}.gz"

# Upload to S3 with full path
/usr/local/bin/aws s3 cp $BACKUP_DIR/$BACKUP_FILE s3://$S3_BUCKET/daily-backups/ >> /var/log/db-backup.log 2>&1

# Check upload result
if [ $? -eq 0 ]; then
    echo "SUCCESS: $BACKUP_FILE uploaded to S3" >> /var/log/db-backup.log 2>&1
else
    echo "ERROR: Failed to upload $BACKUP_FILE to S3" >> /var/log/db-backup.log 2>&1
fi

# Clean up local backup
rm $BACKUP_DIR/$BACKUP_FILE

echo "=== Backup completed at $(date) ===" >> /var/log/db-backup.log 2>&1
```

**Key improvements in this version:**

- Full PATH set for cron environment compatibility
- Full command paths (`/usr/bin/pg_dump`, `/usr/local/bin/aws`)
- Comprehensive logging with timestamps
- Error checking for backup creation and S3 upload
- Uses `PGPASSWORD` for reliable authentication
- Clear success/failure messages

## Step 7: Set Up Automated Daily Backups with Cron

### Make the Script Executable

```bash
chmod +x /home/ubuntu/backup-db-s3.sh
```

### Set Up Cron Job

Edit your crontab to schedule daily backups:

```bash
crontab -e
```

Add your preferred schedule:

```bash
# Daily backup at 11:52 PM
52 23 * * * /home/ubuntu/backup-db-s3.sh >> /var/log/db-backup.log 2>&1

# Or daily backup at 12:45 AM
45 0 * * * /home/ubuntu/backup-db-s3.sh >> /var/log/db-backup.log 2>&1
```

### Monitor Your Backups

```bash
# Check recent backup logs
tail -f /var/log/db-backup.log

# List your current cron jobs
crontab -l
```

## Step 8: Troubleshooting Cron Issues

If your cron job isn't running (manual execution works but cron doesn't):

### 1. Check Script Permissions

```bash
ls -la /home/ubuntu/backup-db-s3.sh
# Should show: -rwxr-xr-x (executable permissions)
```

### 2. Test with Simple Cron Job

Add this temporarily to verify cron is working:

```bash
crontab -e
# Add this line:
* * * * * echo "$(date): Cron test" >> /tmp/cron-test.log
```

Wait 2 minutes, then check:

```bash
cat /tmp/cron-test.log
```

### 3. Check Cron Service

```bash
# Check if cron is running
sudo systemctl status cron

# Start cron if needed
sudo systemctl start cron
sudo systemctl enable cron
```

### 4. Verify Command Paths

```bash
# Find exact paths for your system
which pg_dump    # Usually /usr/bin/pg_dump
which aws        # Usually /usr/local/bin/aws
which gzip       # Usually /bin/gzip
```

### 5. Check System Logs for Cron Errors

```bash
# Check cron logs
sudo tail -f /var/log/syslog | grep CRON

# Or check systemd journal
sudo journalctl -u cron -f
```

### 6. Test Manual Execution

```bash
# Run the script manually to ensure it works
/home/ubuntu/backup-db-s3.sh

# Check the logs
tail /var/log/db-backup.log
```

## Step 9: Monitoring and Maintenance

### Regular Checks

- Monitor `/var/log/db-backup.log` for errors
- Check S3 bucket periodically to verify uploads
- Set up CloudWatch or email alerts for backup failures

### S3 Storage Management

Consider setting up S3 lifecycle policies to automatically delete old backups:

- Keep daily backups for 30 days
- Keep weekly backups for 12 weeks
- Keep monthly backups for 12 months

### Backup Verification

Periodically test restore procedures:

```bash
# Download a backup from S3
aws s3 cp s3://your-s3-bucket-name/daily-backups/backup_yourdb_20240101_120000.sql.gz /tmp/

# Extract and test restore (on a test database)
gunzip /tmp/backup_yourdb_20240101_120000.sql.gz
psql -U your_db_user -d test_database < /tmp/backup_yourdb_20240101_120000.sql
```
