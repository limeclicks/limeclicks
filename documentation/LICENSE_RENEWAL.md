# Screaming Frog License Renewal Guide

## Problem
Site audits are failing with the error: "No output files generated" or similar errors.

## Root Cause
The Screaming Frog SEO Spider license has expired.

## Symptoms
- Site audits fail immediately without generating any output files
- Celery logs show: `FATAL - Licence expired [DATE] GMT`
- All site audits (not just armorpoxy.com) will fail

## License Information
**Current License Expiry Date:** December 6, 2025

## How to Renew

### Step 1: Purchase/Renew License
1. Visit [Screaming Frog website](https://www.screamingfrogseo.com/seo-spider/)
2. Purchase or renew the SEO Spider license
3. You will receive a new license key in the format: `USERNAME-XXXXXXXXXX-XXXXXXXXXXXX-XXXXXXXXXXXX`

### Step 2: Update License on Server

#### Option A: Update via Web Interface (If Available)
1. Log into the Screaming Frog account portal
2. Download the new license file
3. Upload it to the server

#### Option B: Update via Command Line (Recommended)
1. SSH into the production server:
   ```bash
   ssh ubuntu@91.230.110.86
   ```

2. Navigate to the application directory:
   ```bash
   cd /home/ubuntu/new-limeclicks
   ```

3. Update the `.env` file with the new license key:
   ```bash
   nano .env
   ```

   Find the line:
   ```
   SCREAMING_FROG_LICENSE='C939DDDB3A-1764979200-00C6F75663'
   ```

   Replace with the new license key:
   ```
   SCREAMING_FROG_LICENSE='YOUR-NEW-LICENSE-KEY-HERE'
   ```

4. Update the Screaming Frog config directory:
   ```bash
   nano /home/ubuntu/.ScreamingFrogSEOSpider/licence.txt
   ```

   Replace the content with your new license in format:
   ```
   USERNAME
   LICENSE-KEY
   ```

5. Restart the services to pick up the new license:
   ```bash
   sudo systemctl restart limeclicks-celery
   sudo systemctl restart limeclicks-celerybeat
   sudo systemctl restart limeclicks-gunicorn
   ```

### Step 3: Verify License Update

1. Test the license by running a manual audit:
   ```bash
   cd /home/ubuntu/new-limeclicks
   /home/ubuntu/.pyenv/versions/3.12.2/bin/python manage.py shell
   ```

2. In the Python shell:
   ```python
   from site_audit.tasks import trigger_manual_site_audit

   # Trigger audit for any project (using armorpoxy as example)
   result = trigger_manual_site_audit(7)
   print(result)
   ```

3. Monitor the celery logs for success:
   ```bash
   tail -f logs/celery-worker.log
   ```

4. You should see the crawl complete successfully without license errors.

### Step 4: Verify All Projects
Once the license is renewed, you can verify that audits work for all projects by triggering a few test audits through the web interface.

## Prevention
Set a calendar reminder to renew the license at least 1 week before the expiration date to avoid service disruption.

## Technical Details

### License Format
The license key contains three parts:
- User identifier
- Expiry timestamp (Unix timestamp)
- Validation hash

Example: `C939DDDB3A-1764979200-00C6F75663`
- Expiry timestamp `1764979200` = December 6, 2025

### Files Involved
- `/home/ubuntu/new-limeclicks/.env` - Environment variable with license
- `/home/ubuntu/.ScreamingFrogSEOSpider/licence.txt` - License file
- `/home/ubuntu/.ScreamingFrogSEOSpider/lease.json` - License lease information

## Troubleshooting

### "License still shows as expired"
- Ensure you restarted all services after updating
- Check that the license key format is correct
- Verify there are no extra spaces or quotes in the license key

### "Services won't restart"
```bash
# Check service status
sudo systemctl status limeclicks-celery
sudo systemctl status limeclicks-gunicorn

# View detailed logs
sudo journalctl -u limeclicks-celery -n 100
```

### "Still getting errors"
- Check the celery-worker.log for specific error messages
- Verify the license was saved correctly in both .env and licence.txt
- Try running a test crawl manually from command line

## Contact
For urgent issues, contact the system administrator or Screaming Frog support.
