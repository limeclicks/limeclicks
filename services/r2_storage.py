"""
Cloudflare R2 Storage Service
Handles file uploads, downloads, and management for R2 storage
"""

import os
import boto3
import logging
import mimetypes
import gzip
from typing import Optional, Dict, Any, BinaryIO, Union
from datetime import datetime
from botocore.exceptions import ClientError
import hashlib
import json

logger = logging.getLogger(__name__)


class R2StorageService:
    """
    Service for interacting with Cloudflare R2 storage
    R2 is S3-compatible, so we use boto3 S3 client
    """
    
    def __init__(
        self,
        access_key_id: Optional[str] = None,
        secret_access_key: Optional[str] = None,
        bucket_name: Optional[str] = None,
        endpoint_url: Optional[str] = None
    ):
        """
        Initialize R2 storage service
        
        Args:
            access_key_id: R2 access key ID
            secret_access_key: R2 secret access key
            bucket_name: R2 bucket name
            endpoint_url: R2 endpoint URL
        """
        self.access_key_id = access_key_id or os.getenv('R2_ACCESS_KEY_ID')
        self.secret_access_key = secret_access_key or os.getenv('R2_SECRET_ACCESS_KEY')
        self.bucket_name = bucket_name or os.getenv('R2_BUCKET_NAME')
        self.endpoint_url = endpoint_url or os.getenv('R2_ENDPOINT_URL')
        
        if not all([self.access_key_id, self.secret_access_key, self.bucket_name, self.endpoint_url]):
            raise ValueError("R2 credentials not properly configured. Check environment variables.")
        
        # Initialize S3 client for R2
        self.client = boto3.client(
            's3',
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.access_key_id,
            aws_secret_access_key=self.secret_access_key,
            region_name='auto'  # R2 uses 'auto' for region
        )
        
        # Initialize S3 resource for higher-level operations
        self.resource = boto3.resource(
            's3',
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.access_key_id,
            aws_secret_access_key=self.secret_access_key,
            region_name='auto'
        )
        
        self.bucket = self.resource.Bucket(self.bucket_name)
    
    def upload_file(
        self,
        file_obj: Union[BinaryIO, bytes],
        key: str,
        metadata: Optional[Dict[str, str]] = None,
        content_type: Optional[str] = None,
        public: bool = False
    ) -> Dict[str, Any]:
        """
        Upload a file to R2
        
        Args:
            file_obj: File object or bytes to upload
            key: Object key (path) in R2
            metadata: Optional metadata to attach to the object
            content_type: MIME type of the file
            public: Whether to make the file publicly accessible
        
        Returns:
            Dict with upload details including URL
        """
        try:
            # Prepare upload arguments
            extra_args = {}
            
            # Set content type
            if content_type:
                extra_args['ContentType'] = content_type
            elif isinstance(key, str):
                # Try to guess content type from file extension
                guessed_type, _ = mimetypes.guess_type(key)
                if guessed_type:
                    extra_args['ContentType'] = guessed_type
            
            # Add metadata
            if metadata:
                extra_args['Metadata'] = metadata
            
            # Set ACL if public
            if public:
                extra_args['ACL'] = 'public-read'
            
            # Upload the file
            if isinstance(file_obj, bytes):
                # Upload bytes directly
                self.client.put_object(
                    Bucket=self.bucket_name,
                    Key=key,
                    Body=file_obj,
                    **extra_args
                )
            else:
                # Upload file object
                self.client.upload_fileobj(
                    file_obj,
                    self.bucket_name,
                    key,
                    ExtraArgs=extra_args if extra_args else None
                )
            
            # Generate URL
            url = self.get_url(key, public=public)
            
            logger.info(f"Successfully uploaded file to R2: {key}")
            
            return {
                'success': True,
                'key': key,
                'bucket': self.bucket_name,
                'url': url,
                'size': len(file_obj) if isinstance(file_obj, bytes) else None
            }
            
        except ClientError as e:
            logger.error(f"Failed to upload file to R2: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
        except Exception as e:
            logger.error(f"Unexpected error uploading to R2: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def download_file(self, key: str) -> Optional[bytes]:
        """
        Download a file from R2
        
        Args:
            key: Object key in R2
        
        Returns:
            File contents as bytes or None if failed
        """
        try:
            response = self.client.get_object(
                Bucket=self.bucket_name,
                Key=key
            )
            content = response['Body'].read()
            logger.info(f"Successfully downloaded file from R2: {key}")
            return content
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                logger.warning(f"File not found in R2: {key}")
            else:
                logger.error(f"Failed to download file from R2: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error downloading from R2: {str(e)}")
            return None
    
    def delete_file(self, key: str) -> bool:
        """
        Delete a file from R2
        
        Args:
            key: Object key in R2
        
        Returns:
            True if successful, False otherwise
        """
        try:
            self.client.delete_object(
                Bucket=self.bucket_name,
                Key=key
            )
            logger.info(f"Successfully deleted file from R2: {key}")
            return True
            
        except ClientError as e:
            logger.error(f"Failed to delete file from R2: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error deleting from R2: {str(e)}")
            return False
    
    def file_exists(self, key: str) -> bool:
        """
        Check if a file exists in R2
        
        Args:
            key: Object key in R2
        
        Returns:
            True if file exists, False otherwise
        """
        try:
            self.client.head_object(
                Bucket=self.bucket_name,
                Key=key
            )
            return True
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                return False
            logger.error(f"Error checking file existence in R2: {str(e)}")
            return False
    
    def list_files(
        self,
        prefix: Optional[str] = None,
        max_keys: int = 1000
    ) -> list:
        """
        List files in R2 bucket
        
        Args:
            prefix: Optional prefix to filter files
            max_keys: Maximum number of keys to return
        
        Returns:
            List of file keys
        """
        try:
            params = {
                'Bucket': self.bucket_name,
                'MaxKeys': max_keys
            }
            
            if prefix:
                params['Prefix'] = prefix
            
            response = self.client.list_objects_v2(**params)
            
            if 'Contents' not in response:
                return []
            
            return [obj['Key'] for obj in response['Contents']]
            
        except ClientError as e:
            logger.error(f"Failed to list files in R2: {str(e)}")
            return []
    
    def get_url(self, key: str, expiration: int = 3600, public: bool = False) -> str:
        """
        Generate a URL for accessing a file
        
        Args:
            key: Object key in R2
            expiration: URL expiration time in seconds (for presigned URLs)
            public: If True, return public URL; if False, return presigned URL
        
        Returns:
            URL to access the file
        """
        if public:
            # Return public URL (assumes bucket is configured for public access)
            # Format: https://pub-{hash}.r2.dev/{key} or custom domain
            # This depends on your R2 bucket configuration
            return f"{self.endpoint_url}/{self.bucket_name}/{key}"
        else:
            # Generate presigned URL
            try:
                url = self.client.generate_presigned_url(
                    'get_object',
                    Params={'Bucket': self.bucket_name, 'Key': key},
                    ExpiresIn=expiration
                )
                return url
            except ClientError as e:
                logger.error(f"Failed to generate presigned URL: {str(e)}")
                return ""
    
    def get_file_info(self, key: str) -> Optional[Dict[str, Any]]:
        """
        Get metadata about a file
        
        Args:
            key: Object key in R2
        
        Returns:
            Dict with file metadata or None if not found
        """
        try:
            response = self.client.head_object(
                Bucket=self.bucket_name,
                Key=key
            )
            
            return {
                'key': key,
                'size': response.get('ContentLength', 0),
                'content_type': response.get('ContentType', ''),
                'last_modified': response.get('LastModified', ''),
                'etag': response.get('ETag', '').strip('"'),
                'metadata': response.get('Metadata', {})
            }
            
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                logger.warning(f"File not found in R2: {key}")
            else:
                logger.error(f"Failed to get file info from R2: {str(e)}")
            return None
    
    def upload_json(self, data: Dict[str, Any], key: str) -> Dict[str, Any]:
        """
        Upload JSON data to R2
        
        Args:
            data: Dictionary to save as JSON
            key: Object key in R2
        
        Returns:
            Upload result
        """
        json_bytes = json.dumps(data, indent=2).encode('utf-8')
        return self.upload_file(
            json_bytes,
            key,
            content_type='application/json'
        )
    
    def download_json(self, key: str) -> Optional[Dict[str, Any]]:
        """
        Download and parse JSON from R2 (supports both plain and gzipped JSON)
        
        Args:
            key: Object key in R2
        
        Returns:
            Parsed JSON data or None if failed
        """
        content = self.download_file(key)
        if content:
            try:
                # Check if the file is gzipped by extension or content
                if key.endswith('.gz'):
                    # Decompress gzipped content
                    decompressed = gzip.decompress(content)
                    return json.loads(decompressed.decode('utf-8'))
                else:
                    # Regular JSON file
                    return json.loads(content.decode('utf-8'))
            except (json.JSONDecodeError, gzip.BadGzipFile) as e:
                logger.error(f"Failed to parse JSON from R2: {str(e)}")
                return None
        return None
    
    def generate_unique_key(
        self,
        prefix: str,
        filename: str,
        include_timestamp: bool = True
    ) -> str:
        """
        Generate a unique key for storing files
        
        Args:
            prefix: Directory prefix (e.g., 'keywords/results')
            filename: Original filename
            include_timestamp: Whether to include timestamp in the key
        
        Returns:
            Unique key for the file
        """
        # Get file extension
        name, ext = os.path.splitext(filename)
        
        # Generate unique identifier
        if include_timestamp:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            unique_part = f"{timestamp}_{hashlib.md5(name.encode()).hexdigest()[:8]}"
        else:
            unique_part = hashlib.md5(f"{name}{datetime.now()}".encode()).hexdigest()[:16]
        
        # Construct key
        key = f"{prefix}/{unique_part}{ext}"
        
        return key
    
    def create_folder_structure(self, base_path: str) -> str:
        """
        Create a folder structure based on date
        
        Args:
            base_path: Base path (e.g., 'keywords/results')
        
        Returns:
            Path with date structure (e.g., 'keywords/results/2024/01/15')
        """
        now = datetime.now()
        return f"{base_path}/{now.year}/{now.month:02d}/{now.day:02d}"
    
    def generate_presigned_url(self, key: str, expiry: int = 3600) -> Dict[str, Any]:
        """
        Generate a presigned URL for accessing a file
        
        Args:
            key: Object key in R2
            expiry: URL expiration time in seconds (default 1 hour)
        
        Returns:
            Dict with success status and URL
        """
        try:
            url = self.client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket_name, 'Key': key},
                ExpiresIn=expiry
            )
            return {
                'success': True,
                'url': url
            }
        except ClientError as e:
            logger.error(f"Failed to generate presigned URL: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
        except Exception as e:
            logger.error(f"Unexpected error generating presigned URL: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }


# Singleton instance
_r2_service = None

def get_r2_service() -> R2StorageService:
    """
    Get singleton instance of R2StorageService
    
    Returns:
        R2StorageService instance
    """
    global _r2_service
    if _r2_service is None:
        _r2_service = R2StorageService()
    return _r2_service