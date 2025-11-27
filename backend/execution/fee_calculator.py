"""
Fee and Tax Calculator
Calculates brokerage fees, taxes, and net P&L for options trading
"""

from typing import Dict, Tuple
from backend.core.logger import get_execution_logger

logger = get_execution_logger()


class FeeCalculator:
    """
    Calculate trading fees and taxes for options
    
    Upstox Fees (as of Nov 2025):
    - Brokerage: ₹20 per executed order (or 0.05%, whichever is lower)
    - STT (Securities Transaction Tax): 0.0625% on sell side (premium)
    - Exchange Charges: ~0.053% (NSE: 0.053%, BSE: 0.05%)
    - GST: 18% on (brokerage + exchange charges)
    - SEBI Charges: ₹10 per crore turnover
    - Stamp Duty: 0.003% on buy side
    """
    
    def __init__(self):
        # Brokerage
        self.brokerage_flat = 20.0  # ₹20 per order
        self.brokerage_percent = 0.0005  # 0.05%
        
        # STT (on sell side only)
        self.stt_rate = 0.000625  # 0.0625% on premium
        
        # Exchange charges
        self.exchange_charges_nse = 0.00053  # 0.053%
        self.exchange_charges_bse = 0.0005   # 0.05%
        
        # GST on brokerage + exchange charges
        self.gst_rate = 0.18  # 18%
        
        # SEBI charges
        self.sebi_charges_per_crore = 10.0  # ₹10 per crore
        
        # Stamp duty (on buy side only)
        self.stamp_duty_rate = 0.00003  # 0.003%
    
    def calculate_brokerage(self, turnover: float) -> float:
        """
        Calculate brokerage (lower of flat or percentage)
        
        Args:
            turnover: Trade turnover (price * quantity)
            
        Returns:
            Brokerage amount
        """
        percentage_brokerage = turnover * self.brokerage_percent
        return min(self.brokerage_flat, percentage_brokerage)
    
    def calculate_stt(self, premium: float, quantity: int, side: str) -> float:
        """
        Calculate STT (on sell side only)
        
        Args:
            premium: Option premium
            quantity: Quantity traded
            side: BUY or SELL
            
        Returns:
            STT amount
        """
        if side.upper() == 'SELL':
            turnover = premium * quantity
            return turnover * self.stt_rate
        return 0.0
    
    def calculate_exchange_charges(self, turnover: float, exchange: str = 'NSE') -> float:
        """
        Calculate exchange transaction charges
        
        Args:
            turnover: Trade turnover
            exchange: NSE or BSE
            
        Returns:
            Exchange charges
        """
        rate = self.exchange_charges_nse if exchange == 'NSE' else self.exchange_charges_bse
        return turnover * rate
    
    def calculate_gst(self, brokerage: float, exchange_charges: float) -> float:
        """
        Calculate GST on brokerage and exchange charges
        
        Args:
            brokerage: Brokerage amount
            exchange_charges: Exchange charges
            
        Returns:
            GST amount
        """
        return (brokerage + exchange_charges) * self.gst_rate
    
    def calculate_sebi_charges(self, turnover: float) -> float:
        """
        Calculate SEBI charges
        
        Args:
            turnover: Trade turnover
            
        Returns:
            SEBI charges
        """
        turnover_crores = turnover / 10000000  # Convert to crores
        return turnover_crores * self.sebi_charges_per_crore
    
    def calculate_stamp_duty(self, turnover: float, side: str) -> float:
        """
        Calculate stamp duty (on buy side only)
        
        Args:
            turnover: Trade turnover
            side: BUY or SELL
            
        Returns:
            Stamp duty amount
        """
        if side.upper() == 'BUY':
            return turnover * self.stamp_duty_rate
        return 0.0
    
    def calculate_total_fees(
        self,
        entry_price: float,
        exit_price: float,
        quantity: int,
        exchange: str = 'NSE'
    ) -> Dict[str, float]:
        """
        Calculate all fees for a complete trade (entry + exit)
        
        Args:
            entry_price: Entry price per unit
            exit_price: Exit price per unit
            quantity: Quantity traded
            exchange: NSE or BSE
            
        Returns:
            Dictionary with fee breakdown
        """
        # Calculate turnovers
        entry_turnover = entry_price * quantity
        exit_turnover = exit_price * quantity
        total_turnover = entry_turnover + exit_turnover
        
        # Brokerage (both sides)
        entry_brokerage = self.calculate_brokerage(entry_turnover)
        exit_brokerage = self.calculate_brokerage(exit_turnover)
        total_brokerage = entry_brokerage + exit_brokerage
        
        # STT (sell side only - on exit for long positions)
        stt = self.calculate_stt(exit_price, quantity, 'SELL')
        
        # Exchange charges (both sides)
        entry_exchange_charges = self.calculate_exchange_charges(entry_turnover, exchange)
        exit_exchange_charges = self.calculate_exchange_charges(exit_turnover, exchange)
        total_exchange_charges = entry_exchange_charges + exit_exchange_charges
        
        # GST on brokerage and exchange charges
        gst = self.calculate_gst(total_brokerage, total_exchange_charges)
        
        # SEBI charges
        sebi_charges = self.calculate_sebi_charges(total_turnover)
        
        # Stamp duty (buy side - on entry for long positions)
        stamp_duty = self.calculate_stamp_duty(entry_turnover, 'BUY')
        
        # Total fees
        total_fees = (
            total_brokerage +
            stt +
            total_exchange_charges +
            gst +
            sebi_charges +
            stamp_duty
        )
        
        return {
            'entry_brokerage': round(entry_brokerage, 2),
            'exit_brokerage': round(exit_brokerage, 2),
            'total_brokerage': round(total_brokerage, 2),
            'stt': round(stt, 2),
            'exchange_charges': round(total_exchange_charges, 2),
            'gst': round(gst, 2),
            'sebi_charges': round(sebi_charges, 2),
            'stamp_duty': round(stamp_duty, 2),
            'total_fees': round(total_fees, 2)
        }
    
    def calculate_net_pnl(
        self,
        gross_pnl: float,
        entry_price: float,
        exit_price: float,
        quantity: int,
        exchange: str = 'NSE'
    ) -> Tuple[float, Dict[str, float]]:
        """
        Calculate net P&L after deducting all fees
        
        Args:
            gross_pnl: Gross P&L before fees
            entry_price: Entry price per unit
            exit_price: Exit price per unit
            quantity: Quantity traded
            exchange: NSE or BSE
            
        Returns:
            Tuple of (net_pnl, fee_breakdown)
        """
        fees = self.calculate_total_fees(entry_price, exit_price, quantity, exchange)
        net_pnl = gross_pnl - fees['total_fees']
        
        logger.debug(
            f"P&L Calculation: Gross=₹{gross_pnl:.2f}, Fees=₹{fees['total_fees']:.2f}, "
            f"Net=₹{net_pnl:.2f}"
        )
        
        return round(net_pnl, 2), fees
    
    def estimate_fees_for_position(
        self,
        entry_price: float,
        quantity: int,
        expected_exit_price: float = None,
        exchange: str = 'NSE'
    ) -> Dict[str, float]:
        """
        Estimate fees for a position (useful for pre-trade analysis)
        
        Args:
            entry_price: Entry price per unit
            quantity: Quantity to trade
            expected_exit_price: Expected exit price (defaults to entry_price if not provided)
            exchange: NSE or BSE
            
        Returns:
            Estimated fee breakdown
        """
        if expected_exit_price is None:
            expected_exit_price = entry_price
        
        return self.calculate_total_fees(entry_price, expected_exit_price, quantity, exchange)
    
    def get_breakeven_exit_price(
        self,
        entry_price: float,
        quantity: int,
        exchange: str = 'NSE'
    ) -> float:
        """
        Calculate breakeven exit price (entry price + fees per unit)
        
        Args:
            entry_price: Entry price per unit
            quantity: Quantity traded
            exchange: NSE or BSE
            
        Returns:
            Breakeven exit price
        """
        # Estimate fees assuming exit at entry price
        fees = self.estimate_fees_for_position(entry_price, quantity, entry_price, exchange)
        
        # Calculate fee per unit
        fee_per_unit = fees['total_fees'] / quantity
        
        # Breakeven is entry price + fees per unit
        breakeven = entry_price + fee_per_unit
        
        logger.debug(
            f"Breakeven calculation: Entry=₹{entry_price:.2f}, "
            f"Fees per unit=₹{fee_per_unit:.2f}, Breakeven=₹{breakeven:.2f}"
        )
        
        return round(breakeven, 2)


# Global fee calculator instance
fee_calculator = FeeCalculator()


def get_fee_calculator() -> FeeCalculator:
    """Get the global fee calculator instance"""
    return fee_calculator
