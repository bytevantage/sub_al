#!/usr/bin/env python3
"""
Fix time consistency across the entire system
Standardize all datetime.now() calls to use IST timezone
"""

import sys
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
logger = logging.getLogger(__name__)

# Add project path
sys.path.append('.')

def fix_time_consistency():
    """Fix time consistency across all Python files"""
    logger.info("🔧 FIXING TIME CONSISTENCY ACROSS SYSTEM")
    logger.info("=" * 60)
    
    # Files to fix
    files_to_fix = [
        'backend/backtest_runner.py',
        'backend/services/technical_indicators.py',
        'backend/services/position_persistence.py',
        'backend/logging/structured_logger.py',
        'backend/services/price_history_tracker.py',
        'backend/services/token_manager.py',
        'backend/data/market_feed.py',
        'backend/data/technical_indicators.py',
        'backend/main.py',
        'backend/data/iv_rank_calculator.py'
    ]
    
    fixes_applied = []
    
    for file_path in files_to_fix:
        full_path = Path(file_path)
        if not full_path.exists():
            logger.warning(f"⚠️ File not found: {file_path}")
            continue
        
        try:
            with open(full_path, 'r') as f:
                content = f.read()
            
            original_content = content
            
            # Fix imports - add timezone_utils import
            if 'from backend.core.timezone_utils import' not in content and 'datetime.now()' in content:
                # Add import after existing imports
                lines = content.split('\n')
                import_line = None
                for i, line in enumerate(lines):
                    if line.strip().startswith('from datetime import'):
                        import_line = i
                        break
                
                if import_line is not None:
                    lines.insert(import_line + 1, 'from backend.core.timezone_utils import now_ist')
                    content = '\n'.join(lines)
                    logger.info(f"✅ Added timezone import to {file_path}")
            
            # Replace datetime.now() with now_ist()
            if 'datetime.now()' in content:
                # Be careful not to replace in comments or strings
                import re
                # Replace datetime.now() calls (not in comments)
                pattern = r'(?<!#.*?)(datetime\.now\(\))'
                content = re.sub(pattern, 'now_ist()', content)
                
                # Count replacements
                replacements = original_content.count('datetime.now()') - content.count('datetime.now()')
                if replacements > 0:
                    logger.info(f"✅ Fixed {replacements} datetime.now() calls in {file_path}")
                    fixes_applied.append(f"{file_path}: {replacements} replacements")
            
            # Replace datetime.utcnow() with now_ist()
            if 'datetime.utcnow()' in content:
                content = content.replace('datetime.utcnow()', 'now_ist()')
                replacements = original_content.count('datetime.utcnow()') - content.count('datetime.utcnow()')
                if replacements > 0:
                    logger.info(f"✅ Fixed {replacements} datetime.utcnow() calls in {file_path}")
                    fixes_applied.append(f"{file_path}: {replacements} utcnow replacements")
            
            # Write back if changed
            if content != original_content:
                with open(full_path, 'w') as f:
                    f.write(content)
                logger.info(f"✅ Updated {file_path}")
            else:
                logger.info(f"ℹ️ No changes needed in {file_path}")
                
        except Exception as e:
            logger.error(f"❌ Error fixing {file_path}: {e}")
    
    logger.info("\n" + "=" * 60)
    logger.info("📋 TIME CONSISTENCY FIX SUMMARY:")
    for fix in fixes_applied:
        logger.info(f"  ✅ {fix}")
    
    logger.info(f"\n🎉 TOTAL FILES FIXED: {len(fixes_applied)}")
    logger.info("🔄 RESTART SYSTEM TO APPLY CHANGES")

if __name__ == "__main__":
    fix_time_consistency()
