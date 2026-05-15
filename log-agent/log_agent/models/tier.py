"""
Storage tier enumeration for log retention management.
"""

from enum import Enum


class Tier(str, Enum):
    """
    Storage tiers for log data with different cost and access characteristics.
    
    HOT: Frequently accessed, high cost, fast retrieval
    WARM: Occasionally accessed, medium cost, moderate retrieval
    COLD: Rarely accessed, low cost, slower retrieval
    ARCHIVE: Long-term retention, lowest cost, slowest retrieval
    """
    HOT = "hot"
    WARM = "warm"
    COLD = "cold"
    ARCHIVE = "archive"
    
    def __str__(self) -> str:
        return self.value

# Made with Bob
