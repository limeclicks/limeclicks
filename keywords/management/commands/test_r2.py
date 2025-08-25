"""
Management command to test R2 storage functionality
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from services.r2_storage import get_r2_service
import json


class Command(BaseCommand):
    help = 'Test R2 storage functionality'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--upload',
            action='store_true',
            help='Test file upload'
        )
        parser.add_argument(
            '--download',
            type=str,
            help='Download file by key'
        )
        parser.add_argument(
            '--list',
            action='store_true',
            help='List files in bucket'
        )
        parser.add_argument(
            '--delete',
            type=str,
            help='Delete file by key'
        )
    
    def handle(self, *args, **options):
        """Handle the command"""
        try:
            r2 = get_r2_service()
            self.stdout.write(self.style.SUCCESS('✅ R2 Storage initialized successfully'))
            self.stdout.write(f'   Bucket: {r2.bucket_name}')
            self.stdout.write(f'   Endpoint: {r2.endpoint_url}\n')
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Failed to initialize R2: {str(e)}'))
            return
        
        if options['upload']:
            self.test_upload(r2)
        
        if options['download']:
            self.test_download(r2, options['download'])
        
        if options['list']:
            self.list_files(r2)
        
        if options['delete']:
            self.delete_file(r2, options['delete'])
        
        if not any([options['upload'], options['download'], options['list'], options['delete']]):
            # Run basic connectivity test
            self.test_basic(r2)
    
    def test_basic(self, r2):
        """Test basic R2 connectivity"""
        self.stdout.write('\n📋 Testing basic R2 connectivity...')
        
        # Test upload
        test_key = f'test/connection_test_{timezone.now().strftime("%Y%m%d_%H%M%S")}.txt'
        test_content = f'Test connection at {timezone.now()}'
        
        result = r2.upload_file(
            test_content.encode('utf-8'),
            test_key,
            content_type='text/plain'
        )
        
        if result['success']:
            self.stdout.write(self.style.SUCCESS(f'✅ Upload successful: {test_key}'))
            
            # Test file exists
            if r2.file_exists(test_key):
                self.stdout.write(self.style.SUCCESS('✅ File existence check passed'))
            
            # Test download
            content = r2.download_file(test_key)
            if content:
                self.stdout.write(self.style.SUCCESS('✅ Download successful'))
                self.stdout.write(f'   Content: {content.decode("utf-8")}')
            
            # Get file info
            info = r2.get_file_info(test_key)
            if info:
                self.stdout.write(self.style.SUCCESS('✅ File info retrieved:'))
                self.stdout.write(f'   Size: {info["size"]} bytes')
                self.stdout.write(f'   Type: {info["content_type"]}')
            
            # Generate URL
            url = r2.get_url(test_key, expiration=3600)
            if url:
                self.stdout.write(self.style.SUCCESS('✅ Presigned URL generated:'))
                self.stdout.write(f'   URL: {url[:100]}...')
            
            # Clean up
            if r2.delete_file(test_key):
                self.stdout.write(self.style.SUCCESS(f'✅ Test file cleaned up: {test_key}'))
        else:
            self.stdout.write(self.style.ERROR(f'❌ Upload failed: {result.get("error")}'))
    
    def test_upload(self, r2):
        """Test file upload"""
        self.stdout.write('\n📤 Testing file upload...')
        
        # Upload text file
        text_key = f'test/sample_{timezone.now().strftime("%Y%m%d_%H%M%S")}.txt'
        text_content = 'This is a test file for R2 storage'
        
        result = r2.upload_file(
            text_content.encode('utf-8'),
            text_key,
            content_type='text/plain',
            metadata={'purpose': 'test', 'created': str(timezone.now())}
        )
        
        if result['success']:
            self.stdout.write(self.style.SUCCESS(f'✅ Text file uploaded: {text_key}'))
            self.stdout.write(f'   URL: {result["url"]}')
        
        # Upload JSON
        json_key = f'test/data_{timezone.now().strftime("%Y%m%d_%H%M%S")}.json'
        json_data = {
            'test': True,
            'timestamp': str(timezone.now()),
            'data': ['item1', 'item2', 'item3']
        }
        
        result = r2.upload_json(json_data, json_key)
        
        if result['success']:
            self.stdout.write(self.style.SUCCESS(f'✅ JSON uploaded: {json_key}'))
    
    def test_download(self, r2, key):
        """Test file download"""
        self.stdout.write(f'\n📥 Downloading file: {key}')
        
        content = r2.download_file(key)
        if content:
            self.stdout.write(self.style.SUCCESS(f'✅ Downloaded {len(content)} bytes'))
            
            # Try to decode as text
            try:
                text = content.decode('utf-8')
                self.stdout.write(f'Content preview: {text[:200]}...' if len(text) > 200 else f'Content: {text}')
            except:
                self.stdout.write(f'Binary content: {len(content)} bytes')
        else:
            self.stdout.write(self.style.ERROR(f'❌ Failed to download: {key}'))
    
    def list_files(self, r2):
        """List files in bucket"""
        self.stdout.write('\n📁 Listing files in R2 bucket...')
        
        # List all files
        files = r2.list_files(max_keys=20)
        
        if files:
            self.stdout.write(self.style.SUCCESS(f'Found {len(files)} files:'))
            for file_key in files:
                info = r2.get_file_info(file_key)
                if info:
                    size = info['size']
                    modified = info['last_modified']
                    self.stdout.write(f'  📄 {file_key} ({size} bytes) - {modified}')
                else:
                    self.stdout.write(f'  📄 {file_key}')
        else:
            self.stdout.write('No files found in bucket')
        
        # List files with prefix
        test_files = r2.list_files(prefix='test/', max_keys=10)
        if test_files:
            self.stdout.write(f'\nTest files ({len(test_files)}):')
            for file_key in test_files:
                self.stdout.write(f'  📄 {file_key}')
    
    def delete_file(self, r2, key):
        """Delete a file"""
        self.stdout.write(f'\n🗑️  Deleting file: {key}')
        
        if r2.delete_file(key):
            self.stdout.write(self.style.SUCCESS(f'✅ Successfully deleted: {key}'))
        else:
            self.stdout.write(self.style.ERROR(f'❌ Failed to delete: {key}'))