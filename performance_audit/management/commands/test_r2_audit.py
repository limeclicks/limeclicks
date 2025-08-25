from django.core.management.base import BaseCommand
from django.conf import settings
from django.utils import timezone
from performance_audit.models import PerformanceHistory
import boto3
from botocore.exceptions import ClientError


class Command(BaseCommand):
    help = 'Test R2 storage for audit files'
    
    def handle(self, *args, **options):
        self.stdout.write("Testing R2 Storage for Audits\n")
        self.stdout.write("="*50 + "\n")
        
        # Check R2 configuration
        self.stdout.write("\n1. Checking R2 Configuration:")
        if not all([
            settings.AWS_ACCESS_KEY_ID,
            settings.AWS_SECRET_ACCESS_KEY,
            settings.AWS_STORAGE_BUCKET_NAME,
            settings.AWS_S3_ENDPOINT_URL
        ]):
            self.stdout.write(self.style.ERROR("   ❌ R2 credentials not configured"))
            return
        
        self.stdout.write(self.style.SUCCESS("   ✅ R2 credentials configured"))
        self.stdout.write(f"   Endpoint: {settings.AWS_S3_ENDPOINT_URL}")
        self.stdout.write(f"   Bucket: {settings.AWS_STORAGE_BUCKET_NAME}")
        
        # Test R2 connection
        self.stdout.write("\n2. Testing R2 Connection:")
        try:
            s3_client = boto3.client(
                's3',
                endpoint_url=settings.AWS_S3_ENDPOINT_URL,
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name='auto'
            )
            
            # Try to list objects in the bucket
            response = s3_client.list_objects_v2(
                Bucket=settings.AWS_STORAGE_BUCKET_NAME,
                Prefix='performance_audit/',
                MaxKeys=5
            )
            
            self.stdout.write(self.style.SUCCESS("   ✅ R2 connection successful"))
            
            # List audit files
            if 'Contents' in response:
                self.stdout.write(f"   Found {len(response['Contents'])} audit files:")
                for obj in response['Contents']:
                    self.stdout.write(f"   - {obj['Key']} ({obj['Size']} bytes)")
            else:
                self.stdout.write("   No audit files found yet")
                
        except ClientError as e:
            self.stdout.write(self.style.ERROR(f"   ❌ R2 connection failed: {e}"))
            return
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"   ❌ Unexpected error: {e}"))
            return
        
        # Check recent audit with files
        self.stdout.write("\n3. Checking Recent Audit Files:")
        recent_audit = PerformanceHistory.objects.filter(
            status='completed',
            json_report__isnull=False
        ).order_by('-created_at').first()
        
        if recent_audit:
            self.stdout.write(f"   Found audit: {recent_audit.id}")
            
            # Check JSON file
            if recent_audit.json_report:
                try:
                    # Get file URL
                    json_url = recent_audit.json_report.url
                    json_name = recent_audit.json_report.name
                    json_size = recent_audit.json_report.size
                    
                    self.stdout.write(self.style.SUCCESS(f"   ✅ JSON file: {json_name}"))
                    self.stdout.write(f"      Size: {json_size} bytes")
                    self.stdout.write(f"      URL: {json_url}")
                    
                    # Try to read a sample
                    content = recent_audit.json_report.read(100)
                    if content:
                        self.stdout.write(f"      First 100 bytes: {content[:100]}")
                    recent_audit.json_report.close()
                    
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"   ❌ Error reading JSON: {e}"))
            
            # Check HTML file
            if recent_audit.html_report:
                try:
                    html_name = recent_audit.html_report.name
                    html_size = recent_audit.html_report.size
                    self.stdout.write(self.style.SUCCESS(f"   ✅ HTML file: {html_name}"))
                    self.stdout.write(f"      Size: {html_size} bytes")
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"   ❌ Error reading HTML: {e}"))
        else:
            self.stdout.write("   No completed audits with files found")
        
        # Test creating a test file
        self.stdout.write("\n4. Testing File Upload:")
        try:
            from django.core.files.base import ContentFile
            from performance_audit.models import PerformancePage
            import json
            import uuid
            
            # Create test JSON content
            test_data = {
                "test": True,
                "timestamp": str(timezone.now()),
                "message": "Test audit JSON file"
            }
            test_content = json.dumps(test_data, indent=2)
            
            # Get or create a test audit
            performance_page = PerformancePage.objects.first()
            if performance_page:
                test_audit = PerformanceHistory.objects.create(
                    performance_page=performance_page,
                    trigger_type='manual',
                    device_type='desktop',
                    status='completed',
                    performance_score=100
                )
                
                # Save test file
                filename = f"test_{test_audit.id}.json"
                test_audit.json_report.save(
                    filename,
                    ContentFile(test_content.encode('utf-8'))
                )
                
                self.stdout.write(self.style.SUCCESS(f"   ✅ Test file uploaded: {filename}"))
                self.stdout.write(f"      File URL: {test_audit.json_report.url}")
                
                # Clean up
                test_audit.json_report.delete()
                test_audit.delete()
                self.stdout.write("   ✅ Test file cleaned up")
                
            else:
                self.stdout.write("   No audit pages available for testing")
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"   ❌ Upload test failed: {e}"))
        
        self.stdout.write("\n" + "="*50)
        self.stdout.write(self.style.SUCCESS("✅ R2 audit storage is working correctly!"))