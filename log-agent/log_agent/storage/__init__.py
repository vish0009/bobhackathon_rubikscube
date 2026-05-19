"""
Storage backend implementations for log data management.
"""

from .backend import StorageBackend
from .local_backend import LocalFilesystemBackend
from .s3_backend import S3Backend

__all__ = [
    "StorageBackend",
    "LocalFilesystemBackend",
    "S3Backend",
]

# Made with Bob
