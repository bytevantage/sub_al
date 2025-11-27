"""
Slippage and Cost Modeling
Simulates realistic execution costs for paper trading
"""

import random
from typing import Dict, Optional
from datetime import datetime

from backend.core.logger import get_logger

logger = get_logger(__name__)


class SlippageModel:
    """
    Models realistic slippage and execution costs
    
    Components:
    - Bid-ask spread
    - Market impact
    - Liquidity-based slippage
    - Transaction costs (brokerage + taxes)
    """
    
    def __init__(self, config: Dict):
        self.config = config
        
        # Slippage parameters
        self.base_slippage_bps = config.get('base_slippage_bps', 10)  # 0.1%
        self.high_vol_slippage_bps = config.get('high_vol_slippage_bps', 50)  # 0.5%
        self.spread_bps = config.get('spread_bps', 5)  # 0.05%
        
        # Transaction costs (per trade)
        self.brokerage_rate = config.get('brokerage_rate', 0.0003)  # 0.03%
        self.stt_rate = config.get('stt_rate', 0.0005)  # 0.05% on options
        self.exchange_charges = config.get('exchange_charges', 0.0005)  # 0.05%
        self.gst_rate = config.get('gst_rate', 0.18)  # 18% on brokerage
        
        # Liquidity thresholds
        self.high_liquidity_oi = config.get('high_liquidity_oi', 50000)
        self.low_liquidity_oi = config.get('low_liquidity_oi', 10000)
        
    def calculate_execution_price(
        self,
        theoretical_price: float,
        side: str,
        quantity: int,
        open_interest: Optional[int] = None,
        iv: Optional[float] = None,
        timestamp: Optional[datetime] = None
    ) -> Dict:
        """
        Calculate realistic execution price with slippage
        
        Args:
            theoretical_price: Clean theoretical price (LTP or signal price)
            side: BUY or SELL
            quantity: Order quantity
            open_interest: Open interest for liquidity estimation
            iv: Implied volatility for volatility-based adjustment
            timestamp: Order timestamp for time-based factors
            
        Returns:
            Dict with execution_price, slippage_amount, slippage_percent, breakdown
        """
        
        # 1. Base spread cost (always incurred)
        spread_cost = self._calculate_spread(theoretical_price)
        
        # 2. Market impact based on liquidity
        liquidity_slippage = self._calculate_liquidity_slippage(
            theoretical_price, quantity, open_interest
        )
        
        # 3. Volatility-based slippage
        vol_slippage = self._calculate_volatility_slippage(
            theoretical_price, iv
        )
        
        # 4. Time-of-day adjustment
        time_adjustment = self._calculate_time_adjustment(
            theoretical_price, timestamp
        )
        
        # Total slippage
        total_slippage = spread_cost + liquidity_slippage + vol_slippage + time_adjustment
        
        # Apply direction (buy pays more, sell receives less)
        if side == "BUY":
            execution_price = theoretical_price + total_slippage
        else:
            execution_price = theoretical_price - total_slippage
            
        slippage_percent = (total_slippage / theoretical_price * 100) if theoretical_price > 0 else 0
        
        result = {
            'execution_price': round(execution_price, 2),
            'theoretical_price': theoretical_price,
            'slippage_amount': round(total_slippage, 2),
            'slippage_percent': round(slippage_percent, 4),
            'breakdown': {
                'spread_cost': round(spread_cost, 2),
                'liquidity_slippage': round(liquidity_slippage, 2),
                'volatility_slippage': round(vol_slippage, 2),
                'time_adjustment': round(time_adjustment, 2)
            }
        }
        
        logger.debug(
            f"Slippage calculation: {side} @ ₹{theoretical_price:.2f} "
            f"→ ₹{execution_price:.2f} (slippage: {slippage_percent:.2f}%)"
        )
        
        return result
        
    def _calculate_spread(self, price: float) -> float:
        """Calculate bid-ask spread cost"""
        # Half-spread (crossing the spread)
        spread = price * (self.spread_bps / 10000) / 2
        return spread
        
    def _calculate_liquidity_slippage(
        self,
        price: float,
        quantity: int,
        open_interest: Optional[int]
    ) -> float:
        """Calculate market impact based on liquidity"""
        
        if open_interest is None:
            # Use medium slippage if OI unknown
            slippage_bps = (self.base_slippage_bps + self.high_vol_slippage_bps) / 2
        elif open_interest >= self.high_liquidity_oi:
            # High liquidity: low slippage
            slippage_bps = self.base_slippage_bps
        elif open_interest <= self.low_liquidity_oi:
            # Low liquidity: high slippage
            slippage_bps = self.high_vol_slippage_bps
        else:
            # Interpolate
            liquidity_factor = (open_interest - self.low_liquidity_oi) / (
                self.high_liquidity_oi - self.low_liquidity_oi
            )
            slippage_bps = self.high_vol_slippage_bps - (
                liquidity_factor * (self.high_vol_slippage_bps - self.base_slippage_bps)
            )
            
        # Add randomness (±20%)
        slippage_bps *= random.uniform(0.8, 1.2)
        
        return price * (slippage_bps / 10000)
        
    def _calculate_volatility_slippage(
        self,
        price: float,
        iv: Optional[float]
    ) -> float:
        """Calculate additional slippage during high volatility"""
        
        if iv is None:
            return 0
            
        # Extra slippage when IV > 30%
        if iv > 30:
            extra_vol_slippage_bps = (iv - 30) * 0.5  # 0.5 bps per IV point above 30
            return price * (extra_vol_slippage_bps / 10000)
            
        return 0
        
    def _calculate_time_adjustment(
        self,
        price: float,
        timestamp: Optional[datetime]
    ) -> float:
        """Calculate time-of-day adjustment (opening/closing more slippage)"""
        
        if timestamp is None:
            return 0
            
        # Market open (9:15-9:30) and close (3:15-3:30): higher slippage
        hour = timestamp.hour
        minute = timestamp.minute
        
        if (hour == 9 and minute < 30) or (hour == 15 and minute >= 15):
            # 50% extra slippage during volatile periods
            return price * (self.base_slippage_bps / 10000) * 0.5
            
        return 0
        
    def calculate_transaction_costs(
        self,
        trade_value: float,
        side: str
    ) -> Dict:
        """
        Calculate all transaction costs
        
        Args:
            trade_value: Total trade value (price * quantity)
            side: BUY or SELL
            
        Returns:
            Dict with cost breakdown
        """
        
        # Brokerage (capped at ₹20 per order for intraday)
        brokerage = min(trade_value * self.brokerage_rate, 20)
        
        # STT (only on sell side for options)
        stt = trade_value * self.stt_rate if side == "SELL" else 0
        
        # Exchange charges
        exchange_charges = trade_value * self.exchange_charges
        
        # GST on brokerage and exchange charges
        gst = (brokerage + exchange_charges) * self.gst_rate
        
        # SEBI charges (negligible, ~₹0.10)
        sebi_charges = trade_value * 0.000001
        
        # Stamp duty (only on buy side, 0.003%)
        stamp_duty = trade_value * 0.00003 if side == "BUY" else 0
        
        total_cost = brokerage + stt + exchange_charges + gst + sebi_charges + stamp_duty
        
        return {
            'brokerage': round(brokerage, 2),
            'stt': round(stt, 2),
            'exchange_charges': round(exchange_charges, 2),
            'gst': round(gst, 2),
            'sebi_charges': round(sebi_charges, 2),
            'stamp_duty': round(stamp_duty, 2),
            'total_cost': round(total_cost, 2),
            'cost_percent': round(total_cost / trade_value * 100, 4) if trade_value > 0 else 0
        }
        
    def calculate_net_pnl(
        self,
        entry_value: float,
        exit_value: float,
        quantity: int,
        entry_slippage: Dict,
        exit_slippage: Dict
    ) -> Dict:
        """
        Calculate net P&L after all costs
        
        Args:
            entry_value: Entry trade value
            exit_value: Exit trade value
            quantity: Position quantity
            entry_slippage: Entry slippage dict from calculate_execution_price
            exit_slippage: Exit slippage dict from calculate_execution_price
            
        Returns:
            Dict with detailed P&L breakdown
        """
        
        # Gross P&L (before costs)
        gross_pnl = exit_value - entry_value
        
        # Total slippage cost
        total_slippage = (
            entry_slippage['slippage_amount'] + exit_slippage['slippage_amount']
        ) * quantity
        
        # Transaction costs
        entry_costs = self.calculate_transaction_costs(entry_value, "BUY")
        exit_costs = self.calculate_transaction_costs(exit_value, "SELL")
        total_transaction_costs = entry_costs['total_cost'] + exit_costs['total_cost']
        
        # Net P&L
        net_pnl = gross_pnl - total_slippage - total_transaction_costs
        
        return {
            'gross_pnl': round(gross_pnl, 2),
            'total_slippage': round(total_slippage, 2),
            'total_transaction_costs': round(total_transaction_costs, 2),
            'net_pnl': round(net_pnl, 2),
            'cost_breakdown': {
                'entry': entry_costs,
                'exit': exit_costs
            },
            'slippage_breakdown': {
                'entry': entry_slippage,
                'exit': exit_slippage
            }
        }
