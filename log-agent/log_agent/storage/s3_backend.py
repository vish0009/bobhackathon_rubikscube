"""
S3 storage backend implementation (stub for Phase 2).

Will use S3 storage classes instead of directory structure for tier management.
"""

from typing import List
from .backend import StorageBackend
from ..models.tier import Tier
from ..config import get_logger

logger = get_logger("system.storage.s3")


class S3Backend(StorageBackend):
    """
    S3 implementation of StorageBackend (stub for Phase 2).
    
    Will use S3 storage classes for tier management:
    - HOT: S3 Standard
    - WARM: S3 Standard-IA
    - COLD: S3 Glacier Instant Retrieval
    - ARCHIVE: S3 Glacier Deep Archive
    
    Tier changes will use S3 lifecycle transitions or direct storage class changes.
    """
    
    def __init__(self, bucket_name: str, region: str = "us-east-1"):
        """
        Initialize the S3 backend.
        
        Args:
            bucket_name: S3 bucket name
            region: AWS region
        """
        self.bucket_name = bucket_name
        self.region = region
        logger.info(f"S3Backend stub initialized for bucket {bucket_name} in {region}")
        raise NotImplementedError("S3Backend is a stub for Phase 2")
    
    def write(self, data: bytes, path: str, tier: Tier) -> bool:
        """
        Write data to S3 with appropriate storage class.
        
        Args:
            data: Binary data to write
            path: S3 object key
            tier: Storage tier (maps to S3 storage class)
            
        Returns:
            True if write was successful, False otherwise
        """
        raise NotImplementedError("S3Backend is a stub for Phase 2")
    
    def read(self, path: str) -> bytes:
        """
        Read data from S3.
        
        Args:
            path: S3 object key
            
        Returns:
            Binary data read from S3
            
        Raises:
            FileNotFoundError: If object does not exist
        """
        raise NotImplementedError("S3Backend is a stub for Phase 2")
    
    def delete(self, path: str) -> bool:
        """
        Delete object from S3.
        
        Args:
            path: S3 object key
            
        Returns:
            True if deletion was successful, False otherwise
        """
        raise NotImplementedError("S3Backend is a stub for Phase 2")
    
    def set_tier(self, path: str, tier: Tier) -> bool:
        """
        Change the storage class for an S3 object.
        
        Args:
            path: S3 object key
            tier: New storage tier (maps to S3 storage class)
            
        Returns:
            True if tier change was successful, False otherwise
        """
        raise NotImplementedError("S3Backend is a stub for Phase 2")
    
    def get_tier(self, path: str) -> Tier:
        """
        Get the current storage class for an S3 object.
        
        Args:
            path: S3 object key
            
        Returns:
            Current storage tier
            
        Raises:
            FileNotFoundError: If object does not exist
        """
        raise NotImplementedError("S3Backend is a stub for Phase 2")
    
    def list(self, prefix: str = "") -> List[str]:
        """
        List all S3 objects with the given prefix.
        
        Args:
            prefix: Object key prefix to filter by
            
        Returns:
            List of object keys matching the prefix
        """
        raise NotImplementedError("S3Backend is a stub for Phase 2")
    
    def exists(self, path: str) -> bool:
        """
        Check if an S3 object exists.
        
        Args:
            path: S3 object key
            
        Returns:
            True if object exists, False otherwise
        """
        raise NotImplementedError("S3Backend is a stub for Phase 2")

# Made with Bob
