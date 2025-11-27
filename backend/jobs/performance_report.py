"""
Strategy Performance Analysis & Reporting
"""

import pandas as pd
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from typing import Dict, List, Tuple

from backend.database.database import db
from backend.database.models import Trade
from backend.core.logger import get_logger

logger = get_logger(__name__)

# Performance metrics calculation
METRIC_FUNCTIONS = {
    'total_pnl': lambda group: group['net_pnl'].sum(),
    'avg_pnl': lambda group: group['net_pnl'].mean(),
    'win_rate': lambda group: (group['net_pnl'] > 0).mean(),
    'profit_factor': lambda group: group[group['net_pnl'] > 0]['net_pnl'].sum() / \
                                  abs(group[group['net_pnl'] < 0]['net_pnl'].sum()) \
                                  if any(group['net_pnl'] < 0) else float('inf'),
    'max_drawdown': lambda group: group['net_pnl'].min(),
    'sharpe_ratio': lambda group: group['net_pnl'].mean() / group['net_pnl'].std() \
                                 if group['net_pnl'].std() != 0 else 0,
    'sortino_ratio': lambda group: group['net_pnl'].mean() / \
                                  group[group['net_pnl'] < 0]['net_pnl'].std() \
                                  if any(group['net_pnl'] < 0) else float('inf'),
    'avg_hold_time': lambda group: group['hold_duration_minutes'].mean()
}

def generate_strategy_report(days: int = 30) -> pd.DataFrame:
    """
    Generate comprehensive performance report for all strategies
    
    Args:
        days: Lookback period in days
        
    Returns:
        DataFrame with strategy performance metrics
    """
    session = db.get_session()
    if not session:
        logger.error("Database session not available")
        return pd.DataFrame()
        
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        # Get trades in date range
        trades = session.query(Trade).filter(
            Trade.entry_time >= start_date,
            Trade.entry_time <= end_date
        ).all()
        
        if not trades:
            logger.warning(f"No trades found between {start_date} and {end_date}")
            return pd.DataFrame()
            
        # Create DataFrame
        trade_data = []
        for trade in trades:
            trade_data.append({
                'strategy': trade.strategy_name,
                'symbol': trade.symbol,
                'entry_time': trade.entry_time,
                'exit_time': trade.exit_time,
                'net_pnl': trade.net_pnl,
                'hold_duration_minutes': trade.hold_duration_minutes or 0
            })
        
        df = pd.DataFrame(trade_data)
        
        # Calculate metrics
        results = {}
        for strategy, group in df.groupby('strategy'):
            strategy_metrics = {'trade_count': len(group)}
            for metric_name, metric_func in METRIC_FUNCTIONS.items():
                try:
                    strategy_metrics[metric_name] = metric_func(group)
                except Exception as e:
                    logger.error(f"Error calculating {metric_name} for {strategy}: {e}")
                    strategy_metrics[metric_name] = 0
            
            results[strategy] = strategy_metrics
        
        return pd.DataFrame(results).T.sort_values('total_pnl', ascending=False)
        
    except Exception as e:
        logger.error(f"Error generating strategy report: {e}")
        return pd.DataFrame()
    finally:
        session.close()

def generate_html_report(report_df: pd.DataFrame, filename: str) -> bool:
    """
    Generate interactive HTML performance report
    
    Args:
        report_df: Performance DataFrame from generate_strategy_report()
        filename: Output HTML file path
        
    Returns:
        True if successful
    """
    try:
        from pretty_html_table import build_table
        
        # Prepare styled DataFrame
        styled_df = report_df.reset_index().rename(columns={'index': 'strategy'})
        styled_df = styled_df.style\
            .background_gradient(subset=['total_pnl'], cmap='RdYlGn')\
            .background_gradient(subset=['win_rate'], cmap='RdYlGn')\
            .format({
                'total_pnl': '₹{:.2f}',
                'avg_pnl': '₹{:.2f}',
                'win_rate': '{:.2%}',
                'profit_factor': '{:.2f}x',
                'sharpe_ratio': '{:.2f}',
                'sortino_ratio': '{:.2f}',
                'avg_hold_time': '{:.1f} min'
            })
        
        # Create visualizations
        plt.figure(figsize=(12, 8))
        sns.barplot(data=report_df.reset_index(), 
                   x='total_pnl', y='index', 
                   palette='viridis')
        plt.title('Strategy P&L Comparison')
        plt.xlabel('Total P&L (₹)')
        plt.ylabel('Strategy')
        plt.tight_layout()
        plt.savefig('strategy_pnl_chart.png')
        
        # Generate HTML
        html_content = f"""
        <html>
        <head>
            <title>Strategy Performance Report</title>
            <style>
                body {{ font-family: Arial, sans-serif; }}
                h1 {{ color: #2c3e50; }}
                .container {{ max-width: 1200px; margin: 0 auto; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Strategy Performance Report</h1>
                <h2>Period: {datetime.now().strftime('%Y-%m-%d')}</h2>
                
                <h3>Performance Metrics</h3>
                {build_table(styled_df.render(), 'blue_light')}
                
                <h3>P&L Distribution</h3>
                <img src="strategy_pnl_chart.png" alt="P&L by Strategy">
                
                <h3>Recommendations</h3>
                <ul>
                    <li><strong>Top Performer:</strong> {report_df.index[0]} (₹{report_df.iloc[0].total_pnl:.2f})</li>
                    <li><strong>Most Consistent:</strong> {report_df.sort_values('win_rate', ascending=False).index[0]} ({report_df.sort_values('win_rate', ascending=False).iloc[0].win_rate:.2%} win rate)</li>
                    <li><strong>Efficiency Leader:</strong> {report_df.sort_values('sortino_ratio', ascending=False).index[0]} ({report_df.sort_values('sortino_ratio', ascending=False).iloc[0].sortino_ratio:.2f} Sortino)</li>
                </ul>
            </div>
        </body>
        </html>
        """
        
        with open(filename, 'w') as f:
            f.write(html_content)
            
        return True
        
    except Exception as e:
        logger.error(f"Error generating HTML report: {e}")
        return False
