"""
Database Optimization - Indexes and Query Tuning
Improves performance without changing data structure
"""

import logging
from typing import List, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy import text

from backend.database.database import db
from backend.core.logger import get_logger

logger = get_logger(__name__)

class DatabaseOptimizer:
    """Optimize database performance with indexes and query tuning"""
    
    def __init__(self):
        self.session = db.get_session()
        
        # Critical queries that need optimization
        self.CRITICAL_QUERIES = {
            'trades_by_date': text("""
                SELECT COUNT(*) as query_count, AVG(execution_time) as avg_time
                FROM pg_stat_statements 
                WHERE query LIKE '%Trade%' AND query LIKE '%exit_time%';
            """),
            
            'positions_query': text("""
                SELECT COUNT(*) as query_count, AVG(execution_time) as avg_time
                FROM pg_stat_statements 
                WHERE query LIKE '%position%' AND query LIKE '%unrealized_pnl%';
            """),
            
            'capital_query': text("""
                SELECT COUNT(*) as query_count, AVG(execution_time) as avg_time
                FROM pg_stat_statements 
                WHERE query LIKE '%capital%' AND query LIKE '%pnl%';
            """)
        }
    
    def create_performance_indexes(self) -> Dict[str, bool]:
        """Create indexes for frequently queried fields"""
        
        indexes = {
            # Trade table indexes
            'idx_trades_exit_time': text("""
                CREATE INDEX IF NOT EXISTS idx_trades_exit_time 
                ON trades (exit_time DESC) 
                WHERE exit_time IS NOT NULL
            """),
            
            'idx_trades_symbol_exit': text("""
                CREATE INDEX IF NOT EXISTS idx_trades_symbol_exit 
                ON trades (symbol, exit_time DESC) 
                WHERE exit_time IS NOT NULL
            """),
            
            'idx_trades_status': text("""
                CREATE INDEX IF NOT EXISTS idx_trades_status 
                ON trades (status) 
                WHERE status IN ('OPEN', 'CLOSED')
            """),
            
            'idx_trades_strategy': text("""
                CREATE INDEX IF NOT EXISTS idx_trades_strategy 
                ON trades (strategy, exit_time DESC)
            """),
            
            # Position tracking indexes
            'idx_positions_symbol': text("""
                CREATE INDEX IF NOT EXISTS idx_positions_symbol 
                ON positions (symbol, updated_at DESC)
            """),
            
            'idx_positions_status': text("""
                CREATE INDEX IF NOT EXISTS idx_positions_status 
                ON positions (status, updated_at DESC)
            """),
            
            # Capital/P&L indexes
            'idx_trades_exit_date': text("""
                CREATE INDEX IF NOT EXISTS idx_trades_exit_date 
                ON trades (DATE(exit_time)) 
                WHERE exit_time IS NOT NULL
            """),
            
            # Dashboard performance indexes
            'idx_trades_recent': text("""
                CREATE INDEX IF NOT EXISTS idx_trades_recent 
                ON trades (created_at DESC, exit_time DESC)
            """)
        }
        
        results = {}
        
        for index_name, sql in indexes.items():
            try:
                start_time = datetime.now()
                self.session.execute(sql)
                self.session.commit()
                
                execution_time = (datetime.now() - start_time).total_seconds()
                logger.info(f"✅ Created index {index_name} in {execution_time:.2f}s")
                results[index_name] = True
                
            except Exception as e:
                logger.error(f"❌ Failed to create index {index_name}: {e}")
                results[index_name] = False
        
        return results
    
    def analyze_query_performance(self) -> Dict[str, Any]:
        """Analyze slow queries and suggest optimizations"""
        
        analysis = {
            'slow_queries': [],
            'recommendations': [],
            'index_usage': {}
        }
        
        try:
            # Check for slow queries (> 100ms)
            slow_query_sql = text("""
                SELECT query, calls, total_exec_time, mean_exec_time
                FROM pg_stat_statements 
                WHERE mean_exec_time > 100 
                AND query NOT LIKE '%pg_stat_statements%'
                ORDER BY mean_exec_time DESC 
                LIMIT 10
            """)
            
            result = self.session.execute(slow_query_sql)
            slow_queries = result.fetchall()
            
            for query in slow_queries:
                analysis['slow_queries'].append({
                    'query': query[0][:100] + '...' if len(query[0]) > 100 else query[0],
                    'calls': query[1],
                    'avg_time_ms': round(query[3] * 1000, 2),
                    'total_time_s': round(query[2], 2)
                })
            
            # Check index usage
            index_usage_sql = text("""
                SELECT schemaname, tablename, indexname, idx_scan, idx_tup_read, idx_tup_fetch
                FROM pg_stat_user_indexes 
                WHERE schemaname = 'public'
                ORDER BY idx_scan DESC
            """)
            
            result = self.session.execute(index_usage_sql)
            indexes = result.fetchall()
            
            for index in indexes:
                analysis['index_usage'][index[2]] = {
                    'table': index[1],
                    'scans': index[3],
                    'tuples_read': index[4],
                    'tuples_fetched': index[5]
                }
            
            # Generate recommendations
            if analysis['slow_queries']:
                analysis['recommendations'].append("Consider adding indexes for frequently filtered columns")
            
            unused_indexes = [name for name, stats in analysis['index_usage'].items() if stats['scans'] == 0]
            if unused_indexes:
                analysis['recommendations'].append(f"Remove unused indexes: {', '.join(unused_indexes[:3])}")
            
        except Exception as e:
            logger.error(f"Error analyzing query performance: {e}")
            analysis['error'] = str(e)
        
        return analysis
    
    def optimize_dashboard_queries(self) -> Dict[str, float]:
        """Optimize specific dashboard queries for better performance"""
        
        optimizations = {}
        
        # Test current dashboard query performance
        queries_to_test = {
            'positions_query': text("""
                SELECT symbol, strike, option_type, direction, entry_price, 
                       current_price, unrealized_pnl, strategy
                FROM positions 
                WHERE status = 'OPEN'
                ORDER BY updated_at DESC
            """),
            
            'recent_trades': text("""
                SELECT symbol, strategy, entry_price, exit_price, net_pnl, exit_time
                FROM trades 
                WHERE exit_time >= NOW() - INTERVAL '7 days'
                ORDER BY exit_time DESC 
                LIMIT 20
            """),
            
            'daily_pnl': text("""
                SELECT DATE(exit_time) as date, SUM(net_pnl) as daily_pnl
                FROM trades 
                WHERE exit_time >= NOW() - INTERVAL '30 days'
                GROUP BY DATE(exit_time)
                ORDER BY date DESC
            """)
        }
        
        for query_name, sql in queries_to_test.items():
            try:
                start_time = datetime.now()
                result = self.session.execute(sql)
                rows = result.fetchall()
                
                execution_time = (datetime.now() - start_time).total_seconds()
                optimizations[query_name] = {
                    'execution_time_s': execution_time,
                    'rows_returned': len(rows),
                    'rows_per_second': len(rows) / execution_time if execution_time > 0 else float('inf')
                }
                
                logger.info(f"Query {query_name}: {execution_time:.3f}s for {len(rows)} rows")
                
            except Exception as e:
                logger.error(f"Error testing query {query_name}: {e}")
                optimizations[query_name] = {'error': str(e)}
        
        return optimizations
    
    def get_table_statistics(self) -> Dict[str, Dict]:
        """Get table size and row count statistics"""
        
        stats = {}
        
        tables = ['trades', 'positions', 'option_chain_snapshots']
        
        for table in tables:
            try:
                # Get row count
                count_sql = text(f"SELECT COUNT(*) FROM {table}")
                result = self.session.execute(count_sql)
                row_count = result.fetchone()[0]
                
                # Get table size
                size_sql = text(f"""
                    SELECT pg_size_pretty(pg_total_relation_size('{table}')) as size,
                           pg_size_pretty(pg_relation_size('{table}')) as table_size
                """)
                result = self.session.execute(size_sql)
                sizes = result.fetchone()
                
                stats[table] = {
                    'row_count': row_count,
                    'total_size': sizes[0],
                    'table_size': sizes[1]
                }
                
                logger.info(f"Table {table}: {row_count:,} rows, {sizes[0]}")
                
            except Exception as e:
                logger.error(f"Error getting stats for {table}: {e}")
                stats[table] = {'error': str(e)}
        
        return stats
    
    def cleanup_old_data(self, days_to_keep: int = 90) -> Dict[str, int]:
        """Clean up old data to improve performance (optional)"""
        
        cleanup_results = {}
        
        # Only clean up if explicitly requested
        if days_to_keep <= 0:
            return cleanup_results
        
        try:
            # Archive old trades (keep last N days)
            archive_sql = text(f"""
                DELETE FROM trades 
                WHERE exit_time < NOW() - INTERVAL '{days_to_keep} days'
                AND status = 'CLOSED'
            """)
            
            start_time = datetime.now()
            result = self.session.execute(archive_sql)
            deleted_count = result.rowcount
            self.session.commit()
            
            execution_time = (datetime.now() - start_time).total_seconds()
            cleanup_results['archived_trades'] = deleted_count
            
            logger.info(f"Archived {deleted_count} old trades in {execution_time:.2f}s")
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
            cleanup_results['error'] = str(e)
        
        return cleanup_results
    
    def generate_optimization_report(self) -> Dict[str, Any]:
        """Generate comprehensive database optimization report"""
        
        logger.info("🔍 Generating database optimization report...")
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'indexes': self.create_performance_indexes(),
            'query_analysis': self.analyze_query_performance(),
            'dashboard_performance': self.optimize_dashboard_queries(),
            'table_statistics': self.get_table_statistics(),
            'recommendations': []
        }
        
        # Add specific recommendations based on analysis
        if report['query_analysis'].get('slow_queries'):
            report['recommendations'].append("Identified slow queries - consider additional indexing")
        
        if any(stat.get('row_count', 0) > 100000 for stat in report['table_statistics'].values()):
            report['recommendations'].append("Large tables detected - consider data archiving")
        
        # Add performance recommendations
        slow_dashboard_queries = [
            name for name, perf in report['dashboard_performance'].items()
            if perf.get('execution_time_s', 0) > 0.5
        ]
        
        if slow_dashboard_queries:
            report['recommendations'].append(f"Slow dashboard queries: {', '.join(slow_dashboard_queries)}")
        
        return report
    
    def close(self):
        """Close database session"""
        if self.session:
            self.session.close()

# Global optimizer instance
_optimizer = None

def get_database_optimizer() -> DatabaseOptimizer:
    """Get global database optimizer instance"""
    global _optimizer
    if _optimizer is None:
        _optimizer = DatabaseOptimizer()
    return _optimizer
