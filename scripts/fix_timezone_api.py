#!/usr/bin/env python3
"""
Fix all datetime.now() calls in API files to use IST
"""

import os
import re

# API files that need fixing
api_files = [
    'backend/api/aggressive_mode.py',
    'backend/api/capital.py',
    'backend/api/dashboard.py',
    'backend/api/market_data.py',
    'backend/api/ml_strategy.py',
    'backend/api/settings.py',
    'backend/api/watchlist.py',
    'backend/api/websocket_manager.py',
    'backend/api/watchlist_performance.py'
]

base_path = '/Users/srbhandary/Documents/Projects/srb-algo'

for file_path in api_files:
    full_path = os.path.join(base_path, file_path)
    
    if not os.path.exists(full_path):
        print(f"⚠️  Skipping {file_path} (not found)")
        continue
    
    with open(full_path, 'r') as f:
        content = f.read()
    
    original_content = content
    
    # Add import if not present
    if 'from backend.core.timezone_utils import' not in content:
        # Find the imports section
        if 'from datetime import' in content:
            content = content.replace(
                'from datetime import',
                'from backend.core.timezone_utils import now_ist\nfrom datetime import',
                1
            )
        elif 'import datetime' in content:
            content = content.replace(
                'import datetime',
                'from backend.core.timezone_utils import now_ist\nimport datetime',
                1
            )
    
    # Replace datetime.now() with now_ist()
    content = re.sub(r'datetime\.now\(\)', 'now_ist()', content)
    
    # Replace __import__('datetime').datetime.now() with now_ist()
    content = re.sub(r"__import__\('datetime'\)\.datetime\.now\(\)", 'now_ist()', content)
    
    if content != original_content:
        with open(full_path, 'w') as f:
            f.write(content)
        print(f"✅ Fixed {file_path}")
    else:
        print(f"ℹ️  No changes needed in {file_path}")

print("\n✅ All API files processed")
