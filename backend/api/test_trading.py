"""
Test Trading Controller - Manual trigger for testing all strategies
"""

from fastapi import APIRouter, HTTPException
from backend.core.logger import get_logger
import asyncio

logger = get_logger(__name__)
router = APIRouter(prefix="/api/test-trading", tags=["test-trading"])

# Global reference to trading system (will be set from main.py)
_trading_system = None

def set_trading_system(trading_system):
    """Set the trading system reference (called from main.py)"""
    global _trading_system
    _trading_system = trading_system

@router.post("/run-all-strategies")
async def run_all_strategies_test():
    """
    Manually trigger one SAC cycle to test all strategies
    This will generate test signals from all 6 strategies
    """
    try:
        logger.info("🧪 Manual test trigger - Running all strategies...")
        
        # Get trading system
        trading_system = _trading_system
        if not trading_system:
            raise HTTPException(status_code=500, detail="Trading system not available")
        
        # Get current market state
        market_state = await trading_system.market_data.get_current_state()
        if not market_state:
            raise HTTPException(status_code=500, detail="Market state not available")
        
        # Test all strategies (0-5)
        results = []
        for i in range(6):
            try:
                logger.info(f"🧪 Testing strategy {i}: {trading_system.strategy_zoo.strategies[i]['name']}")
                
                # Generate signals
                signals = await trading_system.strategy_zoo.generate_signals(i, market_state)
                
                # Score signals
                scored_signals = await trading_system.model_manager.score_signals(signals, market_state)
                
                # Filter signals
                top_signals = trading_system.filter_top_signals(scored_signals)
                
                results.append({
                    "strategy_index": i,
                    "strategy_name": trading_system.strategy_zoo.strategies[i]['name'],
                    "signals_generated": len(signals),
                    "signals_scored": len(scored_signals),
                    "top_signals": len(top_signals),
                    "status": "success"
                })
                
                logger.info(f"✅ Strategy {i}: {len(signals)} → {len(scored_signals)} → {len(top_signals)} signals")
                
            except Exception as e:
                logger.error(f"❌ Strategy {i} failed: {e}")
                results.append({
                    "strategy_index": i,
                    "strategy_name": trading_system.strategy_zoo.strategies[i]['name'] if i < len(trading_system.strategy_zoo.strategies) else "Unknown",
                    "signals_generated": 0,
                    "signals_scored": 0,
                    "top_signals": 0,
                    "status": f"failed: {str(e)}"
                })
        
        # Execute all top signals from all strategies
        total_executed = 0
        for result in results:
            if result["top_signals"] > 0:
                try:
                    # This would normally execute, but for test we'll just count
                    total_executed += result["top_signals"]
                    logger.info(f"🎯 Would execute {result['top_signals']} signals from {result['strategy_name']}")
                except Exception as e:
                    logger.error(f"❌ Execution failed for {result['strategy_name']}: {e}")
        
        return {
            "status": "success",
            "message": "Test cycle completed",
            "results": results,
            "total_strategies_tested": len(results),
            "total_signals_generated": sum(r["signals_generated"] for r in results),
            "total_signals_executed": total_executed,
            "market_state_available": market_state is not None
        }
        
    except Exception as e:
        logger.error(f"Failed to run strategy test: {e}")
        raise HTTPException(status_code=500, detail=f"Test failed: {str(e)}")

@router.post("/execute-test-signals")
async def execute_test_signals():
    """
    Execute the actual test signals (paper trading)
    """
    try:
        logger.info("🧪 Executing test signals...")
        
        trading_system = _trading_system
        if not trading_system:
            raise HTTPException(status_code=500, detail="Trading system not available")
        
        # Get current market state
        market_state = await trading_system.market_data.get_current_state()
        if not market_state:
            raise HTTPException(status_code=500, detail="Market state not available")
        
        executed_count = 0
        
        # Generate and execute signals from all strategies
        for i in range(6):
            try:
                # Generate signals
                signals = await trading_system.strategy_zoo.generate_signals(i, market_state)
                
                # Score signals
                scored_signals = await trading_system.model_manager.score_signals(signals, market_state)
                
                # Filter signals
                top_signals = trading_system.filter_top_signals(scored_signals)
                
                # Execute each signal
                for signal in top_signals:
                    # Bypass risk manager for test signals (marked with TEST_MODE metadata)
                    is_test_signal = (hasattr(signal, 'metadata') and 
                                    signal.metadata and 
                                    signal.metadata.get('TEST_MODE', False))
                    
                    if is_test_signal or trading_system.risk_manager.can_take_trade(signal):
                        logger.info(f"🧪 Executing test signal: {signal.strategy} {signal.symbol} {signal.strike} {signal.direction}")
                        
                        # Convert to dict for order manager
                        signal_dict = signal.to_dict() if hasattr(signal, 'to_dict') else signal
                        
                        # Execute signal
                        execution_success = await trading_system.order_manager.execute_signal(signal_dict)
                        
                        if execution_success:
                            executed_count += 1
                            logger.info(f"✅ Test signal executed successfully")
                        else:
                            logger.warning(f"❌ Test signal execution failed")
                    else:
                        logger.warning(f"⚠️ Risk manager rejected test signal")
                        
            except Exception as e:
                logger.error(f"❌ Failed to execute strategy {i}: {e}")
        
        return {
            "status": "success",
            "message": f"Test signals executed",
            "executed_count": executed_count,
            "note": "Check recent trades and positions for test results"
        }
        
    except Exception as e:
        logger.error(f"Failed to execute test signals: {e}")
        raise HTTPException(status_code=500, detail=f"Execution failed: {str(e)}")

@router.get("/test-status")
async def get_test_status():
    """
    Get current test mode status and results
    """
    try:
        trading_system = _trading_system
        
        # Check actual test mode from strategy_zoo_simple.py
        test_mode_enabled = False
        if trading_system and hasattr(trading_system, 'strategy_zoo'):
            # Import to check the actual TEST_MODE flag
            try:
                import importlib
                from meta_controller.strategy_zoo_simple import StrategyZoo
                # Read the file to check TEST_MODE value
                with open('/app/meta_controller/strategy_zoo_simple.py', 'r') as f:
                    content = f.read()
                    test_mode_enabled = 'TEST_MODE = True' in content
            except:
                test_mode_enabled = False
        
        return {
            "test_mode_enabled": test_mode_enabled,
            "trading_system_available": trading_system is not None,
            "sac_enabled": trading_system.sac_enabled if trading_system else False,
            "strategy_count": len(trading_system.strategy_zoo.strategies) if trading_system and hasattr(trading_system, 'strategy_zoo') else 0,
            "note": "Test mode is now DISABLED - Back to production mode" if not test_mode_enabled else "Test mode is active"
        }
        
    except Exception as e:
        logger.error(f"Failed to get test status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get test status: {str(e)}")
