"""
Simple Test - Just generate and log test signals
"""

from fastapi import APIRouter, HTTPException
from backend.core.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/test-simple", tags=["test-simple"])

# Global reference to trading system
_trading_system = None

def set_trading_system(trading_system):
    global _trading_system
    _trading_system = trading_system

@router.post("/generate-test-signals")
async def generate_test_signals():
    """
    Simply generate test signals and log them (no execution)
    """
    try:
        logger.info("🧪 Simple test - Generating test signals...")
        
        trading_system = _trading_system
        if not trading_system:
            raise HTTPException(status_code=500, detail="Trading system not available")
        
        # Get current market state
        market_state = await trading_system.market_data.get_current_state()
        if not market_state:
            raise HTTPException(status_code=500, detail="Market state not available")
        
        all_signals = []
        
        # Generate signals from all strategies
        for i in range(6):
            try:
                strategy_name = trading_system.strategy_zoo.strategies[i]['name']
                logger.info(f"🧪 Testing strategy {i}: {strategy_name}")
                
                # Generate signals
                signals = await trading_system.strategy_zoo.generate_signals(i, market_state)
                
                # Log signal details
                for signal in signals:
                    signal_info = {
                        "strategy_index": i,
                        "strategy_name": strategy_name,
                        "symbol": getattr(signal, 'symbol', 'Unknown'),
                        "strike": getattr(signal, 'strike', 'Unknown'),
                        "direction": getattr(signal, 'direction', 'Unknown'),
                        "action": getattr(signal, 'action', 'Unknown'),
                        "expiry": getattr(signal, 'expiry', 'Unknown'),
                        "entry_price": getattr(signal, 'entry_price', 'Unknown'),
                        "strength": getattr(signal, 'strength', 'Unknown'),
                        "is_test": (hasattr(signal, 'metadata') and 
                                  signal.metadata and 
                                  signal.metadata.get('TEST_MODE', False))
                    }
                    all_signals.append(signal_info)
                    
                    logger.info(f"🧪 SIGNAL: {signal_info}")
                
            except Exception as e:
                logger.error(f"❌ Failed to generate signals for strategy {i}: {e}")
        
        return {
            "status": "success",
            "message": f"Generated {len(all_signals)} test signals",
            "signals": all_signals,
            "test_signals_count": len([s for s in all_signals if s['is_test']])
        }
        
    except Exception as e:
        logger.error(f"Failed to generate test signals: {e}")
        raise HTTPException(status_code=500, detail=f"Test failed: {str(e)}")
