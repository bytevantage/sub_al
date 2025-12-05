
"""
Telegram Notifications Service
Sends trade notifications and P&L updates to Telegram
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional, Dict, Any
import requests
from dataclasses import dataclass

from backend.core.timezone_utils import now_ist, to_ist
from backend.core.config import config

logger = logging.getLogger(__name__)

@dataclass
class TelegramConfig:
    """Telegram configuration"""
    bot_token: str
    chat_id: str
    enabled: bool = True

class TelegramNotifier:
    """Telegram notification service"""
    
    def __init__(self, bot_token: str = None, chat_id: str = None):
        """Initialize Telegram notifier"""
        # Get from config if not provided
        if bot_token is None:
            bot_token = config.get('notifications.telegram.bot_token', '')
        if chat_id is None:
            chat_id = config.get('notifications.telegram.chat_id', '')
        
        self.config = TelegramConfig(
            bot_token=bot_token,
            chat_id=chat_id,
            enabled=bool(bot_token and chat_id)
        )
        
        self.base_url = f"https://api.telegram.org/bot{self.config.bot_token}"
        
        logger.info(f"Telegram notifier initialized: {'✅ Enabled' if self.config.enabled else '❌ Disabled'}")
    
    async def send_message(self, message: str, parse_mode: str = 'Markdown') -> bool:
        """Send message to Telegram"""
        if not self.config.enabled:
            logger.debug("Telegram notifications disabled, skipping message")
            return False
        
        try:
            url = f"{self.base_url}/sendMessage"
            data = {
                'chat_id': self.config.chat_id,
                'text': message,
                'parse_mode': parse_mode
            }
            
            response = requests.post(url, json=data, timeout=10)
            response.raise_for_status()
            
            result = response.json()
            if result.get('ok'):
                logger.debug(f"Telegram message sent successfully")
                return True
            else:
                logger.error(f"Telegram API error: {result.get('description', 'Unknown error')}")
                return False
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send Telegram message: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending Telegram message: {e}")
            return False
    
    async def send_trade_entry(self, trade_data: Dict[str, Any]) -> bool:
        """Send trade entry notification"""
        if not self.config.enabled:
            return False
        
        try:
            symbol = trade_data.get('symbol', 'UNKNOWN')
            instrument_type = trade_data.get('instrument_type', 'UNKNOWN')
            strike_price = trade_data.get('strike_price', 0)
            entry_price = trade_data.get('entry_price', 0)
            quantity = trade_data.get('quantity', 0)
            strategy = trade_data.get('strategy_name', 'UNKNOWN')
            direction = trade_data.get('direction', 'BUY')
            
            message = f"""
🚀 *TRADE ENTRY*

📊 *Symbol*: {symbol}
📈 *Type*: {instrument_type} {strike_price}
💰 *Price*: ₹{entry_price:.2f}
📊 *Quantity*: {quantity}
🎯 *Strategy*: {strategy}
🔄 *Direction*: {direction}
⏰ *Time*: {to_ist(datetime.now()).strftime('%H:%M:%S IST')}

#Trading #Options #SAC
            """.strip()
            
            return await self.send_message(message)
            
        except Exception as e:
            logger.error(f"Error sending trade entry notification: {e}")
            return False
    
    async def send_trade_exit(self, trade_data: Dict[str, Any]) -> bool:
        """Send trade exit notification"""
        if not self.config.enabled:
            return False
        
        try:
            symbol = trade_data.get('symbol', 'UNKNOWN')
            instrument_type = trade_data.get('instrument_type', 'UNKNOWN')
            strike_price = trade_data.get('strike_price', 0)
            entry_price = trade_data.get('entry_price', 0)
            exit_price = trade_data.get('exit_price', 0)
            quantity = trade_data.get('quantity', 0)
            pnl = trade_data.get('net_pnl', 0)
            pnl_pct = trade_data.get('pnl_percentage', 0)
            exit_type = trade_data.get('exit_type', 'UNKNOWN')
            strategy = trade_data.get('strategy_name', 'UNKNOWN')
            
            pnl_emoji = "📈" if pnl > 0 else "📉" if pnl < 0 else "⚖️"
            pnl_color = "🟢" if pnl > 0 else "🔴" if pnl < 0 else "🟡"
            
            message = f"""
{pnl_emoji} *TRADE EXIT*

📊 *Symbol*: {symbol}
📈 *Type*: {instrument_type} {strike_price}
💰 *Entry*: ₹{entry_price:.2f}
💰 *Exit*: ₹{exit_price:.2f}
📊 *Quantity*: {quantity}
🎯 *Strategy*: {strategy}
🔄 *Exit Type*: {exit_type}
⏰ *Time*: {to_ist(datetime.now()).strftime('%H:%M:%S IST')}

{pnl_color} *P&L*: ₹{pnl:.2f} ({pnl_pct:+.2f}%)

#Trading #Options #PnL
            """.strip()
            
            return await self.send_message(message)
            
        except Exception as e:
            logger.error(f"Error sending trade exit notification: {e}")
            return False
    
    async def send_pnl_update(self, pnl_data: Dict[str, Any]) -> bool:
        """Send periodic P&L update"""
        if not self.config.enabled:
            return False
        
        try:
            total_pnl = pnl_data.get('total_pnl', 0)
            total_pnl_pct = pnl_data.get('total_pnl_percentage', 0)
            current_capital = pnl_data.get('current_capital', 0)
            initial_capital = pnl_data.get('initial_capital', 0)
            open_positions = pnl_data.get('open_positions', 0)
            trades_today = pnl_data.get('trades_today', 0)
            
            pnl_emoji = "📈" if total_pnl > 0 else "📉" if total_pnl < 0 else "⚖️"
            pnl_color = "🟢" if total_pnl > 0 else "🔴" if total_pnl < 0 else "🟡"
            
            message = f"""
📊 *P&L UPDATE - 30 MINUTES*

{pnl_emoji} *Total P&L*: {pnl_color} ₹{total_pnl:.2f} ({total_pnl_pct:+.2f}%)
💰 *Capital*: ₹{current_capital:.2f} / ₹{initial_capital:.2f}
📈 *Positions Open*: {open_positions}
🔄 *Trades Today*: {trades_today}
⏰ *Time*: {to_ist(datetime.now()).strftime('%H:%M:%S IST')}

#PnL #Trading #SAC
            """.strip()
            
            return await self.send_message(message)
            
        except Exception as e:
            logger.error(f"Error sending P&L update notification: {e}")
            return False

# Global instance
telegram_notifier = None

def get_telegram_notifier() -> TelegramNotifier:
    """Get global Telegram notifier instance"""
    global telegram_notifier
    if telegram_notifier is None:
        telegram_notifier = TelegramNotifier()
    return telegram_notifier
