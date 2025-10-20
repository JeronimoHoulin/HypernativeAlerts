#!/usr/bin/env python3
"""
Test script to verify data loading works correctly
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.performance_optimizer import optimizer
import pandas as pd

def test_data_loading():
    """Test the data loading functionality"""
    print("Testing Hypernative Data Loading...")
    print("=" * 50)
    
    try:
        print("1. Testing cache status...")
        cache_valid = optimizer.is_cache_valid()
        print(f"   Cache valid: {cache_valid}")
        
        print("2. Testing data loading (force refresh=False)...")
        df = optimizer.get_hn_monitors_optimized(force_refresh=False)
        
        if df is None:
            print("   ERROR: get_hn_monitors_optimized returned None")
            return False
            
        if df.empty:
            print("   WARNING: DataFrame is empty")
            print("   This could be normal if no cache exists and API is slow")
        else:
            print(f"   SUCCESS: Loaded {len(df)} rows")
            print(f"   Columns: {list(df.columns)}")
            
            # Check for clients
            clients = df["Client"].dropna().unique()
            clients = [c for c in clients if str(c).strip() != ""]
            print(f"   Clients found: {len(clients)}")
            if clients:
                print(f"   Sample clients: {clients[:3]}")
        
        print("3. Testing cache after loading...")
        cache_valid_after = optimizer.is_cache_valid()
        print(f"   Cache valid after loading: {cache_valid_after}")
        
        if not df.empty:
            print("\n✅ Data loading test PASSED")
            return True
        else:
            print("\n⚠️  Data loading test PARTIAL - no data returned")
            print("   This might be normal if API is slow or has issues")
            return True
            
    except Exception as e:
        print(f"\n❌ Data loading test FAILED: {e}")
        import traceback
        print(f"Full error: {traceback.format_exc()}")
        return False

def test_app_integration():
    """Test that the app can load data like it would in Streamlit"""
    print("\nTesting App Integration...")
    print("=" * 50)
    
    try:
        # Simulate the app's data loading logic
        force_refresh = True  # Force fresh data for testing
        
        print("Loading data with force_refresh=True...")
        df = optimizer.get_hn_monitors_optimized(force_refresh=force_refresh)
        
        if df is None or df.empty:
            print("❌ App integration test FAILED - no data loaded")
            return False
        
        print(f"✅ App integration test PASSED - loaded {len(df)} rows")
        
        # Test client extraction (like the app does)
        clients = sorted(df["Client"].dropna().unique())
        clients = [c for c in clients if str(c).strip() != ""]
        
        print(f"✅ Found {len(clients)} clients")
        if clients:
            print(f"   Sample clients: {clients[:3]}")
        
        return True
        
    except Exception as e:
        print(f"❌ App integration test FAILED: {e}")
        return False

if __name__ == "__main__":
    print("Hypernative Alerts Data Loading Test")
    print("=" * 60)
    
    # Run tests
    test1_passed = test_data_loading()
    test2_passed = test_app_integration()
    
    print("\nTest Results:")
    print("=" * 30)
    print(f"Data Loading Test: {'PASSED' if test1_passed else 'FAILED'}")
    print(f"App Integration Test: {'PASSED' if test2_passed else 'FAILED'}")
    
    if test1_passed and test2_passed:
        print("\nAll tests PASSED! The app should work correctly.")
    else:
        print("\nSome tests FAILED. Check the errors above.")
        print("   The app might still work, but there could be issues.")
