"""
Check Screaming Frog license expiry and send reminders
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from datetime import timedelta

from onpageaudit.models import ScreamingFrogLicense
from accounts.models import User


class Command(BaseCommand):
    help = 'Check Screaming Frog license expiry and send reminders'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Run without sending emails'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Send reminder regardless of when last sent'
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        force = options['force']
        
        self.stdout.write(self.style.NOTICE('=' * 60))
        self.stdout.write(self.style.NOTICE('Screaming Frog License Expiry Check'))
        self.stdout.write(self.style.NOTICE('=' * 60))
        
        # Get license
        try:
            license_obj = ScreamingFrogLicense.objects.first()
            
            if not license_obj:
                self.stdout.write(self.style.WARNING('No license record found'))
                return
            
            # Check if license has expiry date
            if not license_obj.expiry_date:
                self.stdout.write('License expiry date not set - manual tracking required')
                return
            
            days_until_expiry = license_obj.days_until_expiry()
            
            self.stdout.write(f'\nLicense Status:')
            self.stdout.write(f'  License Key: {license_obj.license_key[:10]}...')
            self.stdout.write(f'  Expiry Date: {license_obj.expiry_date}')
            self.stdout.write(f'  Days Until Expiry: {days_until_expiry}')
            
            # Determine if reminder should be sent
            should_send_reminder = False
            urgency = 'info'
            
            if days_until_expiry < 0:
                # Already expired
                self.stdout.write(self.style.ERROR(f'  Status: EXPIRED ({abs(days_until_expiry)} days ago)'))
                should_send_reminder = True
                urgency = 'critical'
                
            elif days_until_expiry <= 7:
                # Expiring within a week
                self.stdout.write(self.style.ERROR(f'  Status: CRITICAL - Expiring in {days_until_expiry} days'))
                should_send_reminder = True
                urgency = 'critical'
                
            elif days_until_expiry <= 30:
                # Expiring within a month
                self.stdout.write(self.style.WARNING(f'  Status: WARNING - Expiring in {days_until_expiry} days'))
                should_send_reminder = True
                urgency = 'warning'
                
            elif days_until_expiry <= 60:
                # Expiring within 2 months
                self.stdout.write(self.style.NOTICE(f'  Status: NOTICE - Expiring in {days_until_expiry} days'))
                should_send_reminder = True
                urgency = 'notice'
                
            else:
                self.stdout.write(self.style.SUCCESS(f'  Status: OK - Valid for {days_until_expiry} days'))
            
            # Check if reminder was recently sent (unless forced)
            if should_send_reminder and not force:
                if license_obj.last_reminder_sent:
                    days_since_reminder = (timezone.now() - license_obj.last_reminder_sent).days
                    
                    # Don't send if reminder was sent in last 7 days
                    if days_since_reminder < 7:
                        self.stdout.write(f'\n  Last reminder sent {days_since_reminder} days ago - skipping')
                        should_send_reminder = False
            
            # Send reminder if needed
            if should_send_reminder:
                if dry_run:
                    self.stdout.write('\n' + self.style.WARNING('DRY RUN - Email would be sent'))
                    self._display_email_content(license_obj, days_until_expiry, urgency)
                else:
                    self._send_reminder_email(license_obj, days_until_expiry, urgency)
                    
                    # Update last reminder sent
                    license_obj.last_reminder_sent = timezone.now()
                    license_obj.save(update_fields=['last_reminder_sent'])
                    
                    self.stdout.write(self.style.SUCCESS('\n✓ Reminder email sent'))
            else:
                self.stdout.write('\n✓ No reminder needed')
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error checking license: {str(e)}'))
    
    def _send_reminder_email(self, license_obj, days_until_expiry, urgency):
        """Send reminder email to admins"""
        # Get admin users
        admin_emails = User.objects.filter(
            is_staff=True, is_active=True
        ).values_list('email', flat=True)
        
        if not admin_emails:
            self.stdout.write(self.style.WARNING('No admin emails found'))
            return
        
        # Prepare email content
        subject = self._get_email_subject(days_until_expiry, urgency)
        message = self._get_email_message(license_obj, days_until_expiry, urgency)
        
        # Send email
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            list(admin_emails),
            fail_silently=False
        )
        
        self.stdout.write(f'  Sent to: {", ".join(admin_emails)}')
    
    def _get_email_subject(self, days_until_expiry, urgency):
        """Get email subject based on urgency"""
        if days_until_expiry < 0:
            return '[CRITICAL] Screaming Frog License Has Expired'
        elif urgency == 'critical':
            return f'[URGENT] Screaming Frog License Expiring in {days_until_expiry} Days'
        elif urgency == 'warning':
            return f'[WARNING] Screaming Frog License Expiring in {days_until_expiry} Days'
        else:
            return f'[NOTICE] Screaming Frog License Expiring in {days_until_expiry} Days'
    
    def _get_email_message(self, license_obj, days_until_expiry, urgency):
        """Get email message content"""
        if days_until_expiry < 0:
            status = f'expired {abs(days_until_expiry)} days ago'
            action = 'Please renew immediately to continue using full features.'
        else:
            status = f'expiring in {days_until_expiry} days'
            action = 'Please renew before expiry to avoid service disruption.'
        
        message = f"""
Screaming Frog License Expiry Notification
{'=' * 40}

License Status: {license_obj.license_status}
License Key: {license_obj.license_key[:20]}...
Expiry Date: {license_obj.expiry_date}

Your Screaming Frog SEO Spider license is {status}.

{action}

Current Limits:
- With valid license: {license_obj.max_urls or 'Unlimited'} URLs per crawl
- Without license: 500 URLs per crawl (free version)

To renew your license:
1. Visit: https://www.screamingfrog.co.uk/seo-spider/
2. Purchase or renew your license
3. Update the SCREAMING_FROG_LICENSE in your .env file
4. Run: python manage.py validate_screaming_frog_license

Impact if not renewed:
- Crawls will be limited to 500 URLs
- Large site audits will be incomplete
- Some advanced features may be unavailable

This is an automated reminder from the LimeClicks SEO Platform.
"""
        return message
    
    def _display_email_content(self, license_obj, days_until_expiry, urgency):
        """Display what email would contain (for dry run)"""
        self.stdout.write('\nEmail Content:')
        self.stdout.write('-' * 40)
        self.stdout.write(f'Subject: {self._get_email_subject(days_until_expiry, urgency)}')
        self.stdout.write(f'Message:\n{self._get_email_message(license_obj, days_until_expiry, urgency)}')