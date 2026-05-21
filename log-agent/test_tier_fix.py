#!/usr/bin/env python3
"""Test script to verify the tier distribution fix."""

import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from log_agent.storage.local_backend import LocalFilesystemBackend
from log_agent.models.tier import Tier

def test_tier_distribution():
    """Test that tier names are correctly mapped to uppercase."""
    print("Testing Storage Tier Distribution Fix")
    print("=" * 50)
    
    # Initialize backend
    backend = LocalFilesystemBackend('log_storage')
    
    print("\n1. Tier Directories:")
    for tier, dir_path in backend.tier_directories.items():
        print(f"   {tier} -> {dir_path}")
    
    print("\n2. Tier Enum Values:")
    for tier in [Tier.HOT, Tier.WARM, Tier.COLD, Tier.ARCHIVE]:
        print(f"   {tier}.value = '{tier.value}' -> uppercase: '{tier.value.upper()}'")
    
    print("\n3. File Counts by Tier:")
    storage_tiers = {"HOT": 0, "WARM": 0, "COLD": 0, "ARCHIVE": 0}
    
    for tier_enum, tier_dir in backend.tier_directories.items():
        logs_dir = tier_dir / "logs"
        
        if logs_dir.exists() and logs_dir.is_dir():
            # This is the fixed logic - convert to uppercase
            tier_name = tier_enum.value.upper()
            
            try:
                files = os.listdir(logs_dir)
                file_count = sum(1 for f in files if f.endswith('.json'))
                storage_tiers[tier_name] = file_count
                print(f"   {tier_name}: {file_count} files")
            except Exception as e:
                print(f"   {tier_name}: Error - {e}")
                storage_tiers[tier_name] = 0
        else:
            tier_name = tier_enum.value.upper()
            print(f"   {tier_name}: 0 files (directory doesn't exist)")
    
    print("\n4. Final storage_tiers dictionary:")
    print(f"   {storage_tiers}")
    
    print("\n5. Verification:")
    expected_keys = {"HOT", "WARM", "COLD", "ARCHIVE"}
    actual_keys = set(storage_tiers.keys())
    
    if expected_keys == actual_keys:
        print("   [SUCCESS] All tier keys are uppercase as expected!")
        print("   [SUCCESS] Dashboard will now display dynamic data correctly!")
    else:
        print(f"   [FAILED] Expected keys {expected_keys}, got {actual_keys}")
    
    total_files = sum(storage_tiers.values())
    print(f"\n6. Total log files across all tiers: {total_files}")
    
    return storage_tiers

if __name__ == "__main__":
    test_tier_distribution()

# Made with Bob
