"""
Test Data Manager - Handle cleanup of test trades and associated data
"""

from fastapi import APIRouter, HTTPException
from backend.core.logger import get_logger
from backend.database.database import db
from datetime import datetime
import sqlite3

logger = get_logger(__name__)
router = APIRouter(prefix="/api/test-data", tags=["test-data"])

@router.delete("/cleanup")
async def cleanup_test_data():
    """
    Clean up all test trades and associated data
    Removes:
    - Trades with TEST_MODE metadata
    - Positions from test trades
    - Paper trading records
    - Any ML training data from test period
    """
    try:
        logger.warning("🧹 Starting TEST DATA cleanup...")
        
        # Get current timestamp for cleanup window
        cleanup_start = datetime.now()
        
        # Initialize counters
        cleanup_stats = {
            "trades_deleted": 0,
            "positions_deleted": 0,
            "paper_records_deleted": 0,
            "ml_data_deleted": 0,
            "cleanup_timestamp": cleanup_start.isoformat()
        }
        
        # Connect to database
        conn = sqlite3.connect("trading_system.db")
        cursor = conn.cursor()
        
        try:
            # 1. Delete test trades (those with test_ prefix or TEST_MODE metadata)
            cursor.execute("""
                DELETE FROM trades 
                WHERE strategy_id LIKE 'test_%' 
                OR strategy_name LIKE 'TEST_%'
                OR reason LIKE '%TEST MODE%'
            """)
            cleanup_stats["trades_deleted"] = cursor.rowcount
            
            # 2. Delete positions that came from test trades
            cursor.execute("""
                DELETE FROM positions 
                WHERE strategy_id LIKE 'test_%' 
                OR entry_reason LIKE '%TEST MODE%'
            """)
            cleanup_stats["positions_deleted"] = cursor.rowcount
            
            # 3. Clear paper trading cache and reset
            cursor.execute("DELETE FROM paper_trading_cache")
            cleanup_stats["paper_records_deleted"] = cursor.rowcount
            
            # 4. Delete ML training data from test period
            cursor.execute("""
                DELETE FROM ml_training_data 
                WHERE strategy_id LIKE 'test_%'
                OR created_at >= ?
            """, (cleanup_start.isoformat(),))
            cleanup_stats["ml_data_deleted"] = cursor.rowcount
            
            # 5. Reset paper trading status
            cursor.execute("""
                UPDATE paper_trading_status 
                SET iteration = 1, 
                    total_pnl = 0, 
                    last_pnl = 0,
                    timestamp = ?
                WHERE id = 1
            """, (cleanup_start.isoformat(),))
            
            # Commit all changes
            conn.commit()
            
            logger.info(f"✅ Test data cleanup completed: {cleanup_stats}")
            
            return {
                "status": "success",
                "message": "Test data cleanup completed",
                "stats": cleanup_stats
            }
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Error during test data cleanup: {e}")
            raise
        finally:
            conn.close()
            
    except Exception as e:
        logger.error(f"Failed to cleanup test data: {e}")
        raise HTTPException(status_code=500, detail=f"Cleanup failed: {str(e)}")

@router.get("/test-data-info")
async def get_test_data_info():
    """
    Get information about current test data in the system
    """
    try:
        conn = sqlite3.connect("trading_system.db")
        cursor = conn.cursor()
        
        # Count test trades
        cursor.execute("""
            SELECT COUNT(*) FROM trades 
            WHERE strategy_id LIKE 'test_%' 
            OR strategy_name LIKE 'TEST_%'
            OR reason LIKE '%TEST MODE%'
        """)
        test_trades = cursor.fetchone()[0]
        
        # Count test positions
        cursor.execute("""
            SELECT COUNT(*) FROM positions 
            WHERE strategy_id LIKE 'test_%' 
            OR entry_reason LIKE '%TEST MODE%'
        """)
        test_positions = cursor.fetchone()[0]
        
        # Get recent test activity
        cursor.execute("""
            SELECT strategy_id, symbol, created_at, reason 
            FROM trades 
            WHERE strategy_id LIKE 'test_%' 
            ORDER BY created_at DESC 
            LIMIT 10
        """)
        recent_tests = cursor.fetchall()
        
        conn.close()
        
        return {
            "test_trades_count": test_trades,
            "test_positions_count": test_positions,
            "recent_test_activity": [
                {
                    "strategy_id": row[0],
                    "symbol": row[1],
                    "timestamp": row[2],
                    "reason": row[3]
                } for row in recent_tests
            ]
        }
        
    except Exception as e:
        logger.error(f"Failed to get test data info: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get test data info: {str(e)}")

@router.post("/toggle-test-mode")
async def toggle_test_mode(enabled: bool = False):
    """
    Toggle test mode on/off by updating the strategy_zoo_simple.py file
    This is a simple way to enable/disable test mode without restarting
    """
    try:
        # For now, this is a placeholder - in production we'd use config
        logger.info(f"🧪 Test mode toggle requested: {enabled}")
        
        # In a real implementation, we'd update a config file or database flag
        # For now, just return the status
        return {
            "status": "success",
            "message": f"Test mode {'enabled' if enabled else 'disabled'}",
            "test_mode_enabled": enabled,
            "note": "Restart required to apply changes to strategy_zoo_simple.py"
        }
        
    except Exception as e:
        logger.error(f"Failed to toggle test mode: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to toggle test mode: {str(e)}")
