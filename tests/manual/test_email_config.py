#!/usr/bin/env python
"""
Test email configuration and Brevo templates
"""
import os
import django
import sys

# Setup Django environment
sys.path.insert(0, '/home/muaaz/enterprise/limeclicks')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'limeclicks.settings')
django.setup()

from django.conf import settings
from accounts.email_backend import BrevoEmailBackend

def test_email_config():
    """Test email configuration"""
    
    print("\n" + "=" * 60)
    print("Email Configuration Test")
    print("=" * 60)
    
    # Check settings
    print("\n1. Email Settings:")
    print(f"   • BREVO_API_KEY: {'✓ Configured' if os.getenv('BREVO_API_KEY') else '✗ Not configured'}")
    print(f"   • DEFAULT_FROM_EMAIL: {settings.DEFAULT_FROM_EMAIL}")
    print(f"   • SITE_URL: {settings.SITE_URL}")
    
    # Test Brevo backend
    print("\n2. Brevo Backend Test:")
    try:
        backend = BrevoEmailBackend()
        print("   ✓ Brevo backend initialized successfully")
        
        # Check if we can access the API
        import brevo_python
        configuration = brevo_python.Configuration()
        configuration.api_key['api-key'] = os.getenv('BREVO_API_KEY')
        api_instance = brevo_python.AccountApi(brevo_python.ApiClient(configuration))
        
        try:
            account = api_instance.get_account()
            print(f"   ✓ Connected to Brevo account: {account.email}")
            print(f"   • Company: {account.company_name}")
            print(f"   • Plan: {account.plan[0].type if account.plan else 'Unknown'}")
        except Exception as e:
            print(f"   ⚠️  Could not retrieve account info: {str(e)}")
        
    except Exception as e:
        print(f"   ✗ Failed to initialize Brevo backend: {str(e)}")
    
    # Template Information
    print("\n3. Email Templates Configuration:")
    print("   Template IDs used in the application:")
    print("   • Template 2: Email Verification (for new user registration)")
    print("   • Template 3: Password Reset")
    print("   • Template 4: Project Invitation (new users)")
    print("   • Template 5: Project Invitation (existing users)")
    
    print("\n4. Template Parameters:")
    print("   Template 4 (New User Invitation):")
    print("     - project: Project domain name")
    print("     - reg_link: Registration link with invitation token")
    print("\n   Template 5 (Existing User Invitation):")
    print("     - name: User's display name")
    
    # Test sending a test email (optional)
    print("\n5. Email Sending Test:")
    test_send = input("   Do you want to send a test email? (y/n): ").strip().lower()
    
    if test_send == 'y':
        test_email = input("   Enter email address for test: ").strip()
        if test_email:
            try:
                success = backend.send_template_email(
                    to_emails=[test_email],
                    template_id=5,  # Using existing user template
                    template_params={'name': 'Test User'}
                )
                if success:
                    print(f"   ✓ Test email sent successfully to {test_email}")
                else:
                    print(f"   ✗ Failed to send test email")
            except Exception as e:
                print(f"   ✗ Error sending test email: {str(e)}")
    
    print("\n" + "=" * 60)
    print("✅ Email Configuration Test Complete!")
    print("\nIMPORTANT:")
    print("Make sure the following templates are configured in Brevo:")
    print("  • Template 4: For inviting new users (with project and reg_link params)")
    print("  • Template 5: For inviting existing users (with name param)")
    print("=" * 60)

if __name__ == "__main__":
    test_email_config()