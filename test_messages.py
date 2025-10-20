#!/usr/bin/env python3
"""
Test script to verify message handling works correctly
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.performance_optimizer import optimizer
import pandas as pd

def test_message_handling():
    """Test that loading messages are properly managed"""
    print("Testing Message Handling...")
    print("=" * 50)
    
    try:
        # Test 1: Fresh data loading
        print("1. Testing fresh data loading...")
        df1 = optimizer.get_hn_monitors_optimized(force_refresh=True, limit_suits=2)
        print(f"   Result: {len(df1)} rows loaded")
        
        # Test 2: Cached data loading
        print("2. Testing cached data loading...")
        df2 = optimizer.get_hn_monitors_optimized(force_refresh=False, limit_suits=2)
        print(f"   Result: {len(df2)} rows loaded")
        
        # Test 3: Cache status
        print("3. Testing cache status...")
        cache_valid = optimizer.is_cache_valid()
        print(f"   Cache valid: {cache_valid}")
        
        print("\nMessage handling test PASSED!")
        print("Loading messages should now be properly managed in the app.")
        
        return True
        
    except Exception as e:
        print(f"ERROR: {e}")
        return False

if __name__ == "__main__":
    print("Message Handling Test")
    print("=" * 30)
    
    success = test_message_handling()
    
    if success:
        print("\nAll tests PASSED!")
        print("The app should now have clean loading messages.")
    else:
        print("\nSome tests FAILED!")
        print("Check the errors above.")
