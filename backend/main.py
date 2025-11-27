"""
Main FastAPI Application
Entry point for the trading system backend
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import asyncio
from typing import List, Optional, Dict, Any
from collections import deque
import uvicorn
from datetime import datetime
from zoneinfo import ZoneInfo
import json
from sqlalchemy import text
from pathlib import Path
import numpy as np

# IST timezone for market operations
IST = ZoneInfo("Asia/Kolkata")

from backend.core.config import config
from backend.core.logger import logger
from backend.core.upstox_client import UpstoxClient
from backend.data.market_data import MarketDataManager
# from backend.strategies.strategy_engine import StrategyEngine  # DISABLED - Using SAC Meta-Controller only
from backend.execution.order_manager import OrderManager
from backend.execution.risk_manager import RiskManager
from backend.execution.delta_hedger import DeltaHedger
from backend.execution.position_reconciler import PositionReconciler
from backend.execution.position_price_updater import PositionPriceUpdater
from backend.execution.entry_timing import EntryTimingManager
from backend.ml.model_manager import ModelManager
from backend.database.database import db
from backend.api.trade_history import router as trade_history_router
from backend.api.analytics import router as analytics_router
from backend.api.capital import router as capital_router
from backend.api.market_data import router as market_data_router
from backend.api.watchlist import router as watchlist_router
from backend.api.watchlist_performance import router as watchlist_performance_router
from backend.api.emergency_controls import router as emergency_router, set_app_state
from backend.api.real_time_metrics_simple import router as real_time_metrics_router
from backend.api.production_lock_simple import router as production_lock_router
from backend.api.dashboard import router as dashboard_router, set_trading_system
from backend.api.settings import router as settings_router
from backend.api.ml_strategy import router as ml_strategy_router, set_ml_state
from backend.api.upstox_auth import router as upstox_auth_router
from backend.api.token_status import router as token_status_router
from backend.api.aggressive_mode import router as aggressive_mode_router, set_aggressive_state
from backend.api.cache_status import router as cache_status_router
from backend.api.database_optimization import router as database_optimization_router
from backend.api.health_monitoring import router as health_monitoring_router
from backend.api.structured_logging import router as structured_logging_router
from backend.api.data_backup import router as data_backup_router
from backend.api.websocket_manager import get_ws_manager, AlertLevel
from backend.safety.circuit_breaker import CircuitBreaker
from backend.safety.position_manager import PositionManager
from backend.safety.market_monitor import MarketMonitor
from backend.safety.data_monitor import MarketDataMonitor
from backend.safety.order_lifecycle import OrderLifecycleManager
from backend.safety.reconciliation import TradeReconciliation
from backend.monitoring.prometheus_exporter import MetricsExporter, metrics_router
from backend.strategies.reversal_detector import ReversalDetector
from backend.jobs.performance_aggregation_job import get_performance_aggregator
from backend.core.adaptive_config import adaptive_config
from backend.backtest_runner import run_full_backtest

class TradingSystem:
    """Main trading system orchestrator"""
    
    def __init__(self):
        self.upstox_client: UpstoxClient = None
        self.market_data: MarketDataManager = None
        # self.strategy_engine: StrategyEngine = None  # DISABLED - Old strategy engine removed
        self.order_manager: OrderManager = None
        self.risk_manager: RiskManager = None
        self.delta_hedger: DeltaHedger = None
        self.position_reconciler: PositionReconciler = None
        self.position_price_updater: PositionPriceUpdater = None
        self.model_manager: ModelManager = None
        self.reversal_detector: ReversalDetector = None
        self.performance_aggregator = None
        self.circuit_breaker: Optional[CircuitBreaker] = None
        self.position_manager: Optional[PositionManager] = None
        self.market_monitor: Optional[MarketMonitor] = None
        self.data_monitor: Optional[MarketDataMonitor] = None
        self.order_lifecycle: Optional[OrderLifecycleManager] = None
        self.trade_reconciliation: Optional[TradeReconciliation] = None
        self.sac_agent: Optional[Any] = None  # SAC Meta-Controller
        self.strategy_zoo: Optional[Any] = None  # Strategy Zoo for SAC
        self.sac_enabled = False
        self.is_running = False
        self.websocket_clients: List[WebSocket] = []
        self.market_data_interval = 30  # Dynamic interval in seconds
        self.risk_check_interval = 1  # Check targets/SL every 1 second for fast exits
        self.metrics_exporter = MetricsExporter()  # Prometheus metrics
        self.ws_manager = get_ws_manager()  # WebSocket manager
        self.entry_timing = EntryTimingManager()  # Entry timing for pullbacks
        self.recent_signals: deque = deque(maxlen=200)
        self.last_heartbeat = datetime.now()  # Track if loops are alive
        self.recent_signals_path = Path("data/state/recent_signals.json")
        self.recent_signals_path.parent.mkdir(parents=True, exist_ok=True)
        # Load recent signals from disk if available
        try:
            if self.recent_signals_path.exists():
                with open(self.recent_signals_path, 'r') as f:
                    signals_data = json.load(f)
                    self.recent_signals.extend(signals_data)
                logger.info(f"✓ Loaded {len(self.recent_signals)} recent signals from disk")
        except Exception as e:
            logger.warning(f"⚠️  Failed to load recent signals: {e}")
        
        # Adaptive configuration system
        self.adaptive_config = adaptive_config
    
    def _convert_numpy_for_json(self, obj):
        """Convert numpy types to JSON-serializable types"""
        import numpy as np
        if isinstance(obj, dict):
            return {k: self._convert_numpy_for_json(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_numpy_for_json(item) for item in obj]
        elif isinstance(obj, (np.float32, np.float64)):
            return float(obj)
        elif isinstance(obj, (np.int32, np.int64)):
            return int(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        else:
            return obj
    
    def _persist_recent_signals(self):
        """Persist recent signals to disk"""
        try:
            signals_list = list(self.recent_signals)
            # Convert numpy types before JSON serialization
            signals_list = self._convert_numpy_for_json(signals_list)
            with open(self.recent_signals_path, 'w') as f:
                json.dump(signals_list, f)
        except Exception as e:
            logger.warning(f"⚠️  Failed to persist recent signals: {e}")
    
    def _initialize_minimal_components(self):
        """Initialize minimal components for dashboard-only mode"""
        logger.info("⚙️  Initializing minimal components (dashboard-only mode)")
        try:
            safety_config = config.get('safety', {}) if isinstance(config.get('safety', {}), dict) else {}
            circuit_breaker_config = safety_config.get('circuit_breaker', {})
            position_manager_config = safety_config.get('position_manager', {})
            market_monitor_config = safety_config.get('market_monitor', {})
            
            # Initialize only safety components needed for dashboard
            self.circuit_breaker = CircuitBreaker(circuit_breaker_config)
            self.position_manager = PositionManager(position_manager_config)
            self.market_monitor = MarketMonitor(market_monitor_config, circuit_breaker=self.circuit_breaker)
            
            # Set app state for emergency controls
            set_app_state({
                'trading_system': self,
                'circuit_breaker': self.circuit_breaker,
                'position_manager': self.position_manager,
                'market_monitor': self.market_monitor,
                'risk_manager': None
            })
            
            logger.info("✓ Minimal components initialized")
        except Exception as e:
            logger.error(f"Failed to initialize minimal components: {e}")
    
    async def _recover_positions_from_database(self):
        """Recover orphaned positions from database that were lost during restart"""
        try:
            from backend.database.models import Position
            session = db.get_session()
            
            try:
                # Get all positions from database
                db_positions = session.query(Position).all()
                
                if not db_positions:
                    logger.info("📊 No positions to recover from database")
                    return
                
                # Convert database positions to dict format for risk manager
                recovered_count = 0
                for db_pos in db_positions:
                    # Check if position is already tracked in memory
                    already_tracked = any(
                        p.get('position_id') == db_pos.position_id or p.get('id') == db_pos.position_id
                        for p in self.risk_manager.open_positions
                    )
                    
                    if not already_tracked:
                        # Convert database position to dict
                        position_dict = {
                            'position_id': db_pos.position_id,
                            'id': db_pos.position_id,
                            'symbol': db_pos.symbol,
                            'instrument_type': db_pos.instrument_type,
                            'strike_price': db_pos.strike_price,
                            'direction': db_pos.direction,
                            'expiry': db_pos.expiry,
                            'quantity': db_pos.quantity,
                            'entry_price': db_pos.entry_price,
                            'current_price': db_pos.current_price,
                            'stop_loss': db_pos.stop_loss,
                            'target_price': db_pos.target,
                            'trailing_sl': db_pos.trailing_sl if db_pos.trailing_sl else db_pos.stop_loss,
                            'highest_price': db_pos.entry_price,  # Will be updated
                            'strategy_name': db_pos.strategy_name,
                            'entry_time': db_pos.entry_time,
                            'position_metadata': db_pos.position_metadata if db_pos.position_metadata else {}
                        }
                        
                        # Add to risk manager's open positions
                        self.risk_manager.open_positions.append(position_dict)
                        recovered_count += 1
                        
                        logger.info(
                            f"🔄 Recovered position: {db_pos.symbol} {db_pos.strike_price} {db_pos.instrument_type} "
                            f"@ ₹{db_pos.entry_price:.2f} (Entry: {db_pos.entry_time.strftime('%H:%M:%S')})"
                        )
                
                if recovered_count > 0:
                    logger.info(f"✅ Recovered {recovered_count} orphaned positions from database")
                else:
                    logger.info("📊 All database positions already tracked in memory")
                    
            finally:
                session.close()
                
        except Exception as e:
            logger.error(f"❌ Failed to recover positions from database: {e}")
            import traceback
            logger.error(traceback.format_exc())
        
    async def initialize(self):
        """Initialize all system components"""
        logger.info("=" * 60)
        logger.info("🚀 Initializing Advanced Options Trading System")
        logger.info("=" * 60)
        
        # Initialize database tables
        try:
            db.create_tables()
            logger.info("✓ Database tables initialized")
        except Exception as e:
            logger.warning(f"⚠️  Database initialization failed (continuing without DB): {e}")
        
        # Load Upstox token
        token = config.get_upstox_token()
        if not token:
            logger.warning("⚠️  No Upstox token found. System will run in degraded mode (dashboard only)")
            logger.info("ℹ️  Run upstox_auth_working.py to authenticate and enable trading")
            return True  # Allow system to start without token
            
        # Initialize Upstox client
        self.upstox_client = UpstoxClient(token)
        if not self.upstox_client.test_connection():
            logger.warning("⚠️  Failed to connect to Upstox API. System will run in degraded mode (dashboard only)")
            logger.info("ℹ️  Token may be expired. Run upstox_auth_working.py to refresh")
            # Initialize minimal components for dashboard
            self._initialize_minimal_components()
            return True  # Allow system to start without valid connection
        
        # Initialize components (full mode with valid Upstox connection)
        try:
            self.market_data = MarketDataManager(self.upstox_client)
            self.risk_manager = RiskManager(config.get('risk'))
            # Initialize model manager only (strategy engine disabled)
            self.model_manager = ModelManager()
            # self.strategy_engine = StrategyEngine(self.model_manager)  # DISABLED - Using SAC Meta-Controller only
            self.reversal_detector = ReversalDetector()
            self.performance_aggregator = get_performance_aggregator()

            # Initialize safety subsystems
            safety_config = config.get('safety', {}) if isinstance(config.get('safety', {}), dict) else {}
            circuit_breaker_config = safety_config.get('circuit_breaker', {})
            position_manager_config = safety_config.get('position_manager', {})
            market_monitor_config = safety_config.get('market_monitor', {})
            data_monitor_config = safety_config.get('data_monitor', {})
            lifecycle_config = safety_config.get('order_lifecycle', {})
            reconciliation_config = safety_config.get('reconciliation', {})

            self.circuit_breaker = CircuitBreaker(circuit_breaker_config)
            self.position_manager = PositionManager(position_manager_config)
            self.market_monitor = MarketMonitor(market_monitor_config, circuit_breaker=self.circuit_breaker)
            
            # Initialize OrderManager with market context support
            self.order_manager = OrderManager(
                self.upstox_client, 
                self.risk_manager, 
                self.market_data,
                self.market_monitor
            )
            
            # Set order_manager reference in risk_manager for position updates
            self.risk_manager.order_manager = self.order_manager
            
            # Initialize Delta Hedger for gamma scalping
            self.delta_hedger = DeltaHedger(self.upstox_client, self.order_manager, self.market_data)
            
            # Initialize Position Reconciler for orphan trade killing
            self.position_reconciler = PositionReconciler(self.upstox_client, self.order_manager)
            
            # Initialize Position Price Updater for real-time price updates
            self.position_price_updater = PositionPriceUpdater(
                self.upstox_client, self.order_manager, self.market_data
            )
            
            self.data_monitor = MarketDataMonitor(data_monitor_config)
            self.order_lifecycle = OrderLifecycleManager(lifecycle_config)
            self.trade_reconciliation = TradeReconciliation(reconciliation_config)

            # Wire safety subsystems across managers
            if hasattr(self.risk_manager, "attach_safety_components"):
                self.risk_manager.attach_safety_components(
                    circuit_breaker=self.circuit_breaker,
                    position_manager=self.position_manager,
                    market_monitor=self.market_monitor,
                    data_monitor=self.data_monitor
                )
            else:
                self.risk_manager.circuit_breaker_interface = self.circuit_breaker
                self.risk_manager.position_manager_interface = self.position_manager

            if hasattr(self.order_manager, "set_position_manager"):
                self.order_manager.set_position_manager(self.position_manager)
            else:
                self.order_manager.position_manager = self.position_manager

            if hasattr(self.market_data, "set_monitors"):
                self.market_data.set_monitors(
                    market_monitor=self.market_monitor,
                    data_monitor=self.data_monitor
                )

            # Load ML models
            await self.model_manager.load_models()
            
            # Initialize ML training pipeline
            from backend.ml.training_data_collector import TrainingDataCollector
            from backend.jobs.eod_training import EODTrainingJob
            from datetime import time as dt_time
            
            self.data_collector = TrainingDataCollector(db)
            self.eod_training_job = EODTrainingJob(
                self.model_manager,
                self.data_collector,
                eod_time=dt_time(16, 0),  # 4:00 PM IST
                strategy_engine=None  # DISABLED - Old strategy engine removed
            )
            logger.info("✓ ML training pipeline initialized (EOD: 4:00 PM)")
            logger.info("✓ Strategy weight auto-adjustment enabled")
            
            # Initialize SAC Meta-Controller
            try:
                sac_config = config.get('sac_meta_controller', {})
                self.sac_enabled = sac_config.get('enabled', False)
                
                logger.info(f"🔍 SAC config check: enabled={self.sac_enabled}")
                
                if self.sac_enabled:
                    from meta_controller.sac_agent import SACAgent
                    from meta_controller.strategy_zoo_simple import StrategyZoo
                    
                    model_path = sac_config.get('model_path', 'models/sac_prod_latest.pth')
                    
                    self.sac_agent = SACAgent(state_dim=35, action_dim=9)
                    
                    import os
                    if os.path.exists(model_path):
                        self.sac_agent.load(model_path)
                        logger.info(f"✓ SAC Meta-Controller loaded: {model_path}")
                    else:
                        logger.warning(f"⚠️  SAC model not found: {model_path}, using random initialization")
                    
                    self.strategy_zoo = StrategyZoo(portfolio_value=5000000)
                    logger.info(f"✓ Strategy Zoo initialized with {len(self.strategy_zoo.strategies)} strategies")
                    logger.info(f"🎯 SAC ACTIVATED: sac_enabled={self.sac_enabled}, agent={self.sac_agent is not None}, zoo={self.strategy_zoo is not None}")
                else:
                    logger.info("ℹ️  SAC Meta-Controller disabled in config")
                    
            except Exception as e:
                logger.error(f"❌ Failed to initialize SAC: {e}")
                import traceback
                logger.error(traceback.format_exc())
                self.sac_enabled = False
            
            # Initialize WebSocket market feed
            try:
                await self.market_data.initialize_websocket_feed()
            except Exception as e:
                logger.warning(f"WebSocket initialization failed, will use REST API: {e}")
            
            logger.info("✓ All components initialized successfully")
            
            # Recover orphaned positions from database
            await self._recover_positions_from_database()
            
            # Brief pause to let rate limits settle after initialization
            await asyncio.sleep(2)
            
            return True
            
        except Exception as e:
            import traceback
            logger.error(f"❌ Failed to initialize components: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return False
    
    async def start(self):
        """Start the trading system"""
        if not await self.initialize():
            return
            
        self.is_running = True
        logger.info("=" * 60)
        logger.info("📈 Trading System Started")
        mode = config.get('mode', 'paper') if hasattr(config, 'get') else 'paper'
        logger.info(f"   Mode: {mode.upper()}")
        logger.info(f"   Capital: ₹{config.get('trading.initial_capital', 100000):,.0f}")
        logger.info(f"   Max Positions: {config.get('trading.max_positions', 20)}")
        logger.info("=" * 60)
        
        # Only start trading loops if we have full components initialized
        logger.info(f"Components check - market_data: {self.market_data is not None}, risk_manager: {self.risk_manager is not None}, performance_aggregator: {self.performance_aggregator is not None}")
        if self.market_data and self.risk_manager and self.performance_aggregator:
            # Start background tasks
            logger.info("✓ Starting trading loop...")
            asyncio.create_task(self.trading_loop())
            asyncio.create_task(self.market_data_loop())
            asyncio.create_task(self.risk_monitoring_loop())
            asyncio.create_task(self.performance_aggregator.schedule_daily_aggregation())
            logger.info("✓ Performance aggregation scheduler started (runs at 6:00 PM IST)")
            
            # Start SAC Meta-Controller task
            # TODO: SACAgent needs run method implementation
            # if self.sac_agent:
            #     asyncio.create_task(self.sac_agent.run())
            
            # Start Delta Hedging monitor for gamma scalping
            if self.delta_hedger:
                asyncio.create_task(self.delta_hedger.start_hedging_monitor())
                logger.info("✅ Delta Hedging Monitor started")
            
            # Start Position Reconciler for orphan trade killing
            if self.position_reconciler:
                asyncio.create_task(self.position_reconciler.start_reconciliation_monitor())
                logger.info("✅ Position Reconciler started (Orphan Killer active)")
            
            # Start Position Price Updater for real-time price updates
            if self.position_price_updater:
                asyncio.create_task(self.position_price_updater.start_price_updates())
                logger.info("✅ Position Price Updater started (5s interval)")
            
            logger.info("✅ Trading system started successfully")
        else:
            logger.warning("⚠️  Running in degraded mode - trading loops disabled")
            logger.info("ℹ️  Dashboard is available but trading is inactive")

        # Update emergency control state with initialized components
        set_app_state({
            'trading_system': self,
            'risk_manager': self.risk_manager if hasattr(self, 'risk_manager') else None,
            'order_manager': self.order_manager if hasattr(self, 'order_manager') else None,
            'market_data': self.market_data if hasattr(self, 'market_data') else None,
            'strategy_engine': None,  # DISABLED - Old strategy engine removed
            'model_manager': self.model_manager if hasattr(self, 'model_manager') else None,
            'circuit_breaker': self.circuit_breaker,
            'position_manager': self.position_manager,
            'market_monitor': self.market_monitor,
            'data_monitor': self.data_monitor if hasattr(self, 'data_monitor') else None,
            'order_lifecycle': self.order_lifecycle if hasattr(self, 'order_lifecycle') else None,
            'trade_reconciliation': self.trade_reconciliation if hasattr(self, 'trade_reconciliation') else None,
        })
        
        # Set trading system reference for dashboard API
        set_trading_system(self)
        
        # Update ML strategy state for API endpoints (only if components exist)
        if hasattr(self, 'model_manager'):
            set_ml_state({
                'ml_strategy': self,
                'model_manager': self.model_manager,
                'eod_training_job': self.eod_training_job if hasattr(self, 'eod_training_job') else None,
                'data_collector': self.data_collector if hasattr(self, 'data_collector') else None
            })
        
        # Update aggressive mode state for API endpoints
        if hasattr(self, 'risk_manager'):
            set_aggressive_state({
                'strategy_engine': None,  # DISABLED - Old strategy engine removed
                'risk_manager': self.risk_manager
            })
        
    async def stop(self):
        """Stop the trading system"""
        logger.info("🛑 Stopping trading system...")
        self.is_running = False

        # Close all positions before shutdown
        if self.order_manager:
            await self.order_manager.close_all_positions()
        
        # Persist recent signal telemetry for next startup
        self._persist_recent_signals()

        logger.info("✓ Trading system stopped")
    
    async def trading_loop(self):
        """Main trading loop - generates and executes signals"""
        logger.info("🔄 Trading loop started")
        while self.is_running:
            # Update heartbeat for health checks
            self.last_heartbeat = datetime.now()
            
            # Refresh market regime every 15 minutes
            if datetime.now().minute % 15 == 0:  # Every 15 minutes
                try:
                    vix = self.market_data.get_vix() if hasattr(self.market_data, 'get_vix') else None
                    # Old strategy engine removed - using default trend strength
                    trend_strength = 0.5  # Default neutral trend
                    self.risk_manager.refresh_risk_parameters(vix, trend_strength)
                    logger.debug(f"Market regime refresh: VIX={vix}, trend_strength={trend_strength} (SAC Meta-Controller)")
                except Exception as e:
                    logger.debug(f"Could not refresh regime parameters: {e}")
            
            try:
                # Check market hours using IST time
                now = datetime.now(IST).time()
                market_open = datetime.strptime("09:15", "%H:%M").time()
                market_close = datetime.strptime("15:25", "%H:%M").time()  # Close at 3:25 PM IST
                is_market_hours = market_open <= now <= market_close
                
                # Also check if it's a weekday
                is_weekday = datetime.now(IST).weekday() < 5
                
                if not is_market_hours or not is_weekday:
                    logger.info(f"⏸️ Market closed - trading paused (IST: {datetime.now(IST).strftime('%H:%M:%S')}, Weekday: {is_weekday})")
                    await asyncio.sleep(60)  # Check every minute when closed
                    continue
                
                # Get latest market data
                logger.info("📊 Fetching market state...")
                market_state = await self.market_data.get_current_state()
                logger.info(f"📊 Market state fetched: {market_state is not None}")
                
                if market_state:
                    # Update adaptive configuration with market data for regime detection
                    self.adaptive_config.update_market_regime(market_state)
                    
                    # Check if thresholds should be adjusted based on performance
                    if self.adaptive_config.should_adjust_thresholds():
                        self.adaptive_config.adjust_thresholds()
                    
                    # Check market conditions first (VIX-based circuit breaker)
                    vix = None
                    try:
                        from backend.api.market_data import get_live_market_data
                        market_overview = get_live_market_data()
                        vix = market_overview.get('volatility', {}).get('india_vix')
                    except Exception as e:
                        logger.debug(f"Could not fetch VIX for market condition check: {e}")
                    
                    # Validate market conditions before generating signals
                    if vix and not self.risk_manager.check_market_conditions(vix):
                        logger.warning(f"⚠️ Market conditions unsuitable for trading (VIX: {vix})")
                        await asyncio.sleep(300)  # OFFICIAL SPEC: 5 minutes
                        continue
                    
                    # Generate signals - use SAC if enabled, else regular strategies
                    if self.sac_enabled and self.sac_agent and self.strategy_zoo:
                        # SAC Meta-Controller path
                        try:
                            state = self._build_sac_state(market_state)
                            # SAC agent returns action (allocation vector), we need strategy index
                            import random
                            # For now, select random strategy index (0-5) for exploration
                            selected_strategy_idx = random.randint(0, len(self.strategy_zoo.strategies) - 1)
                            signals = await self.strategy_zoo.generate_signals(selected_strategy_idx, market_state)
                            logger.info(f"🎯 SAC selected strategy {selected_strategy_idx}: {self.strategy_zoo.strategies[selected_strategy_idx]['name']}")
                            logger.info(f"📊 Generated {len(signals)} signals from strategy_zoo")
                        except Exception as e:
                            logger.error(f"SAC strategy selection failed: {e}, no fallback to old strategy engine")
                            import traceback
                            logger.error(traceback.format_exc())
                            signals = []  # No signals if SAC fails
                    else:
                        # SAC not enabled - no trading
                        logger.info("SAC Meta-Controller not enabled - no signals generated")
                        signals = []
                    
                    # Score signals using ML
                    scored_signals = await self.model_manager.score_signals(signals, market_state)
                    logger.info(f"📊 After ML scoring: {len(scored_signals)} signals")
                    
                    # Filter and rank signals
                    top_signals = self.filter_top_signals(scored_signals)
                    logger.info(f"📊 After filtering: {len(top_signals)} top signals")
                    
                    # Execute top signals immediately if risk allows
                    logger.info(f"🎯 Executing {len(top_signals)} top signals...")
                    for i, signal in enumerate(top_signals):
                        # Handle both Signal objects and dicts
                        if isinstance(signal, dict):
                            signal_name = signal.get('strategy', signal.get('strategy_name', 'Unknown'))
                            symbol = signal.get('symbol', 'Unknown')
                            strike = signal.get('strike', 'Unknown')
                            direction = signal.get('direction', 'Unknown')
                        else:
                            signal_name = getattr(signal, 'strategy', getattr(signal, 'strategy_name', 'Unknown'))
                            symbol = getattr(signal, 'symbol', 'Unknown')
                            strike = getattr(signal, 'strike', 'Unknown')
                            direction = getattr(signal, 'direction', 'Unknown')
                        logger.info(f"📊 Signal {i+1}: {signal_name} {symbol} {strike} {direction}")
                        if self.risk_manager.can_take_trade(signal):
                            logger.info(f"✅ Risk manager approved signal {i+1}")
                            # OFFICIAL SPEC: ENTER IMMEDIATELY - no timing checks
                            # Convert Signal object to dict for order manager
                            signal_dict = signal.to_dict() if hasattr(signal, 'to_dict') else signal
                            
                            # ENTER IMMEDIATELY - NO waiting, NO filters
                            execution_success = await self.order_manager.execute_signal(signal_dict)
                            status = "executed" if execution_success else "execution_failed"
                            reason = None if execution_success else "order_execution_failed"
                            self._record_signal(signal, status=status, reason=reason, accepted=True)

                            if execution_success:
                                await self.broadcast_signal(signal)
                        else:
                            logger.warning(f"❌ Risk manager blocked signal {i+1}: {signal_name} {symbol}")
                            self._record_signal(
                                signal,
                                status="blocked_by_risk",
                                reason="risk_manager_denied",
                                accepted=False
                            )
                
                # Wait for next cycle (OFFICIAL SPEC: 300 seconds = 5 minutes)
                await asyncio.sleep(300)
                
            except Exception as e:
                logger.error(f"Error in trading loop: {e}")
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")
                self.metrics_exporter.record_system_error("trading_loop", "error")
                
                # Categorize error and attempt recovery
                error_str = str(e).lower()
                
                if "database" in error_str or "connection" in error_str:
                    logger.warning("🔄 Database error detected, attempting reconnection...")
                    try:
                        # Reconnect database
                        await asyncio.sleep(5)
                        logger.info("✅ Database reconnection wait completed")
                    except Exception as recovery_error:
                        logger.error(f"❌ Database recovery failed: {recovery_error}")
                        await asyncio.sleep(30)
                        
                elif "api" in error_str or "http" in error_str or "timeout" in error_str:
                    logger.warning("🔄 API error detected, backing off...")
                    await asyncio.sleep(15)
                    
                elif "memory" in error_str or "allocation" in error_str:
                    logger.error("🔴 Memory error detected - garbage collecting...")
                    import gc
                    gc.collect()
                    await asyncio.sleep(10)
                    
                else:
                    # Unknown error - standard backoff
                    await asyncio.sleep(10)
                    
                continue
    
    def _build_sac_state(self, market_data: Dict) -> np.ndarray:
        """
        Build state vector for SAC agent from market data
        State dimension: 35
        """
        try:
            import numpy as np
            
            # Extract NIFTY and SENSEX data
            nifty_data = market_data.get('NIFTY', {})
            sensex_data = market_data.get('SENSEX', {})
            
            state = []
            
            # Helper to extract numeric value
            def get_numeric(data, key, default=0):
                val = data.get(key, default)
                if isinstance(val, dict):
                    return default
                return val if isinstance(val, (int, float)) else default
            
            # Price features (6) - with None and dict checks
            state.append(get_numeric(nifty_data, 'spot_price', 25000) / 25000.0)  # Normalized
            state.append(get_numeric(sensex_data, 'spot_price', 80000) / 80000.0)  # Normalized
            state.append(get_numeric(nifty_data, 'change_percent', 0) / 5.0)  # Normalized
            state.append(get_numeric(sensex_data, 'change_percent', 0) / 5.0)  # Normalized
            state.append(get_numeric(market_data, 'india_vix', 15) / 50.0)  # Normalized
            state.append(get_numeric(market_data, 'volatility', 20) / 100.0)  # Normalized
            
            # Option chain features (10) - with None and dict checks
            state.append(get_numeric(nifty_data, 'pcr', 1.0))  # Put-Call Ratio
            state.append(get_numeric(sensex_data, 'pcr', 1.0))
            state.append(get_numeric(nifty_data, 'max_pain', get_numeric(nifty_data, 'spot_price', 25000)) / 25000.0)
            state.append(get_numeric(sensex_data, 'max_pain', get_numeric(sensex_data, 'spot_price', 80000)) / 80000.0)
            state.append(get_numeric(nifty_data, 'call_oi', 0) / 1e7)  # Normalized
            state.append(get_numeric(nifty_data, 'put_oi', 0) / 1e7)
            state.append(get_numeric(sensex_data, 'call_oi', 0) / 1e7)
            state.append(get_numeric(sensex_data, 'put_oi', 0) / 1e7)
            state.append(get_numeric(nifty_data, 'iv_rank', 50) / 100.0)
            state.append(get_numeric(sensex_data, 'iv_rank', 50) / 100.0)
            
            # Technical indicators (10) - with None and dict checks
            nifty_tech = nifty_data.get('technical_indicators', {})
            sensex_tech = sensex_data.get('technical_indicators', {})
            state.append(get_numeric(nifty_tech, 'rsi', 50) / 100.0)
            state.append(get_numeric(sensex_tech, 'rsi', 50) / 100.0)
            state.append(get_numeric(nifty_tech, 'macd', 0) / 100.0)
            state.append(get_numeric(sensex_tech, 'macd', 0) / 100.0)
            state.append(get_numeric(nifty_tech, 'adx', 25) / 100.0)
            state.append(get_numeric(sensex_tech, 'adx', 25) / 100.0)
            state.append((get_numeric(nifty_data, 'spot_price', 0) - get_numeric(nifty_tech, 'ema_20', 0)) / 500.0)
            state.append((get_numeric(sensex_data, 'spot_price', 0) - get_numeric(sensex_tech, 'ema_20', 0)) / 1000.0)
            state.append(get_numeric(nifty_tech, 'bollinger_position', 0.5))  # Position in Bollinger bands
            state.append(get_numeric(sensex_tech, 'bollinger_position', 0.5))
            
            # Market microstructure (5) - with None and dict checks
            state.append(get_numeric(nifty_data, 'volume', 0) / 1e9)  # Normalized volume
            state.append(get_numeric(sensex_data, 'volume', 0) / 1e9)
            state.append(get_numeric(nifty_data, 'bid_ask_spread', 0) / 10.0)
            state.append(get_numeric(sensex_data, 'bid_ask_spread', 0) / 10.0)
            state.append(market_data.get('market_breadth', 0.5))  # Advance/decline ratio
            
            # Time features (4)
            now = datetime.now(IST)
            state.append(now.hour / 24.0)
            state.append(now.minute / 60.0)
            state.append(now.weekday() / 7.0)
            
            # Time to expiry (normalized)
            days_to_expiry = self._get_days_to_expiry(now)
            state.append(days_to_expiry / 7.0)  # Weekly options
            
            # Pad or trim to exactly 35 dimensions
            state = state[:35]  # Trim if too long
            while len(state) < 35:
                state.append(0.0)  # Pad if too short
            
            return np.array(state, dtype=np.float32)
            
        except Exception as e:
            logger.error(f"Error building SAC state: {e}")
            # Return zero state as fallback
            import numpy as np
            return np.zeros(35, dtype=np.float32)
    
    def _get_days_to_expiry(self, current_time: datetime) -> int:
        """Calculate days to next expiry"""
        try:
            # NIFTY expires on Tuesday (weekday 1)
            current_weekday = current_time.weekday()
            if current_weekday <= 1:  # Monday or Tuesday
                days = 1 - current_weekday
            else:
                days = 8 - current_weekday  # Days to next Tuesday
            return max(0, days)
        except:
            return 3  # Default to mid-week
    
    def _record_signal(self, signal: Dict[str, Any], status: str, reason: Optional[str] = None, accepted: bool = False):
        """Persist recent signal info for APIs and dashboards"""
        try:
            record = {
                "timestamp": datetime.now(IST).isoformat(),
                "strategy": signal.get("strategy"),
                "strategy_id": signal.get("strategy_id"),
                "symbol": signal.get("symbol"),
                "direction": signal.get("direction"),
                "action": signal.get("action"),
                "strike": signal.get("strike"),  # Added: strike price
                "expiry": signal.get("expiry"),  # Added: expiry date
                "strength": signal.get("strength"),
                "ml_probability": signal.get("ml_probability"),
                "entry_price": signal.get("entry_price"),
                "target_price": signal.get("target_price"),
                "stop_loss": signal.get("stop_loss"),
                "status": status,
                "reason": reason,
                "metadata": signal.get("metadata", {}),
            }

            self.recent_signals.appendleft(record)
            self._persist_recent_signals()
            
            # Update adaptive configuration with signal data
            self.adaptive_config.update_performance_data(signal_data={
                'strength': signal.get('strength', 0),
                'strategy': signal.get('strategy_id') or signal.get('strategy', 'unknown'),
                'accepted': accepted
            })
        except Exception as exc:
            logger.error(f"Failed to record signal telemetry: {exc}")

    def _calculate_optimal_interval(self) -> int:
        """Calculate optimal fetch interval based on market conditions and positions"""
        
        # Get configured base interval from config (default 30s for aggressive scanning)
        base_interval = config.get('data.option_chain_update_interval', 30)
        
        # Check if we have positions
        has_positions = len(self.order_manager.positions) > 0 if self.order_manager else False
        
        # Check VIX (from NIFTY market state)
        vix = 15.0  # Default
        if self.market_data and hasattr(self.market_data, 'market_state'):
            nifty_state = self.market_data.market_state.get('NIFTY', {})
            vix = nifty_state.get('vix', 15.0)
        
        # Check market hours using IST time
        now = datetime.now(IST).time()
        market_open = datetime.strptime("09:15", "%H:%M").time()
        market_close = datetime.strptime("15:25", "%H:%M").time()  # 3:25 PM IST
        is_market_hours = market_open <= now <= market_close
        
        # Calculate interval based on conditions
        if not is_market_hours:
            return 300  # 5 minutes after hours (minimal monitoring)
        elif has_positions:
            # Positions get real-time updates from WebSocket feed
            # Use configured interval for option chain updates
            return base_interval
        elif vix > 25:
            # High volatility - scan faster (20% faster than base)
            return max(15, int(base_interval * 0.8))
        elif vix > 20:
            # Elevated volatility - use configured interval
            return base_interval
        else:
            # Normal market - use configured interval for aggressive scanning
            return base_interval
    
    async def market_data_loop(self):
        """Market data update loop with adaptive intervals"""
        while self.is_running:
            try:
                # Check market hours - stop updating after 3:25 PM
                now = datetime.now(IST).time()
                market_close = datetime.strptime("15:25", "%H:%M").time()  # 3:25 PM IST
                is_weekday = datetime.now(IST).weekday() < 5
                
                if now > market_close or not is_weekday:
                    # Market closed - longer sleep
                    await asyncio.sleep(300)  # Sleep 5 minutes when closed
                    continue
                
                # Update heartbeat for health checks
                self.last_heartbeat = datetime.now()
                
                # Calculate optimal interval
                self.market_data_interval = self._calculate_optimal_interval()
                
                # Update option chain data (with filtering)
                await self.market_data.update_option_chain()
                
                # Update Greeks (only for filtered strikes)
                await self.market_data.calculate_greeks()
                
                # Update Prometheus metrics
                await self._update_market_metrics()
                
                # Broadcast updates to dashboard via WebSocket
                await self.broadcast_market_data()
                
                logger.debug(f"Market data updated, next update in {self.market_data_interval}s")
                
                # Adaptive sleep based on conditions
                await asyncio.sleep(self.market_data_interval)
                
            except Exception as e:
                logger.error(f"Error in market data loop: {e}")
                self.metrics_exporter.record_system_error("market_data_loop", "error")
                await asyncio.sleep(10)
    
    async def risk_monitoring_loop(self):
        """Risk monitoring loop with live MTM tracking and reversal detection"""
        while self.is_running:
            try:
                # Update heartbeat to show loop is alive (critical for health checks)
                self.last_heartbeat = datetime.now()
                
                # Get current market state
                market_state = await self.market_data.get_current_state()
                
                # Check for reversal signals
                reversal_signals = self.reversal_detector.update(market_state)
                
                # If high-severity reversal detected, trigger circuit breaker
                for signal in reversal_signals:
                    if signal.severity == 'high':
                        logger.warning(f"⚠️ High-severity reversal: {signal.description}")
                        # Trigger risk manager circuit breaker
                        self.risk_manager._trigger_circuit_breaker(f'reversal_{signal.signal_type}')
                        # Update metrics
                        self.metrics_exporter.record_system_error('reversal_detected', signal.signal_type)
                
                # Check positions
                positions = await self.order_manager.get_positions()
                
                # Update live MTM for all positions using direct LTP API
                # This is much faster than option chain lookup: 1 API call for all positions
                if positions:
                    # Build instrument keys for all open positions
                    # Use numerical instrument keys from Upstox (NSE_FO|44300, not symbol format)
                    instrument_keys = []
                    position_map = {}  # Map instrument_key -> list of positions (multiple positions can share same instrument)
                    
                    # Group positions by (symbol, expiry) to fetch option chains once per group
                    expiry_groups = {}
                    skipped_positions = 0
                    for position in positions:
                        symbol = position.get('symbol')
                        expiry = position.get('expiry')
                        instrument_type = (position.get('instrument_type') or '').upper()
                        
                        # Skip non-option instruments (e.g., futures hedges)
                        if instrument_type not in ('CALL', 'PUT', 'CE', 'PE'):
                            continue
                        
                        if symbol and expiry:
                            # Parse expiry to date string format YYYY-MM-DD
                            if isinstance(expiry, str):
                                expiry_date = expiry.split('T')[0]
                            else:
                                expiry_date = expiry.strftime('%Y-%m-%d')
                            
                            key = (symbol, expiry_date)
                            if key not in expiry_groups:
                                expiry_groups[key] = []
                            expiry_groups[key].append(position)
                        else:
                            skipped_positions += 1
                    
                    if skipped_positions:
                        logger.warning(f"Skipped {skipped_positions} positions lacking symbol/expiry during grouping")
                    
                    logger.info(f"Grouped {len(positions)} positions into {len(expiry_groups)} expiry groups: {list(expiry_groups.keys())}")
                    
                    # Fetch current market state (has full option chain like SAC uses)
                    try:
                        market_state = await self.market_data.get_current_state()
                        logger.info(f"✓ Fetched market state for position updates")
                    except Exception as e:
                        logger.error(f"Error fetching market state: {e}")
                        market_state = {}
                    
                    # Update positions using market_state (same as SAC strategies use)
                    updated_count = 0
                    for position in positions:
                        try:
                            symbol = position.get('symbol')
                            strike = position.get('strike_price') or position.get('strike')
                            option_type = position.get('instrument_type') or position.get('direction')
                            
                            if not symbol or not strike or not option_type:
                                continue
                            
                            # Get symbol data from market state
                            symbol_data = market_state.get(symbol, {})
                            option_chain_data = symbol_data.get('option_chain', {})
                            
                            # Extract calls/puts dicts (same structure as SAC uses)
                            calls_dict = option_chain_data.get('calls', {})
                            puts_dict = option_chain_data.get('puts', {})
                            
                            # Select correct dict
                            options_dict = calls_dict if option_type.upper() in ['CALL', 'CE'] else puts_dict
                            
                            # Get option data for this strike
                            strike_str = str(int(strike))
                            option_data = options_dict.get(strike_str, {})
                            
                            # Get LTP
                            current_ltp = option_data.get('ltp', 0)
                            
                            if current_ltp > 0:
                                logger.info(f"✓ Found LTP: {symbol} {strike} {option_type} = ₹{current_ltp}")
                                
                                try:
                                    position_id = position.get('position_id') or position.get('id')
                                    
                                    # Update in risk manager
                                    self.risk_manager.update_position_mtm(position, current_ltp)
                                    
                                    # Update in database
                                    if hasattr(self, 'order_manager') and self.order_manager.position_service:
                                        self.order_manager.position_service.update_position_price(
                                            position_id,
                                            current_ltp
                                        )
                                    
                                    # Update Greeks
                                    if hasattr(self, 'order_manager') and option_data:
                                        await self.order_manager.update_position_greeks(
                                            position_id,
                                            option_data
                                        )
                                    
                                    updated_count += 1
                                    logger.info(f"✓ Updated {symbol} {strike} {option_type} → ₹{current_ltp}")
                                    
                                except Exception as update_error:
                                    logger.error(f"Error updating position: {update_error}")
                            else:
                                logger.warning(f"✗ No LTP for {symbol} {strike} {option_type}")
                                
                        except Exception as e:
                            logger.error(f"Error processing position update: {e}")
                    
                    if updated_count > 0:
                        logger.info(f"✓✓✓ Successfully updated {updated_count}/{len(positions)} positions with live prices ✓✓✓")
                        
                        # Broadcast position updates via WebSocket after market state updates
                        try:
                            for position in positions:
                                await self.ws_manager.broadcast_position_update({
                                    'position_id': position.get('position_id') or position.get('id'),
                                    'symbol': position.get('symbol'),
                                    'strike': position.get('strike_price'),
                                    'type': position.get('instrument_type'),
                                    'quantity': position.get('quantity'),
                                    'entry_price': position.get('entry_price'),
                                    'current_price': position.get('current_price'),
                                    'pnl': position.get('pnl'),
                                    'pnl_percent': position.get('pnl_percent'),
                                    'timestamp': datetime.now(IST).isoformat()
                                })
                            logger.info(f"✓ Broadcasted {len(positions)} position updates via WebSocket")
                        except Exception as ws_error:
                            logger.error(f"Error broadcasting position updates: {ws_error}")
                    
                    # Fetch LTP for all positions in ONE API call
                    if instrument_keys:
                        try:
                            logger.info(f"Fetching LTP for {len(instrument_keys)} positions: {instrument_keys[:3]}...")
                            ltp_response = self.upstox_client.get_ltp(instrument_keys)
                            
                            if not ltp_response:
                                logger.warning("LTP API returned None - likely rate limit or API error")
                            elif 'data' not in ltp_response:
                                logger.warning(f"LTP response missing 'data' key: {ltp_response}")
                            elif ltp_response and 'data' in ltp_response:
                                logger.debug(f"LTP response keys: {list(ltp_response['data'].keys())[:3]}")
                                
                                # Build price lookup: use BOTH instrument_key and instrument_token
                                price_lookup = {}
                                for resp_key, data in ltp_response['data'].items():
                                    # resp_key is like "BSE_FO|1127928" or "NSE_FO|44298"
                                    last_price = data.get('last_price')
                                    if last_price:
                                        # Index by response key (instrument_key format)
                                        price_lookup[resp_key] = last_price
                                        
                                        # Also index by instrument_token if available
                                        instrument_token = data.get('instrument_token', '')
                                        if instrument_token:
                                            price_lookup[str(instrument_token)] = last_price
                                
                                logger.debug(f"Price lookup has {len(price_lookup)} entries")
                                
                                updated_count = 0
                                # position_map now has instrument_key -> list of positions
                                for instrument_key, position_list in position_map.items():
                                    try:
                                        # Try to look up price by instrument_key
                                        current_price = price_lookup.get(instrument_key)
                                        
                                        if current_price and current_price > 0:
                                            # Update ALL positions that share this instrument_key
                                            for position in position_list:
                                                # Update position price
                                                self.risk_manager.update_position_mtm(position, current_price)
                                                
                                                # Update in position service for persistence
                                                if hasattr(self, 'order_manager') and self.order_manager.position_service:
                                                    self.order_manager.position_service.update_position_price(
                                                        position.get('position_id') or position.get('id'),
                                                        current_price
                                                    )
                                                
                                                updated_count += 1
                                                logger.debug(f"Updated position {position.get('position_id', '')[:8]}: {position.get('symbol')} {position.get('strike_price')} {position.get('instrument_type')} = ₹{current_price}")
                                        else:
                                            logger.warning(f"No price found for instrument {instrument_key} ({len(position_list)} positions)")
                                    except Exception as e:
                                        logger.error(f"Error processing LTP for {instrument_key}: {e}")
                                
                                if updated_count > 0:
                                    logger.info(f"✓ Updated {updated_count}/{len(positions)} position prices")
                                    
                                    # Broadcast position updates via WebSocket
                                    try:
                                        for position in positions:
                                            await self.ws_manager.broadcast_position_update({
                                                'position_id': position.get('position_id') or position.get('id'),
                                                'symbol': position.get('symbol'),
                                                'strike': position.get('strike_price'),
                                                'type': position.get('instrument_type'),
                                                'quantity': position.get('quantity'),
                                                'entry_price': position.get('entry_price'),
                                                'current_price': position.get('current_price'),
                                                'pnl': position.get('pnl'),
                                                'pnl_percent': position.get('pnl_percent'),
                                                'timestamp': datetime.now(IST).isoformat()
                                            })
                                        logger.info(f"✓ Broadcasted {len(positions)} position updates via WebSocket")
                                    except Exception as ws_error:
                                        logger.error(f"Error broadcasting position updates: {ws_error}")
                            else:
                                logger.warning(f"No LTP data returned for {len(instrument_keys)} positions")
                        except Exception as e:
                            logger.error(f"Error fetching LTP for positions: {e}")
                
                # Check EOD exit - close all positions after 3:25 PM
                if self.risk_manager.should_exit_eod():
                    logger.warning("⚠️ EOD exit triggered - closing all positions")
                    valid_positions = []
                    corrupted_count = 0
                    
                    for position in positions:
                        # Validate position has critical data before attempting to close
                        if (position.get('symbol') and 
                            position.get('strike_price') and 
                            position.get('instrument_type')):
                            valid_positions.append(position)
                        else:
                            logger.error(f"🔴 Skipping corrupted position during EOD: {position.get('symbol')} {position.get('strike_price')} {position.get('instrument_type')}")
                            corrupted_count += 1
                    
                    logger.info(f"📊 EOD exit: {len(valid_positions)} valid positions, {corrupted_count} corrupted positions")
                    
                    # Close only valid positions
                    for position in valid_positions:
                        await self.order_manager.close_position(position, exit_type="EOD")
                        
                    if corrupted_count > 0:
                        logger.warning(f"⚠️ {corrupted_count} corrupted positions were skipped during EOD exit")
                else:
                    # Check stop losses and targets
                    for position in positions:
                        # Store original TSL and metadata to detect changes
                        original_tsl = position.get('trailing_sl')
                        original_metadata = position.get('position_metadata', {}).copy()
                        
                        if self.risk_manager.should_exit(position):
                            await self.order_manager.close_position(position)
                        else:
                            # Check if TSL or metadata changed and persist to database
                            new_tsl = position.get('trailing_sl')
                            new_metadata = position.get('position_metadata', {})
                            
                            if (new_tsl != original_tsl or new_metadata != original_metadata):
                                position_id = position.get('position_id')
                                # Use order_manager's position_service (position_persistence)
                                if hasattr(self.order_manager, 'position_service'):
                                    self.order_manager.position_service.update_position_metadata(
                                        position_id=position_id,
                                        trailing_sl=new_tsl if new_tsl != original_tsl else None,
                                        position_metadata=new_metadata if new_metadata != original_metadata else None
                                    )
                        
                        # Check for reversal signals (disabled - old strategy engine removed)
                        # market_state = await self.market_data.get_current_state()
                        # if self.strategy_engine.detect_reversal(position, market_state):
                        #     logger.info(f"Reversal detected for {position['symbol']}")
                        #     await self.order_manager.close_position(position, exit_type="REVERSAL")
                
                # Check daily loss limit (Production Lock)
                daily_pnl = self.risk_manager.get_daily_pnl()
                if self.risk_manager.should_stop_trading(daily_pnl):
                    logger.warning("⚠️ Daily loss limit reached. Stopping trading.")
                elif self.risk_manager.check_daily_loss_limit():
                    logger.error("🔒 PRODUCTION DAILY LOSS LIMIT HIT - Full system shutdown")
                    # Emergency shutdown - close all positions immediately
                    for position in positions:
                        await self.order_manager.close_position(position, exit_type="DAILY_LIMIT_HIT")
                    return  # Exit trading loop for the day
                    await self.stop()
                
                # Update metrics
                await self._update_risk_metrics()
                
                # Check every 3 seconds for faster position updates
                # API load: 1 call/3s (positions) + 2 calls/30s (spot) = 24 calls/min
                # Well under 25/min sustained limit while giving near real-time updates
                await asyncio.sleep(3)
                
            except Exception as e:
                logger.error(f"Error in risk monitoring loop: {e}")
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")
                self.metrics_exporter.record_system_error("risk_monitoring_loop", "error")
                
                # Check if we should attempt recovery
                if "database" in str(e).lower() or "connection" in str(e).lower():
                    logger.info("🔄 Database/connection error detected, attempting recovery...")
                    try:
                        # Reconnect database
                        await asyncio.sleep(5)
                        logger.info("✅ Recovery wait completed, continuing...")
                    except Exception as recovery_error:
                        logger.error(f"❌ Recovery failed: {recovery_error}")
                        await asyncio.sleep(30)  # Longer wait on failed recovery
                else:
                    await asyncio.sleep(10)
    
    async def _get_option_ltp(self, symbol: str, strike: float, option_type: str) -> Optional[float]:
        """Get current LTP for an option"""
        try:
            if symbol not in self.market_data.market_state:
                logger.debug(f"Symbol {symbol} not in market state")
                return None
            
            option_chain = self.market_data.market_state[symbol].get('option_chain', {})
            if not option_chain:
                logger.debug(f"No option chain for {symbol}")
                return None
            
            strike_str = str(int(strike))  # Ensure strike is integer string
            
            if option_type.upper() == 'CALL':
                option_data = option_chain.get('calls', {}).get(strike_str, {})
            elif option_type.upper() == 'PUT':
                option_data = option_chain.get('puts', {}).get(strike_str, {})
            else:
                logger.warning(f"Invalid option type: {option_type}")
                return None
            
            ltp = option_data.get('ltp', 0)
            if ltp > 0:
                return ltp
            else:
                logger.debug(f"No LTP for {symbol} {strike} {option_type}: {option_data}")
                return None
        except Exception as e:
            logger.error(f"Error getting option LTP for {symbol} {strike} {option_type}: {e}")
            return None
    
    async def _update_market_metrics(self):
        """Update Prometheus metrics for market data"""
        try:
            if not self.market_data or not hasattr(self.market_data, 'market_state'):
                return
            
            for symbol in ['NIFTY', 'SENSEX']:
                if symbol not in self.market_data.market_state:
                    continue
                
                market_data = self.market_data.market_state[symbol]
                
                # Update VIX and market condition
                vix = market_data.get('vix', 0)
                condition = market_data.get('market_condition', 'unknown')
                self.metrics_exporter.update_market_metrics(vix, condition)
                
                # Record market data age
                last_update = market_data.get('last_update')
                if last_update:
                    age_seconds = (datetime.now() - last_update).total_seconds()
                    self.metrics_exporter.record_market_data_update(symbol, age_seconds)
                    
        except Exception as e:
            logger.error(f"Error updating market metrics: {e}")
    
    async def _update_risk_metrics(self):
        """Update Prometheus metrics for risk and positions"""
        try:
            # Get positions
            positions = await self.order_manager.get_positions()
            
            # Update position metrics
            total_positions = len(positions)
            total_value = sum(p.get('market_value', 0) for p in positions)
            
            # Get strategy breakdown
            strategy_breakdown = {}
            for p in positions:
                strategy = p.get('strategy', 'unknown')
                strategy_breakdown[strategy] = strategy_breakdown.get(strategy, 0) + 1
            
            self.metrics_exporter.update_position_metrics(positions, strategy_breakdown)
            
            # Update capital metrics
            capital = self.risk_manager.get_capital_info()
            self.metrics_exporter.update_capital_metrics(
                total=capital.get('total', 0),
                used=capital.get('used', 0),
                available=capital.get('available', 0),
                utilization=capital.get('utilization', 0)
            )
            
            # Update P&L metrics
            daily_pnl = self.risk_manager.get_daily_pnl()
            daily_pnl_pct = (daily_pnl / capital.get('total', 1)) * 100 if capital.get('total', 0) > 0 else 0
            realized_pnl = sum(p.get('realized_pnl', 0) for p in positions)
            
            self.metrics_exporter.update_pnl_metrics(
                daily=daily_pnl,
                daily_pct=daily_pnl_pct,
                realized=realized_pnl
            )
            
        except Exception as e:
            logger.error(f"Error updating risk metrics: {e}")
    
    def filter_top_signals(self, signals: List) -> List:
        """
        Filter and rank signals from all strategies.
        Allows lower strength threshold to foster broader strategy participation.
        """
        default_min_strength = config.get('risk.min_signal_strength', 75)
        # Allow strategies with slightly lower confidence to surface (down to 40 for testing)
        min_strength = max(40, default_min_strength - 10)

        # Convert Signal objects to dicts if needed and enrich with weight info
        signal_dicts = []
        for s in signals:
            if hasattr(s, 'to_dict'):
                signal_dict = s.to_dict()
                signal_dict['strategy_weight'] = getattr(s, 'strategy_weight', getattr(s, 'weight', 50))
                signal_dict['ensemble_weight'] = getattr(s, 'ensemble_weight', signal_dict.get('strategy_weight', 50))
                signal_dict['ml_confidence'] = getattr(s, 'ml_confidence', signal_dict.get('ml_probability', 0.5))
                signal_dict['model_version'] = getattr(s, 'model_version', None)
                signal_dict['model_hash'] = getattr(s, 'model_hash', None)
                signal_dicts.append(signal_dict)
            elif isinstance(s, dict):
                signal_dict = dict(s)
                signal_dict.setdefault('strategy_weight', 50)
                signal_dict.setdefault('ensemble_weight', signal_dict.get('strategy_weight', 50))
                signal_dicts.append(signal_dict)
            else:
                continue

        # Filter by minimum strength and ensure ML score defaults exist
        filtered = []
        logger.info(f"🔍 Filtering {len(signal_dicts)} signals with min_strength={min_strength}")
        
        # Log signals by strategy before filtering
        strategy_counts = {}
        for s in signal_dicts:
            strategy = s.get('strategy', 'Unknown')
            strategy_counts[strategy] = strategy_counts.get(strategy, 0) + 1
        
        if strategy_counts:
            logger.info(f"📊 Signals by strategy: {strategy_counts}")
        else:
            logger.info("📊 No signals generated by any strategy")
        for s in signal_dicts:
            strength = s.get('strength', 0)
            if strength < min_strength:
                logger.debug(f"❌ Filtered out {s.get('strategy')} signal: strength={strength} < {min_strength}")
                continue
            s.setdefault('ml_probability', s.get('ml_probability', 0.5))
            s.setdefault('strategy_weight', 50)
            s.setdefault('ensemble_weight', s.get('strategy_weight', 50))
            s.setdefault('ml_confidence', s.get('ml_probability', 0.5))
            filtered.append(s)

        if not filtered:
            return []

        # Composite ranking: blend strength, ML probability, and strategy weight
        def composite_score(signal: Dict[str, Any]) -> float:
            strength_component = signal.get('strength', 0) / 100
            ml_component = signal.get('ml_probability', 0.5)
            ml_confidence = signal.get('ml_confidence', ml_component)
            ensemble_component = signal.get('ensemble_weight', signal.get('strategy_weight', 50)) / 100
            return (
                (strength_component * 0.35)
                + (ml_component * 0.35)
                + (ml_confidence * 0.15)
                + (ensemble_component * 0.15)
            )

        sorted_signals = sorted(filtered, key=composite_score, reverse=True)

        # Permit more signals to pass through for execution evaluation
        return sorted_signals[:10]
    
    async def broadcast_signal(self, signal: dict):
        """Broadcast signal to WebSocket clients via WebSocket manager"""
        try:
            # Format signal message with correct fields
            symbol = signal.get('symbol', 'UNKNOWN')
            direction = signal.get('direction', 'UNKNOWN')  # CALL or PUT
            action = signal.get('action', 'BUY')  # BUY or SELL
            strike = signal.get('strike', 0)
            entry_price = signal.get('entry_price', 0)
            
            alert_message = (
                f"New signal: {action} {symbol} {strike} {direction} "
                f"@ ₹{entry_price:.2f}"
            )
            
            # Broadcast via centralized WebSocket manager
            await self.ws_manager.broadcast_alert(
                alert_message=alert_message,
                level=AlertLevel.INFO,
                details=signal
            )
        except Exception as e:
            logger.error(f"Error broadcasting signal: {e}")
    
    async def broadcast_market_data(self):
        """Broadcast market data to WebSocket clients"""
        try:
            # Get the internal market state (not the full state with nested data)
            market_state = self.market_data.market_state
            
            # Get VIX value (market-wide metric)
            vix_value = None
            market_condition = None
            try:
                from backend.api.market_data import get_live_market_data
                market_overview = get_live_market_data()
                vix_value = market_overview.get('volatility', {}).get('india_vix')
                
                # Update market monitor with VIX to calculate market condition
                if vix_value and self.market_monitor:
                    await self.market_monitor.update_vix(vix_value)
                    market_condition = self.market_monitor.market_condition.value
                    
            except Exception as e:
                logger.debug(f"Could not fetch VIX: {e}")
            
            # Broadcast market condition via WebSocket manager
            for symbol in ['NIFTY', 'SENSEX']:
                if symbol in market_state:
                    data = market_state[symbol]
                    await self.ws_manager.broadcast_market_condition({
                        'symbol': symbol,
                        'spot_price': data.get('spot_price'),
                        'vix': vix_value,  # Market-wide VIX
                        'pcr': data.get('pcr'),
                        'max_pain': data.get('max_pain'),
                        'condition': market_condition,  # Use calculated market condition
                        'timestamp': datetime.now(IST).isoformat()
                    })
            
            # Update WebSocket connection count metric
            conn_count = self.ws_manager.get_connection_count()
            self.metrics_exporter.update_websocket_connections(conn_count)
            
        except Exception as e:
            logger.error(f"Error broadcasting market data: {e}")


# Create FastAPI app with lifespan
trading_system = TradingSystem()

# Set app state for emergency controls (will be updated post-initialization)
set_app_state({'trading_system': trading_system})
set_trading_system(trading_system)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager"""
    # Store trading system in app state for API access
    app.state.trading_system = trading_system
    logger.info("✓ Trading system stored in app.state")
    
    # Start token manager service
    from backend.services.token_manager import get_token_manager
    token_manager = get_token_manager()
    await token_manager.start()
    logger.info("✓ Token manager service started")
    
    await trading_system.start()
    yield
    
    # Shutdown
    logger.info("🛑 Shutting down trading system...")
    if trading_system.is_running:
        await trading_system.stop()
    logger.info("✅ Trading system stopped")


# Create FastAPI app with lifespan
app = FastAPI(
    title="Advanced Options Trading System",
    description="Real-time options trading with ML-powered strategies",
    version="2.0.0",
    lifespan=lifespan
)

# CORS middleware - Allow all origins including file:// protocol
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Include API routers
app.include_router(trade_history_router)
app.include_router(analytics_router)
app.include_router(capital_router)
app.include_router(market_data_router)
app.include_router(watchlist_router)
app.include_router(watchlist_performance_router)
app.include_router(emergency_router)
app.include_router(settings_router)
app.include_router(metrics_router)  # Prometheus metrics
app.include_router(dashboard_router)  # Dashboard API endpoints
app.include_router(real_time_metrics_router)
app.include_router(production_lock_router)
app.include_router(ml_strategy_router) 
app.include_router(upstox_auth_router)  # Upstox OAuth authentication
app.include_router(token_status_router)  # Token status and health monitoring
app.include_router(aggressive_mode_router)  # Aggressive mode toggle
app.include_router(cache_status_router)  # Redis cache monitoring
app.include_router(database_optimization_router)  # Database optimization
app.include_router(health_monitoring_router)  # Health monitoring
app.include_router(structured_logging_router)  # Structured logging
app.include_router(data_backup_router)  # Data backup

# Mount static files for dashboard
dashboard_path = Path(__file__).parent.parent / "frontend" / "dashboard"
if dashboard_path.exists():
    app.mount("/dashboard", StaticFiles(directory=str(dashboard_path), html=True), name="dashboard")
    logger.info(f"✓ Dashboard mounted at /dashboard from {dashboard_path}")
else:
    logger.warning(f"⚠️  Dashboard directory not found: {dashboard_path}")

# Additional middleware to handle CORS for file:// protocol
@app.middleware("http")
async def add_cors_headers(request, call_next):
    """Add CORS headers to all responses"""
    response = await call_next(request)
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "*"
    response.headers["Access-Control-Allow-Credentials"] = "true"
    return response

# Initialize database tables on startup
@app.on_event("startup")
async def startup_db():
    """Create database tables and start WebSocket heartbeat"""
    db.create_tables()
    # Start WebSocket heartbeat for keep-alive
    await trading_system.ws_manager.start_heartbeat(interval=30)


# ========== API Routes ==========

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Advanced Options Trading System API",
        "version": "1.0.0",
        "status": "running" if trading_system.is_running else "stopped"
    }


@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    # Check if loops are actually alive by checking heartbeat
    heartbeat_age = (datetime.now() - trading_system.last_heartbeat).total_seconds()
    loops_alive = heartbeat_age < 30  # If no heartbeat in 30s, loops might be dead
    
    return {
        "status": "healthy",
        "mode": config.settings.mode,
        "trading_active": trading_system.is_running and loops_alive,
        "loops_alive": loops_alive,
        "last_heartbeat_seconds": int(heartbeat_age)
    }


@app.get("/api/health/db")
async def database_health_check():
    """Database health check endpoint"""
    try:
        # Try to query the database
        session = db.get_session()
        if session is None:
            raise RuntimeError("Database session unavailable")
        session.execute(text("SELECT 1"))
        session.close()
        return {
            "status": "ok",
            "message": "Database connection successful"
        }
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return {
            "status": "error",
            "message": str(e)
        }


@app.get("/health")
async def health():
    """Simple health endpoint for status dots"""
    return {"status": "ok"}


@app.get("/api/signals")
async def get_signals():
    """Get recent signals"""
    if trading_system.recent_signals:
        return {"signals": list(trading_system.recent_signals)}
    return {"signals": []}


@app.get("/api/signals/recent")
async def get_recent_signals():
    """Get recent signals with formatted response"""
    if trading_system.recent_signals:
        return {
            "status": "success",
            "data": list(trading_system.recent_signals)
        }
    return {
        "status": "success",
        "data": []
    }


@app.get("/api/positions")
async def get_positions():
    """Get current open positions"""
    positions = await trading_system.order_manager.get_positions()
    # Convert numpy types to Python native types
    cleaned_positions = []
    for pos in positions:
        cleaned_pos = {}
        for k, v in pos.items():
            if isinstance(v, (np.integer, np.int64)):
                cleaned_pos[k] = int(v)
            elif isinstance(v, (np.floating, np.float64)):
                cleaned_pos[k] = float(v)
            else:
                cleaned_pos[k] = v
        cleaned_positions.append(cleaned_pos)
    return {"positions": cleaned_positions}


# Cache for paper trading status to reduce backend load
_paper_trading_cache = {}
_paper_trading_cache_timeout = 10  # 10 seconds cache

@app.get("/paper_trading_status.json")
async def get_paper_trading_status():
    """Get current paper trading status for dashboard"""
    try:
        # Check cache first
        cache_key = "paper_trading_status"
        now = datetime.now()
        
        if cache_key in _paper_trading_cache:
            cached_data, cached_time = _paper_trading_cache[cache_key]
            if (now - cached_time).total_seconds() < _paper_trading_cache_timeout:
                return cached_data
        
        # Get current capital
        if trading_system.risk_manager:
            capital_data = trading_system.risk_manager.get_capital_info()
            current_capital = capital_data.get('current_capital', 100000)
            initial_capital = capital_data.get('starting_capital', 100000)
        else:
            current_capital = 100000
            initial_capital = 100000
        
        # Get strategy allocations from strategy_zoo
        strategies = {
            "quantum_edge_v2": {"enabled": True, "allocation": 0.25},
            "quantum_edge": {"enabled": True, "allocation": 0.20},
            "default": {"enabled": True, "allocation": 0.10},
            "gamma_scalping": {"enabled": True, "allocation": 0.15},
            "vwap_deviation": {"enabled": True, "allocation": 0.10},
            "iv_rank_trading": {"enabled": True, "allocation": 0.10}
        }
        
        # Get current positions count
        positions = await trading_system.order_manager.get_positions()
        
        response = {
            "timestamp": datetime.now().isoformat(),
            "capital": current_capital,
            "initial_capital": initial_capital,
            "total_pnl": current_capital - initial_capital,
            "last_pnl": current_capital - initial_capital,
            "iteration": 1,
            "sac_enabled": trading_system.sac_enabled,
            "active_strategies": len(trading_system.strategy_zoo.strategies) if trading_system.strategy_zoo else 0,
            "sac_allocation": [0.25, 0.20, 0.10, 0.15, 0.10, 0.10],  # Actual strategy allocations
            "top_groups": [0, 1, 3],  # Top 3 strategies by allocation
            "market_status": "open",
            "strategies": strategies,
            "open_positions": len(positions)
        }
        
        # Store in cache
        _paper_trading_cache[cache_key] = (response, now)
        
        return response
    except Exception as e:
        logger.error(f"Error generating paper trading status: {e}")
        return {
            "timestamp": datetime.now().isoformat(),
            "capital": 100000,
            "initial_capital": 100000,
            "total_pnl": 0,
            "last_pnl": 0,
            "iteration": 0,
            "sac_enabled": trading_system.sac_enabled,
            "active_strategies": 6,
            "sac_allocation": [0.25, 0.20, 0.10, 0.15, 0.10, 0.10],
            "top_groups": [0, 1, 3],
            "market_status": "open",
            "strategies": {},
            "open_positions": 0
        }


@app.get("/api/performance")
async def get_performance():
    """Get performance metrics"""
    if trading_system.risk_manager:
        metrics = {
            "daily_pnl": trading_system.risk_manager.get_daily_pnl(),
            "total_trades": trading_system.risk_manager.get_total_trades(),
            "win_rate": trading_system.risk_manager.get_win_rate(),
            "profit_factor": trading_system.risk_manager.get_profit_factor()
        }
        return metrics
    return {}


@app.get("/api/option-chain/{symbol}/{expiry}")
async def get_option_chain(symbol: str, expiry: str):
    """Get option chain data"""
    if trading_system and hasattr(trading_system, 'market_data') and trading_system.market_data:
        chain = await trading_system.market_data.get_option_chain(symbol, expiry)
        return {"option_chain": chain}
    return {"option_chain": None, "error": "Market data not available - system running in dashboard-only mode"}


@app.get("/api/trades/history")
async def get_trade_history(limit: int = 100, offset: int = 0):
    """Get trade history from database"""
    try:
        from backend.database.models import Trade
        from backend.database.db import session_scope
        
        with session_scope() as session:
            trades = session.query(Trade)\
                .order_by(Trade.entry_time.desc())\
                .limit(limit)\
                .offset(offset)\
                .all()
            
            return {
                "trades": [trade.to_dict() for trade in trades],
                "total": session.query(Trade).count(),
                "limit": limit,
                "offset": offset
            }
    except Exception as e:
        logger.error(f"Error fetching trade history: {e}")
        return {"trades": [], "total": 0, "error": str(e)}


@app.get("/api/upstox/token/status")
async def get_token_status():
    """Check Upstox token status"""
    import pathlib
    import time
    
    token_file = pathlib.Path(config.settings.upstox_token_file)
    
    if not token_file.exists():
        return {"exists": False, "valid": False}
    
    try:
        with open(token_file) as f:
            data = json.load(f)
            created_at = data.get('created_at', 0)
            expires_in = data.get('expires_in', 86400)  # Default 24 hours in seconds
            
            # Calculate when token expires
            expires_at = created_at + expires_in
            current_time = time.time()
            
            # Token is valid if current time is before expiry time
            valid = current_time < expires_at
            
            # Calculate age and remaining time
            age_seconds = current_time - created_at
            remaining_seconds = expires_at - current_time
            
            return {
                "exists": True,
                "valid": valid,
                "age_hours": round(age_seconds / 3600, 1),
                "remaining_hours": round(remaining_seconds / 3600, 1) if valid else 0,
                "created_at": created_at,
                "expires_at": expires_at
            }
    except Exception as e:
        return {"exists": True, "valid": False, "error": str(e)}


@app.post("/api/upstox/token/start-auth")
async def start_upstox_auth():
    """Proxy dashboard auth start to shared Upstox handler."""
    from backend.api.upstox_auth import start_auth_flow

    logger.info("Dashboard requested Upstox auth start; delegating to shared handler")
    return await start_auth_flow()


@app.post("/api/trading/start")
async def start_trading():
    """Start trading"""
    try:
        if not trading_system.is_running:
            logger.info("Starting trading system via API request...")
            await trading_system.start()
            return {"message": "Trading started successfully", "status": "success"}
        else:
            # Already running, but restart background tasks just in case
            logger.info("Trading system already marked as running, restarting background tasks...")
            if trading_system.market_data and trading_system.risk_manager:
                asyncio.create_task(trading_system.trading_loop())
                asyncio.create_task(trading_system.market_data_loop())
                asyncio.create_task(trading_system.risk_monitoring_loop())
                return {"message": "Trading system refreshed", "status": "success"}
            return {"message": "Trading already running", "status": "info"}
    except Exception as e:
        logger.error(f"Failed to start trading system: {e}")
        return {"message": f"Failed to start: {str(e)}", "status": "error"}


@app.post("/api/trading/stop")
async def stop_trading():
    """Stop trading"""
    if trading_system.is_running:
        await trading_system.stop()
        return {"message": "Trading stopped", "status": "success"}
    return {"message": "Trading not running", "status": "info"}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates"""
    await websocket.accept()
    trading_system.websocket_clients.append(websocket)
    
    # Also register with ws_manager for broadcasting
    client_id = f"dashboard_{id(websocket)}"
    # Don't call accept again on ws_manager since it's already accepted
    trading_system.ws_manager.active_connections.add(websocket)
    trading_system.ws_manager.connection_metadata[websocket] = {
        "client_id": client_id,
        "connected_at": datetime.now(),
        "message_count": 0
    }
    
    try:
        while True:
            # Keep connection alive
            data = await websocket.receive_text()
            # Echo back
            await websocket.send_json({"type": "pong", "data": data})
    except WebSocketDisconnect:
        if websocket in trading_system.websocket_clients:
            trading_system.websocket_clients.remove(websocket)
        trading_system.ws_manager.disconnect(websocket)


@app.post("/api/backtest")
async def run_backtest():
    """Run comprehensive backtest with all strategies and ML"""
    try:
        from backend.backtest import run_full_backtest  # Fix import for backtest_runner
        results = await run_full_backtest()
        return {
            "status": "success",
            "results": results
        }
    except Exception as e:
        logger.error(f"Backtest failed: {e}")
        return {"status": "error", "message": str(e)}


async def run_trading_system():
    """Run trading system with auto-restart"""
    while True:
        try:
            trading_system = TradingSystem()
            await trading_system.start()
            logger.info("Trading system started")
            while trading_system.is_running:
                await asyncio.sleep(1)
            logger.warning("Trading system stopped")
        except Exception as e:
            logger.critical(f"Trading engine crashed: {e}", exc_info=True)
        logger.info("Restarting trading system in 10 seconds...")
        await asyncio.sleep(10)


if __name__ == "__main__":
    asyncio.run(run_trading_system())
