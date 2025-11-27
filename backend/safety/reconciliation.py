"""
Trade Reconciliation System
Compares database trades with broker statements to detect discrepancies
"""

import csv
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from pathlib import Path

from backend.core.logger import get_logger

logger = get_logger(__name__)


class ReconciliationStatus:
    """Reconciliation match statuses"""
    MATCHED = "matched"
    MISSING_IN_DB = "missing_in_db"
    MISSING_IN_BROKER = "missing_in_broker"
    PRICE_MISMATCH = "price_mismatch"
    QUANTITY_MISMATCH = "quantity_mismatch"


class TradeReconciliation:
    """
    Reconciles database trades with broker statements
    
    Features:
    - Import broker CSV statements
    - Match trades by order ID or timestamp+symbol
    - Detect discrepancies (missing trades, wrong prices)
    - Generate reconciliation reports
    - Alert on mismatches
    """
    
    def __init__(self, config: Dict):
        self.config = config
        
        # Matching settings
        self.time_tolerance_seconds = config.get('time_tolerance_seconds', 60)
        self.price_tolerance_percent = config.get('price_tolerance_percent', 0.5)
        self.quantity_tolerance = config.get('quantity_tolerance', 0)
        
        # Alert settings
        self.alert_on_mismatch = config.get('alert_on_mismatch', True)
        self.alert_callbacks = []
        
        # Reconciliation history
        self.reconciliation_reports = []
        
    def register_alert_callback(self, callback):
        """Register callback for reconciliation alerts"""
        self.alert_callbacks.append(callback)
        
    async def import_broker_statement(
        self,
        csv_path: str,
        broker: str = "upstox"
    ) -> List[Dict]:
        """
        Import trades from broker CSV statement
        
        Args:
            csv_path: Path to broker CSV file
            broker: Broker name (upstox, zerodha, etc.)
            
        Returns:
            List of trade dicts
        """
        trades = []
        
        try:
            with open(csv_path, 'r') as f:
                reader = csv.DictReader(f)
                
                for row in reader:
                    if broker == "upstox":
                        trade = self._parse_upstox_row(row)
                    elif broker == "zerodha":
                        trade = self._parse_zerodha_row(row)
                    else:
                        logger.warning(f"Unknown broker: {broker}")
                        continue
                        
                    if trade:
                        trades.append(trade)
                        
            logger.info(f"Imported {len(trades)} trades from {csv_path}")
            return trades
            
        except Exception as e:
            logger.error(f"Error importing broker statement: {e}")
            return []
            
    def _parse_upstox_row(self, row: Dict) -> Optional[Dict]:
        """Parse Upstox CSV row"""
        try:
            return {
                'order_id': row.get('Order ID', ''),
                'timestamp': datetime.strptime(
                    row.get('Trade Time', ''), '%Y-%m-%d %H:%M:%S'
                ),
                'symbol': row.get('Symbol', ''),
                'side': row.get('Type', ''),  # BUY/SELL
                'quantity': int(row.get('Quantity', 0)),
                'price': float(row.get('Price', 0)),
                'trade_id': row.get('Trade ID', ''),
                'broker': 'upstox'
            }
        except Exception as e:
            logger.error(f"Error parsing Upstox row: {e}")
            return None
            
    def _parse_zerodha_row(self, row: Dict) -> Optional[Dict]:
        """Parse Zerodha CSV row"""
        try:
            return {
                'order_id': row.get('order_id', ''),
                'timestamp': datetime.strptime(
                    row.get('trade_time', ''), '%Y-%m-%d %H:%M:%S'
                ),
                'symbol': row.get('tradingsymbol', ''),
                'side': row.get('trade_type', ''),
                'quantity': int(row.get('quantity', 0)),
                'price': float(row.get('average_price', 0)),
                'trade_id': row.get('trade_id', ''),
                'broker': 'zerodha'
            }
        except Exception as e:
            logger.error(f"Error parsing Zerodha row: {e}")
            return None
            
    async def reconcile_trades(
        self,
        db_trades: List[Dict],
        broker_trades: List[Dict]
    ) -> Dict:
        """
        Reconcile database trades with broker trades
        
        Args:
            db_trades: Trades from database
            broker_trades: Trades from broker statement
            
        Returns:
            Reconciliation report dict
        """
        logger.info(
            f"Starting reconciliation: {len(db_trades)} DB trades, "
            f"{len(broker_trades)} broker trades"
        )
        
        # Match trades
        matched = []
        missing_in_db = []
        missing_in_broker = []
        mismatches = []
        
        # Create lookup maps
        db_by_order_id = {t.get('order_id'): t for t in db_trades if t.get('order_id')}
        broker_by_order_id = {t.get('order_id'): t for t in broker_trades if t.get('order_id')}
        
        # Match by order ID first
        for order_id, db_trade in db_by_order_id.items():
            if order_id in broker_by_order_id:
                broker_trade = broker_by_order_id[order_id]
                
                # Check for mismatches
                match_result = self._compare_trades(db_trade, broker_trade)
                
                if match_result['status'] == ReconciliationStatus.MATCHED:
                    matched.append({
                        'db_trade': db_trade,
                        'broker_trade': broker_trade,
                        'status': ReconciliationStatus.MATCHED
                    })
                else:
                    mismatches.append({
                        'db_trade': db_trade,
                        'broker_trade': broker_trade,
                        'status': match_result['status'],
                        'details': match_result['details']
                    })
                    
                # Remove from broker map (matched)
                del broker_by_order_id[order_id]
            else:
                # Try to match by timestamp + symbol
                fuzzy_match = self._find_fuzzy_match(
                    db_trade, broker_trades
                )
                
                if fuzzy_match:
                    match_result = self._compare_trades(db_trade, fuzzy_match)
                    
                    if match_result['status'] == ReconciliationStatus.MATCHED:
                        matched.append({
                            'db_trade': db_trade,
                            'broker_trade': fuzzy_match,
                            'status': ReconciliationStatus.MATCHED,
                            'matched_by': 'fuzzy'
                        })
                    else:
                        mismatches.append({
                            'db_trade': db_trade,
                            'broker_trade': fuzzy_match,
                            'status': match_result['status'],
                            'details': match_result['details'],
                            'matched_by': 'fuzzy'
                        })
                else:
                    missing_in_broker.append(db_trade)
                    
        # Remaining broker trades are missing in DB
        missing_in_db = list(broker_by_order_id.values())
        
        # Calculate summary
        total_db = len(db_trades)
        total_broker = len(broker_trades)
        matched_count = len(matched)
        mismatch_count = len(mismatches)
        
        match_rate = (matched_count / max(total_db, 1)) * 100
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'summary': {
                'total_db_trades': total_db,
                'total_broker_trades': total_broker,
                'matched': matched_count,
                'mismatches': mismatch_count,
                'missing_in_db': len(missing_in_db),
                'missing_in_broker': len(missing_in_broker),
                'match_rate_percent': round(match_rate, 2)
            },
            'matched_trades': matched,
            'mismatches': mismatches,
            'missing_in_db': missing_in_db,
            'missing_in_broker': missing_in_broker
        }
        
        # Store report
        self.reconciliation_reports.append(report)
        
        # Log summary
        logger.info(
            f"Reconciliation complete:\n"
            f"  Matched: {matched_count}\n"
            f"  Mismatches: {mismatch_count}\n"
            f"  Missing in DB: {len(missing_in_db)}\n"
            f"  Missing in Broker: {len(missing_in_broker)}\n"
            f"  Match rate: {match_rate:.1f}%"
        )
        
        # Alert on issues
        if mismatch_count > 0 or missing_in_db or missing_in_broker:
            await self._trigger_alerts(report)
            
        return report
        
    def _compare_trades(
        self,
        db_trade: Dict,
        broker_trade: Dict
    ) -> Dict:
        """
        Compare two trades for discrepancies
        
        Returns:
            Dict with status and details
        """
        details = []
        
        # Check quantity
        db_qty = db_trade.get('quantity', 0)
        broker_qty = broker_trade.get('quantity', 0)
        
        if abs(db_qty - broker_qty) > self.quantity_tolerance:
            details.append(
                f"Quantity mismatch: DB={db_qty}, Broker={broker_qty}"
            )
            
        # Check price
        db_price = db_trade.get('entry_price') or db_trade.get('price', 0)
        broker_price = broker_trade.get('price', 0)
        
        if broker_price > 0:
            price_diff_percent = abs(db_price - broker_price) / broker_price * 100
            
            if price_diff_percent > self.price_tolerance_percent:
                details.append(
                    f"Price mismatch: DB={db_price:.2f}, "
                    f"Broker={broker_price:.2f} "
                    f"({price_diff_percent:.2f}% difference)"
                )
                
        # Determine status
        if not details:
            status = ReconciliationStatus.MATCHED
        elif 'Quantity mismatch' in details[0]:
            status = ReconciliationStatus.QUANTITY_MISMATCH
        else:
            status = ReconciliationStatus.PRICE_MISMATCH
            
        return {
            'status': status,
            'details': details
        }
        
    def _find_fuzzy_match(
        self,
        db_trade: Dict,
        broker_trades: List[Dict]
    ) -> Optional[Dict]:
        """
        Find fuzzy match by timestamp and symbol
        
        Args:
            db_trade: Database trade
            broker_trades: List of broker trades
            
        Returns:
            Matching broker trade or None
        """
        db_time = db_trade.get('entry_time') or db_trade.get('timestamp')
        if not db_time:
            return None
            
        db_symbol = db_trade.get('symbol', '')
        tolerance = timedelta(seconds=self.time_tolerance_seconds)
        
        for broker_trade in broker_trades:
            broker_time = broker_trade.get('timestamp')
            broker_symbol = broker_trade.get('symbol', '')
            
            if not broker_time:
                continue
                
            # Check symbol match
            if db_symbol != broker_symbol:
                continue
                
            # Check time tolerance
            time_diff = abs(db_time - broker_time)
            if time_diff <= tolerance:
                return broker_trade
                
        return None
        
    async def _trigger_alerts(self, report: Dict):
        """Trigger alerts for reconciliation issues"""
        if not self.alert_on_mismatch:
            return
            
        summary = report['summary']
        
        alert_data = {
            'type': 'reconciliation_alert',
            'timestamp': report['timestamp'],
            'summary': summary,
            'severity': 'high' if summary['missing_in_db'] > 0 else 'medium'
        }
        
        logger.warning(
            f"⚠️ Reconciliation alert:\n"
            f"  Mismatches: {summary['mismatches']}\n"
            f"  Missing in DB: {summary['missing_in_db']}\n"
            f"  Missing in Broker: {summary['missing_in_broker']}"
        )
        
        for callback in self.alert_callbacks:
            try:
                if callable(callback):
                    callback(alert_data)
            except Exception as e:
                logger.error(f"Error in alert callback: {e}")
                
    def generate_report_file(
        self,
        report: Dict,
        output_path: Optional[str] = None
    ) -> str:
        """
        Generate detailed reconciliation report file
        
        Args:
            report: Reconciliation report dict
            output_path: Optional output file path
            
        Returns:
            Path to generated report file
        """
        if not output_path:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_path = f"data/reconciliation_report_{timestamp}.txt"
            
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w') as f:
            f.write("=" * 80 + "\n")
            f.write("TRADE RECONCILIATION REPORT\n")
            f.write("=" * 80 + "\n\n")
            
            # Summary
            summary = report['summary']
            f.write(f"Generated: {report['timestamp']}\n\n")
            f.write("SUMMARY:\n")
            f.write(f"  Database Trades: {summary['total_db_trades']}\n")
            f.write(f"  Broker Trades: {summary['total_broker_trades']}\n")
            f.write(f"  Matched: {summary['matched']}\n")
            f.write(f"  Mismatches: {summary['mismatches']}\n")
            f.write(f"  Missing in DB: {summary['missing_in_db']}\n")
            f.write(f"  Missing in Broker: {summary['missing_in_broker']}\n")
            f.write(f"  Match Rate: {summary['match_rate_percent']}%\n\n")
            
            # Mismatches
            if report['mismatches']:
                f.write("=" * 80 + "\n")
                f.write("MISMATCHES:\n")
                f.write("=" * 80 + "\n\n")
                
                for i, mismatch in enumerate(report['mismatches'], 1):
                    f.write(f"{i}. Status: {mismatch['status']}\n")
                    f.write(f"   DB Trade: {mismatch['db_trade']}\n")
                    f.write(f"   Broker Trade: {mismatch['broker_trade']}\n")
                    f.write(f"   Details: {', '.join(mismatch['details'])}\n\n")
                    
            # Missing in DB
            if report['missing_in_db']:
                f.write("=" * 80 + "\n")
                f.write("MISSING IN DATABASE:\n")
                f.write("=" * 80 + "\n\n")
                
                for i, trade in enumerate(report['missing_in_db'], 1):
                    f.write(f"{i}. {trade}\n")
                    
            # Missing in Broker
            if report['missing_in_broker']:
                f.write("\n" + "=" * 80 + "\n")
                f.write("MISSING IN BROKER STATEMENT:\n")
                f.write("=" * 80 + "\n\n")
                
                for i, trade in enumerate(report['missing_in_broker'], 1):
                    f.write(f"{i}. {trade}\n")
                    
        logger.info(f"Reconciliation report saved to {output_path}")
        return output_path
        
    def get_reconciliation_history(
        self,
        days: int = 7
    ) -> List[Dict]:
        """Get recent reconciliation reports"""
        cutoff = datetime.now() - timedelta(days=days)
        
        return [
            report for report in self.reconciliation_reports
            if datetime.fromisoformat(report['timestamp']) >= cutoff
        ]
