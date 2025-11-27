"""
Multi-Leg Spread Pricing Engine
Handles pricing, Greeks calculation, and P&L for option spreads
"""
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class OptionLeg:
    """Single leg of a multi-leg spread"""
    symbol: str
    strike: float
    option_type: str  # 'CE' or 'PE'
    action: str  # 'BUY' or 'SELL'
    quantity: int
    price: float
    greeks: Dict[str, float]  # delta, gamma, theta, vega, iv
    
    @property
    def signed_quantity(self) -> int:
        """Quantity with sign based on action"""
        return self.quantity if self.action == 'BUY' else -self.quantity
    
    @property
    def premium_flow(self) -> float:
        """Cash flow from this leg (negative for debit, positive for credit)"""
        return -self.price * self.signed_quantity


@dataclass
class SpreadPosition:
    """Multi-leg spread position"""
    spread_type: str  # 'IRON_CONDOR', 'BUTTERFLY', 'STRADDLE', 'STRANGLE'
    legs: List[OptionLeg]
    entry_cost: float  # Net debit (positive) or credit (negative)
    max_profit: float
    max_loss: float
    breakeven_points: List[float]
    net_greeks: Dict[str, float]
    
    def calculate_pnl(self, current_prices: Dict[str, float]) -> float:
        """Calculate current P&L of the spread"""
        current_value = sum(
            leg.signed_quantity * current_prices.get(leg.symbol, leg.price)
            for leg in self.legs
        )
        return current_value - self.entry_cost


class SpreadPricer:
    """Pricing engine for multi-leg option spreads"""
    
    @staticmethod
    def calculate_net_greeks(legs: List[OptionLeg]) -> Dict[str, float]:
        """Calculate net Greeks for a spread"""
        net_greeks = {
            'delta': 0.0,
            'gamma': 0.0,
            'theta': 0.0,
            'vega': 0.0,
            'iv': 0.0
        }
        
        total_weight = 0
        for leg in legs:
            weight = abs(leg.signed_quantity)
            total_weight += weight
            
            sign = 1 if leg.action == 'BUY' else -1
            net_greeks['delta'] += leg.greeks.get('delta', 0) * sign * weight
            net_greeks['gamma'] += leg.greeks.get('gamma', 0) * sign * weight
            net_greeks['theta'] += leg.greeks.get('theta', 0) * sign * weight
            net_greeks['vega'] += leg.greeks.get('vega', 0) * sign * weight
            net_greeks['iv'] += leg.greeks.get('iv', 0) * weight
        
        # Average IV
        if total_weight > 0:
            net_greeks['iv'] /= total_weight
            
        return net_greeks
    
    @staticmethod
    def calculate_spread_cost(legs: List[OptionLeg]) -> float:
        """Calculate net debit/credit for entering the spread"""
        return sum(leg.premium_flow for leg in legs)
    
    @staticmethod
    def calculate_iron_condor_metrics(
        legs: List[OptionLeg],
        spot_price: float
    ) -> Tuple[float, float, List[float]]:
        """
        Calculate max profit, max loss, and breakeven for Iron Condor
        Structure: Sell OTM Put, Buy further OTM Put, Sell OTM Call, Buy further OTM Call
        """
        if len(legs) != 4:
            raise ValueError("Iron Condor requires exactly 4 legs")
        
        # Sort legs by strike
        put_legs = sorted([l for l in legs if l.option_type == 'PE'], key=lambda x: x.strike)
        call_legs = sorted([l for l in legs if l.option_type == 'CE'], key=lambda x: x.strike)
        
        if len(put_legs) != 2 or len(call_legs) != 2:
            raise ValueError("Iron Condor requires 2 puts and 2 calls")
        
        # Net credit received (max profit)
        net_credit = -sum(leg.premium_flow for leg in legs)
        max_profit = net_credit
        
        # Max loss is the width of wider spread minus net credit
        put_spread_width = abs(put_legs[1].strike - put_legs[0].strike)
        call_spread_width = abs(call_legs[1].strike - call_legs[0].strike)
        max_spread_width = max(put_spread_width, call_spread_width)
        max_loss = max_spread_width - net_credit
        
        # Breakeven points
        lower_breakeven = put_legs[1].strike + net_credit  # Sold put strike + credit
        upper_breakeven = call_legs[0].strike - net_credit  # Sold call strike - credit
        breakeven_points = [lower_breakeven, upper_breakeven]
        
        return max_profit, max_loss, breakeven_points
    
    @staticmethod
    def calculate_butterfly_metrics(
        legs: List[OptionLeg],
        spot_price: float
    ) -> Tuple[float, float, List[float]]:
        """
        Calculate max profit, max loss, and breakeven for Butterfly
        Structure: Buy 1 ITM, Sell 2 ATM, Buy 1 OTM (all same type)
        """
        if len(legs) != 3:
            raise ValueError("Butterfly requires exactly 3 legs")
        
        # Sort by strike
        sorted_legs = sorted(legs, key=lambda x: x.strike)
        
        # Net debit paid (max loss)
        net_debit = sum(leg.premium_flow for leg in legs)
        max_loss = abs(net_debit)
        
        # Max profit = (Middle strike - Lower strike) - Net debit
        lower_strike = sorted_legs[0].strike
        middle_strike = sorted_legs[1].strike
        upper_strike = sorted_legs[2].strike
        
        max_profit = (middle_strike - lower_strike) - max_loss
        
        # Breakeven points
        lower_breakeven = lower_strike + max_loss
        upper_breakeven = upper_strike - max_loss
        breakeven_points = [lower_breakeven, upper_breakeven]
        
        return max_profit, max_loss, breakeven_points
    
    @staticmethod
    def calculate_straddle_strangle_metrics(
        legs: List[OptionLeg],
        spot_price: float
    ) -> Tuple[float, float, List[float]]:
        """
        Calculate max profit, max loss, and breakeven for Straddle/Strangle
        Structure: Buy/Sell Call + Buy/Sell Put (2 legs)
        """
        if len(legs) != 2:
            raise ValueError("Straddle/Strangle requires exactly 2 legs")
        
        call_leg = next((l for l in legs if l.option_type == 'CE'), None)
        put_leg = next((l for l in legs if l.option_type == 'PE'), None)
        
        if not call_leg or not put_leg:
            raise ValueError("Straddle/Strangle requires 1 call and 1 put")
        
        # Net debit/credit
        net_cost = sum(leg.premium_flow for leg in legs)
        
        if legs[0].action == 'BUY':
            # Long Straddle/Strangle
            max_loss = abs(net_cost)
            max_profit = float('inf')  # Unlimited
            
            # Breakeven = strike ± net debit
            lower_breakeven = put_leg.strike - max_loss
            upper_breakeven = call_leg.strike + max_loss
        else:
            # Short Straddle/Strangle
            max_profit = abs(net_cost)
            max_loss = float('inf')  # Unlimited risk
            
            # Breakeven = strike ± net credit
            lower_breakeven = put_leg.strike - max_profit
            upper_breakeven = call_leg.strike + max_profit
        
        breakeven_points = [lower_breakeven, upper_breakeven]
        
        return max_profit, max_loss, breakeven_points
    
    @classmethod
    def create_spread_position(
        cls,
        spread_type: str,
        legs: List[OptionLeg],
        spot_price: float
    ) -> SpreadPosition:
        """Create a complete spread position with all metrics"""
        entry_cost = cls.calculate_spread_cost(legs)
        net_greeks = cls.calculate_net_greeks(legs)
        
        # Calculate spread-specific metrics
        if spread_type == 'IRON_CONDOR':
            max_profit, max_loss, breakeven = cls.calculate_iron_condor_metrics(legs, spot_price)
        elif spread_type == 'BUTTERFLY':
            max_profit, max_loss, breakeven = cls.calculate_butterfly_metrics(legs, spot_price)
        elif spread_type in ('STRADDLE', 'STRANGLE'):
            max_profit, max_loss, breakeven = cls.calculate_straddle_strangle_metrics(legs, spot_price)
        else:
            raise ValueError(f"Unknown spread type: {spread_type}")
        
        return SpreadPosition(
            spread_type=spread_type,
            legs=legs,
            entry_cost=entry_cost,
            max_profit=max_profit,
            max_loss=max_loss,
            breakeven_points=breakeven,
            net_greeks=net_greeks
        )
