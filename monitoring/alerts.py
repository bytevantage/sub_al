"""
Monitoring & Alerts System
Telegram notifications for critical events

Author: AI Systems Operator
Last Modified: 2025-11-20
"""

import os
import requests
from datetime import datetime
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class TelegramAlerts:
    """Telegram alert system for critical events"""
    
    def __init__(self):
        self.bot_token = os.getenv('TELEGRAM_BOT_TOKEN', '')
        self.chat_id = os.getenv('TELEGRAM_CHAT_ID', '')
        self.enabled = bool(self.bot_token and self.chat_id)
        
        if not self.enabled:
            logger.warning("Telegram alerts disabled - missing credentials")
            logger.info("Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID environment variables")
    
    def send_message(self, message: str, priority: str = 'info'):
        """Send message to Telegram"""
        if not self.enabled:
            logger.info(f"[TELEGRAM {priority.upper()}] {message}")
            return False
        
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            
            # Add timestamp
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S IST')
            full_message = f"{message}\n\n⏰ {timestamp}"
            
            payload = {
                'chat_id': self.chat_id,
                'text': full_message,
                'parse_mode': 'HTML' if '<' in message else 'Markdown'
            }
            
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            
            logger.info(f"Telegram alert sent: {priority}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send Telegram message: {e}")
            return False
    
    def send_critical(self, message: str):
        """Send critical alert (urgent action required)"""
        formatted = f"🚨 CRITICAL ALERT 🚨\n\n{message}"
        return self.send_message(formatted, priority='critical')
    
    def send_warning(self, message: str):
        """Send warning alert (attention needed)"""
        formatted = f"⚠️  WARNING\n\n{message}"
        return self.send_message(formatted, priority='warning')
    
    def send_info(self, message: str):
        """Send informational message"""
        return self.send_message(message, priority='info')
    
    def send_success(self, message: str):
        """Send success message"""
        formatted = f"✅ SUCCESS\n\n{message}"
        return self.send_message(formatted, priority='success')


class SystemMonitor:
    """Monitor system health and send alerts"""
    
    def __init__(self):
        self.alerts = TelegramAlerts()
        self.critic_loss_threshold = 3.0  # 300% jump
        self.accuracy_threshold = 0.80  # 80%
        self.allocation_stability_threshold = 0.5  # 50% change
        
    def check_critic_loss_spike(self, current_loss: float, previous_loss: Optional[float]):
        """Check if critic loss has spiked dangerously"""
        if previous_loss is None:
            return False
        
        if current_loss > previous_loss * self.critic_loss_threshold:
            jump_pct = (current_loss / previous_loss - 1) * 100
            
            self.alerts.send_critical(
                f"🚨 SAC CRITIC LOSS SPIKE\n\n"
                f"Previous: {previous_loss:.4f}\n"
                f"Current: {current_loss:.4f}\n"
                f"Jump: {jump_pct:.1f}%\n\n"
                f"⚠️  Trading should be paused!\n"
                f"Manual review required."
            )
            return True
        
        return False
    
    def check_quantum_edge_accuracy(self, accuracy: float):
        """Check if QuantumEdge accuracy has dropped"""
        if accuracy < self.accuracy_threshold:
            self.alerts.send_warning(
                f"⚠️  QUANTUMEDGE ACCURACY DROP\n\n"
                f"Current: {accuracy:.2%}\n"
                f"Threshold: {self.accuracy_threshold:.2%}\n\n"
                f"Consider full retrain or review data quality."
            )
            return True
        
        return False
    
    def check_allocation_stability(self, previous_alloc, current_alloc):
        """Check if SAC allocations are unstable"""
        import numpy as np
        
        if previous_alloc is None:
            return False
        
        change = np.abs(np.array(current_alloc) - np.array(previous_alloc)).max()
        
        if change > self.allocation_stability_threshold:
            self.alerts.send_warning(
                f"⚠️  SAC ALLOCATION INSTABILITY\n\n"
                f"Max change: {change:.2%}\n"
                f"Threshold: {self.allocation_stability_threshold:.2%}\n\n"
                f"SAC allocations are changing rapidly.\n"
                f"This may indicate:\n"
                f"  • Market regime change\n"
                f"  • Model instability\n"
                f"  • Data quality issues\n\n"
                f"Monitor closely."
            )
            return True
        
        return False
    
    def send_daily_summary(self, metrics: dict):
        """Send end-of-day summary"""
        summary = (
            f"📊 DAILY SUMMARY\n"
            f"{'='*40}\n\n"
            f"Date: {datetime.now().strftime('%Y-%m-%d')}\n\n"
        )
        
        if 'pnl' in metrics:
            summary += f"💰 P&L: ₹{metrics['pnl']:,.2f}\n"
        
        if 'trades' in metrics:
            summary += f"📈 Trades: {metrics['trades']}\n"
        
        if 'win_rate' in metrics:
            summary += f"🎯 Win Rate: {metrics['win_rate']:.1%}\n"
        
        if 'quantum_edge_signals' in metrics:
            summary += f"🤖 QuantumEdge Signals: {metrics['quantum_edge_signals']}\n"
        
        if 'sac_updates' in metrics:
            summary += f"🎯 SAC Updates: {metrics['sac_updates']}\n"
        
        self.alerts.send_info(summary)
    
    def send_weekly_report(self, metrics: dict):
        """Send weekly performance report"""
        report = (
            f"📊 WEEKLY REPORT\n"
            f"{'='*40}\n\n"
            f"Week ending: {datetime.now().strftime('%Y-%m-%d')}\n\n"
        )
        
        if 'weekly_pnl' in metrics:
            report += f"💰 Weekly P&L: ₹{metrics['weekly_pnl']:,.2f}\n"
        
        if 'total_trades' in metrics:
            report += f"📈 Total Trades: {metrics['total_trades']}\n"
        
        if 'best_strategy' in metrics:
            report += f"🏆 Best Strategy: {metrics['best_strategy']}\n"
        
        if 'worst_strategy' in metrics:
            report += f"⚠️  Worst Strategy: {metrics['worst_strategy']}\n"
        
        report += f"\n{'='*40}\n"
        report += f"Next SAC full retrain: Friday 6 PM IST"
        
        self.alerts.send_info(report)
    
    def send_startup_notification(self):
        """Send notification when system starts"""
        self.alerts.send_success(
            f"🚀 TRADING SYSTEM STARTED\n\n"
            f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S IST')}\n"
            f"Mode: Paper Trading\n"
            f"Capital: ₹50,00,000\n\n"
            f"All systems operational."
        )
    
    def send_shutdown_notification(self, reason: str = "Normal shutdown"):
        """Send notification when system stops"""
        self.alerts.send_info(
            f"⏹️  TRADING SYSTEM STOPPED\n\n"
            f"Reason: {reason}\n"
            f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S IST')}"
        )


# Global monitor instance
monitor = SystemMonitor()
