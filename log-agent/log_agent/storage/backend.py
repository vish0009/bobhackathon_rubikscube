"""
Storage backend interface for log data management.

Provides abstraction for different storage implementations (local filesystem, S3, etc.)
"""

from abc import ABC, abstractmethod
from typing import List, Optional
from ..models.tier import Tier


class StorageBackend(ABC):
    """
    Abstract base class for storage backends.
    
    All storage implementations must implement this interface to ensure
    consistent behavior across different storage systems.
    """
    
    @abstractmethod
    def write(self, data: bytes, path: str, tier: Tier) -> bool:
        """
        Write data to storage at the specified path and tier.
        
        Args:
            data: Binary data to write
            path: Storage path (relative to backend root)
            tier: Storage tier for the data
            
        Returns:
            True if write was successful, False otherwise
        """
        pass
    
    @abstractmethod
    def read(self, path: str) -> bytes:
        """
        Read data from storage at the specified path.
        
        Args:
            path: Storage path (relative to backend root)
            
        Returns:
            Binary data read from storage
            
        Raises:
            FileNotFoundError: If path does not exist
        """
        pass
    
    @abstractmethod
    def delete(self, path: str) -> bool:
        """
        Delete data at the specified path.
        
        Args:
            path: Storage path (relative to backend root)
            
        Returns:
            True if deletion was successful, False otherwise
        """
        pass
    
    @abstractmethod
    def set_tier(self, path: str, tier: Tier) -> bool:
        """
        Change the storage tier for data at the specified path.
        
        This is a MOVE operation, not a COPY. The data is moved from
        one tier to another, maintaining the audit trail.
        
        Args:
            path: Storage path (relative to backend root)
            tier: New storage tier
            
        Returns:
            True if tier change was successful, False otherwise
        """
        pass
    
    @abstractmethod
    def get_tier(self, path: str) -> Tier:
        """
        Get the current storage tier for data at the specified path.
        
        Args:
            path: Storage path (relative to backend root)
            
        Returns:
            Current storage tier
            
        Raises:
            FileNotFoundError: If path does not exist
        """
        pass
    
    @abstractmethod
    def list(self, prefix: str = "") -> List[str]:
        """
        List all paths with the given prefix.
        
        Args:
            prefix: Path prefix to filter by (empty string for all)
            
        Returns:
            List of paths matching the prefix
        """
        pass
    
    @abstractmethod
    def exists(self, path: str) -> bool:
        """
        Check if a path exists in storage.
        
        Args:
            path: Storage path (relative to backend root)
            
        Returns:
            True if path exists, False otherwise
        """
        pass

# Made with Bob
