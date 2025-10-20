#!/usr/bin/env python3
"""
Quick test script to verify data loading with limited suits
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.performance_optimizer import optimizer
import pandas as pd

def quick_test():
    """Quick test with limited suits"""
    print("Quick Test - Loading 3 suits only...")
    print("=" * 50)
    
    try:
        # Test with only 3 suits for quick testing
        df = optimizer.get_hn_monitors_optimized(force_refresh=True, limit_suits=3)
        
        if df is None:
            print("ERROR: get_hn_monitors_optimized returned None")
            return False
            
        if df.empty:
            print("WARNING: DataFrame is empty")
            return False
        else:
            print(f"SUCCESS: Loaded {len(df)} rows")
            print(f"Columns: {list(df.columns)}")
            
            # Check for clients
            if 'Client' in df.columns:
                clients = df["Client"].dropna().unique()
                clients = [c for c in clients if str(c).strip() != ""]
                print(f"Clients found: {len(clients)}")
                if clients:
                    print(f"Sample clients: {clients[:3]}")
            else:
                print("WARNING: No 'Client' column found")
            
            return True
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        print(f"Full error: {traceback.format_exc()}")
        return False

if __name__ == "__main__":
    print("Quick Test - 3 Suits Only")
    print("=" * 30)
    
    success = quick_test()
    
    if success:
        print("\nQuick test PASSED!")
        print("The app should now work with limited data for testing.")
    else:
        print("\nQuick test FAILED!")
        print("Check the errors above.")
