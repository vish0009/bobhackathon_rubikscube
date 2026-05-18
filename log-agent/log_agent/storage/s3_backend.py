"""
S3 storage backend implementation.

Uses S3 storage classes for tier management instead of directory structure.
"""

import os
from typing import List, Optional
import boto3
from botocore.exceptions import ClientError

from .backend import StorageBackend
from ..models.tier import Tier
from ..config import get_logger

logger = get_logger("system.storage.s3")


class S3Backend(StorageBackend):
    """
    S3 implementation of StorageBackend.
    
    Uses S3 storage classes for tier management:
    - HOT: S3 Standard
    - WARM: S3 Standard-IA (Infrequent Access)
    - COLD: S3 Glacier Instant Retrieval
    - ARCHIVE: S3 Glacier Deep Archive
    
    Tier changes use S3 storage class transitions.
    """
    
    # Mapping of Tier enum to S3 storage classes
    TIER_TO_STORAGE_CLASS = {
        Tier.HOT: "STANDARD",
        Tier.WARM: "STANDARD_IA",
        Tier.COLD: "GLACIER_IR",  # Glacier Instant Retrieval
        Tier.ARCHIVE: "DEEP_ARCHIVE"
    }
    
    STORAGE_CLASS_TO_TIER = {
        "STANDARD": Tier.HOT,
        "STANDARD_IA": Tier.WARM,
        "GLACIER_IR": Tier.COLD,
        "GLACIER": Tier.COLD,  # Legacy Glacier maps to COLD
        "DEEP_ARCHIVE": Tier.ARCHIVE
    }
    
    def __init__(
        self,
        bucket_name: str,
        region: str = "us-east-1",
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
        prefix: str = "logs/"
    ):
        """
        Initialize the S3 backend.
        
        Args:
            bucket_name: S3 bucket name
            region: AWS region (default: us-east-1)
            aws_access_key_id: AWS access key (optional, uses env/IAM if not provided)
            aws_secret_access_key: AWS secret key (optional, uses env/IAM if not provided)
            prefix: Object key prefix for all operations (default: logs/)
        """
        self.bucket_name = bucket_name
        self.region = region
        self.prefix = prefix.rstrip('/') + '/' if prefix else ''
        
        # Initialize S3 client
        session_kwargs = {'region_name': region}
        if aws_access_key_id and aws_secret_access_key:
            session_kwargs['aws_access_key_id'] = aws_access_key_id
            session_kwargs['aws_secret_access_key'] = aws_secret_access_key
        
        self.s3_client = boto3.client('s3', **session_kwargs)
        
        # Verify bucket exists and is accessible
        try:
            self.s3_client.head_bucket(Bucket=bucket_name)
            logger.info(f"system.storage.s3: Initialized S3 backend for bucket {bucket_name} in {region}")
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                logger.error(f"system.storage.s3: Bucket {bucket_name} does not exist")
                raise ValueError(f"Bucket {bucket_name} does not exist")
            elif error_code == '403':
                logger.error(f"system.storage.s3: Access denied to bucket {bucket_name}")
                raise ValueError(f"Access denied to bucket {bucket_name}")
            else:
                logger.error(f"system.storage.s3: Error accessing bucket: {e}")
                raise
    
    def _get_full_key(self, path: str) -> str:
        """Get the full S3 object key with prefix."""
        # Remove leading slash if present
        path = path.lstrip('/')
        return f"{self.prefix}{path}"
    
    def write(self, data: bytes, path: str, tier: Tier) -> bool:
        """
        Write data to S3 with appropriate storage class.
        
        Args:
            data: Binary data to write
            path: S3 object key (relative to prefix)
            tier: Storage tier (maps to S3 storage class)
            
        Returns:
            True if write was successful, False otherwise
        """
        try:
            full_key = self._get_full_key(path)
            storage_class = self.TIER_TO_STORAGE_CLASS[tier]
            
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=full_key,
                Body=data,
                StorageClass=storage_class
            )
            
            logger.info(f"system.storage.s3: Wrote {len(data)} bytes to {full_key} with storage class {storage_class}")
            return True
            
        except ClientError as e:
            logger.error(f"system.storage.s3: Error writing to {path}: {e}")
            return False
        except Exception as e:
            logger.error(f"system.storage.s3: Unexpected error writing to {path}: {e}")
            return False
    
    def read(self, path: str) -> bytes:
        """
        Read data from S3.
        
        Args:
            path: S3 object key (relative to prefix)
            
        Returns:
            Binary data read from S3
            
        Raises:
            FileNotFoundError: If object does not exist
        """
        try:
            full_key = self._get_full_key(path)
            
            response = self.s3_client.get_object(
                Bucket=self.bucket_name,
                Key=full_key
            )
            
            data = response['Body'].read()
            logger.info(f"system.storage.s3: Read {len(data)} bytes from {full_key}")
            return data
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'NoSuchKey':
                logger.warning(f"system.storage.s3: Object not found: {path}")
                raise FileNotFoundError(f"Object not found: {path}")
            else:
                logger.error(f"system.storage.s3: Error reading from {path}: {e}")
                raise
        except Exception as e:
            logger.error(f"system.storage.s3: Unexpected error reading from {path}: {e}")
            raise
    
    def delete(self, path: str) -> bool:
        """
        Delete object from S3.
        
        Args:
            path: S3 object key (relative to prefix)
            
        Returns:
            True if deletion was successful, False otherwise
        """
        try:
            full_key = self._get_full_key(path)
            
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=full_key
            )
            
            logger.info(f"system.storage.s3: Deleted {full_key}")
            return True
            
        except ClientError as e:
            logger.error(f"system.storage.s3: Error deleting {path}: {e}")
            return False
        except Exception as e:
            logger.error(f"system.storage.s3: Unexpected error deleting {path}: {e}")
            return False
    
    def set_tier(self, path: str, tier: Tier) -> bool:
        """
        Change the storage class for an S3 object.
        
        This is implemented as a copy operation with new storage class,
        followed by deletion of the original (S3 doesn't support in-place
        storage class changes for all transitions).
        
        Args:
            path: S3 object key (relative to prefix)
            tier: New storage tier (maps to S3 storage class)
            
        Returns:
            True if tier change was successful, False otherwise
        """
        try:
            full_key = self._get_full_key(path)
            new_storage_class = self.TIER_TO_STORAGE_CLASS[tier]
            
            # Copy object to itself with new storage class
            copy_source = {'Bucket': self.bucket_name, 'Key': full_key}
            
            self.s3_client.copy_object(
                Bucket=self.bucket_name,
                CopySource=copy_source,
                Key=full_key,
                StorageClass=new_storage_class,
                MetadataDirective='COPY'
            )
            
            logger.info(f"system.storage.s3: Changed storage class for {full_key} to {new_storage_class}")
            return True
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'NoSuchKey':
                logger.warning(f"system.storage.s3: Object not found for tier change: {path}")
                return False
            else:
                logger.error(f"system.storage.s3: Error changing tier for {path}: {e}")
                return False
        except Exception as e:
            logger.error(f"system.storage.s3: Unexpected error changing tier for {path}: {e}")
            return False
    
    def get_tier(self, path: str) -> Tier:
        """
        Get the current storage class for an S3 object.
        
        Args:
            path: S3 object key (relative to prefix)
            
        Returns:
            Current storage tier
            
        Raises:
            FileNotFoundError: If object does not exist
        """
        try:
            full_key = self._get_full_key(path)
            
            response = self.s3_client.head_object(
                Bucket=self.bucket_name,
                Key=full_key
            )
            
            storage_class = response.get('StorageClass', 'STANDARD')
            tier = self.STORAGE_CLASS_TO_TIER.get(storage_class, Tier.HOT)
            
            logger.debug(f"system.storage.s3: Storage class for {full_key} is {storage_class} (tier: {tier})")
            return tier
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                logger.warning(f"system.storage.s3: Object not found: {path}")
                raise FileNotFoundError(f"Object not found: {path}")
            else:
                logger.error(f"system.storage.s3: Error getting tier for {path}: {e}")
                raise
        except Exception as e:
            logger.error(f"system.storage.s3: Unexpected error getting tier for {path}: {e}")
            raise
    
    def list(self, prefix: str = "") -> List[str]:
        """
        List all S3 objects with the given prefix.
        
        Args:
            prefix: Object key prefix to filter by (relative to backend prefix)
            
        Returns:
            List of object keys matching the prefix (without backend prefix)
        """
        try:
            full_prefix = self._get_full_key(prefix)
            
            objects = []
            paginator = self.s3_client.get_paginator('list_objects_v2')
            
            for page in paginator.paginate(Bucket=self.bucket_name, Prefix=full_prefix):
                if 'Contents' in page:
                    for obj in page['Contents']:
                        # Remove backend prefix from returned keys
                        key = obj['Key']
                        if key.startswith(self.prefix):
                            key = key[len(self.prefix):]
                        objects.append(key)
            
            logger.info(f"system.storage.s3: Listed {len(objects)} objects with prefix {full_prefix}")
            return objects
            
        except ClientError as e:
            logger.error(f"system.storage.s3: Error listing objects with prefix {prefix}: {e}")
            return []
        except Exception as e:
            logger.error(f"system.storage.s3: Unexpected error listing objects: {e}")
            return []
    
    def exists(self, path: str) -> bool:
        """
        Check if an S3 object exists.
        
        Args:
            path: S3 object key (relative to prefix)
            
        Returns:
            True if object exists, False otherwise
        """
        try:
            full_key = self._get_full_key(path)
            
            self.s3_client.head_object(
                Bucket=self.bucket_name,
                Key=full_key
            )
            
            return True
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                return False
            else:
                logger.error(f"system.storage.s3: Error checking existence of {path}: {e}")
                return False
        except Exception as e:
            logger.error(f"system.storage.s3: Unexpected error checking existence of {path}: {e}")
            return False

# Made with Bob
