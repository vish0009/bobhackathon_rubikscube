"""
Local filesystem storage backend implementation.

Uses separate directories for each storage tier (hot/, warm/, cold/, archive/).
"""

import os
import shutil
from pathlib import Path
from typing import List
from .backend import StorageBackend
from ..models.tier import Tier
from ..config import get_logger

logger = get_logger("system.storage.local")


class LocalFilesystemBackend(StorageBackend):
    """
    Local filesystem implementation of StorageBackend.
    
    Organizes data into tier-specific directories:
    - base_path/hot/
    - base_path/warm/
    - base_path/cold/
    - base_path/archive/
    
    Tier changes are implemented as file moves between directories.
    """
    
    def __init__(self, base_path: str):
        """
        Initialize the local filesystem backend.
        
        Args:
            base_path: Root directory for all storage
        """
        self.base_path = Path(base_path)
        self.tier_directories = {
            Tier.HOT: self.base_path / "hot",
            Tier.WARM: self.base_path / "warm",
            Tier.COLD: self.base_path / "cold",
            Tier.ARCHIVE: self.base_path / "archive",
        }
        
        # Create tier directories if they don't exist
        for tier_dir in self.tier_directories.values():
            tier_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Initialized LocalFilesystemBackend at {base_path}")
    
    def _get_full_path(self, path: str, tier: Tier) -> Path:
        """Get the full filesystem path for a given path and tier."""
        return self.tier_directories[tier] / path
    
    def _find_path_in_tiers(self, path: str) -> tuple[Path, Tier]:
        """Find which tier a path exists in."""
        for tier, tier_dir in self.tier_directories.items():
            full_path = tier_dir / path
            if full_path.exists():
                return full_path, tier
        raise FileNotFoundError(f"Path not found in any tier: {path}")
    
    def write(self, data: bytes, path: str, tier: Tier) -> bool:
        """Write data to the specified tier."""
        try:
            full_path = self._get_full_path(path, tier)
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_bytes(data)
            logger.debug(f"Wrote {len(data)} bytes to {tier}/{path}")
            return True
        except Exception as e:
            logger.error(f"Failed to write to {tier}/{path}: {e}")
            return False
    
    def read(self, path: str) -> bytes:
        """Read data from any tier."""
        full_path, tier = self._find_path_in_tiers(path)
        logger.debug(f"Reading from {tier}/{path}")
        return full_path.read_bytes()
    
    def delete(self, path: str) -> bool:
        """Delete data from any tier."""
        try:
            full_path, tier = self._find_path_in_tiers(path)
            full_path.unlink()
            logger.info(f"Deleted {tier}/{path}")
            return True
        except FileNotFoundError:
            logger.warning(f"Cannot delete non-existent path: {path}")
            return False
        except Exception as e:
            logger.error(f"Failed to delete {path}: {e}")
            return False
    
    def set_tier(self, path: str, tier: Tier) -> bool:
        """Move data to a different tier."""
        try:
            old_path, old_tier = self._find_path_in_tiers(path)
            
            if old_tier == tier:
                logger.debug(f"Path {path} already in tier {tier}")
                return True
            
            new_path = self._get_full_path(path, tier)
            new_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Move file (not copy) to maintain audit trail accuracy
            shutil.move(str(old_path), str(new_path))
            logger.info(f"Moved {path} from {old_tier} to {tier}")
            return True
        except Exception as e:
            logger.error(f"Failed to change tier for {path}: {e}")
            return False
    
    def get_tier(self, path: str) -> Tier:
        """Get the current tier for a path."""
        _, tier = self._find_path_in_tiers(path)
        return tier
    
    def list(self, prefix: str = "") -> List[str]:
        """List all paths with the given prefix across all tiers."""
        paths = []
        for tier_dir in self.tier_directories.values():
            if prefix:
                search_path = tier_dir / prefix
            else:
                search_path = tier_dir
            
            if search_path.exists():
                if search_path.is_file():
                    # If prefix is a file, add it
                    paths.append(str(search_path.relative_to(tier_dir)))
                else:
                    # If prefix is a directory, add all files in it
                    for file_path in search_path.rglob("*"):
                        if file_path.is_file():
                            paths.append(str(file_path.relative_to(tier_dir)))
        
        return sorted(set(paths))  # Remove duplicates and sort
    
    def exists(self, path: str) -> bool:
        """Check if a path exists in any tier."""
        try:
            self._find_path_in_tiers(path)
            return True
        except FileNotFoundError:
            return False

# Made with Bob
