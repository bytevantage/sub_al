"""
Database Optimization API Endpoints
Monitor database performance and query optimization
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Dict, Any, Optional
from backend.core.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/database", tags=["database"])

@router.get("/optimization-report")
async def get_optimization_report():
    """Get comprehensive database optimization report"""
    try:
        from backend.optimization.database_optimizer import get_database_optimizer
        optimizer = get_database_optimizer()
        
        report = optimizer.generate_optimization_report()
        return report
        
    except Exception as e:
        logger.error(f"Error generating optimization report: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/query-performance")
async def get_query_performance():
    """Get query performance analysis"""
    try:
        from backend.optimization.database_optimizer import get_database_optimizer
        optimizer = get_database_optimizer()
        
        analysis = optimizer.analyze_query_performance()
        return analysis
        
    except Exception as e:
        logger.error(f"Error getting query performance: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/dashboard-performance")
async def get_dashboard_performance():
    """Get dashboard query performance metrics"""
    try:
        from backend.optimization.database_optimizer import get_database_optimizer
        optimizer = get_database_optimizer()
        
        performance = optimizer.optimize_dashboard_queries()
        return performance
        
    except Exception as e:
        logger.error(f"Error getting dashboard performance: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/table-statistics")
async def get_table_statistics():
    """Get database table statistics"""
    try:
        from backend.optimization.database_optimizer import get_database_optimizer
        optimizer = get_database_optimizer()
        
        stats = optimizer.get_table_statistics()
        return stats
        
    except Exception as e:
        logger.error(f"Error getting table statistics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/create-indexes")
async def create_performance_indexes():
    """Create performance indexes for frequently queried fields"""
    try:
        from backend.optimization.database_optimizer import get_database_optimizer
        optimizer = get_database_optimizer()
        
        results = optimizer.create_performance_indexes()
        
        success_count = sum(1 for success in results.values() if success)
        total_count = len(results)
        
        return {
            "status": "completed",
            "message": f"Created {success_count}/{total_count} indexes",
            "results": results,
            "success_rate": f"{(success_count/total_count)*100:.1f}%"
        }
        
    except Exception as e:
        logger.error(f"Error creating indexes: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/cleanup")
async def cleanup_old_data(days_to_keep: int = Query(default=90, ge=0, le=365)):
    """Clean up old data to improve performance"""
    try:
        from backend.optimization.database_optimizer import get_database_optimizer
        optimizer = get_database_optimizer()
        
        if days_to_keep == 0:
            return {
                "status": "skipped",
                "message": "Data cleanup disabled (days_to_keep=0)"
            }
        
        results = optimizer.cleanup_old_data(days_to_keep)
        
        return {
            "status": "completed",
            "message": f"Cleaned up data older than {days_to_keep} days",
            "results": results
        }
        
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/health")
async def get_database_health():
    """Get database health and performance metrics"""
    try:
        from backend.optimization.database_optimizer import get_database_optimizer
        optimizer = get_database_optimizer()
        
        # Get basic statistics
        stats = optimizer.get_table_statistics()
        
        # Check for performance issues
        performance_issues = []
        
        # Check table sizes
        for table, table_stats in stats.items():
            if 'row_count' in table_stats and table_stats['row_count'] > 100000:
                performance_issues.append(f"Large table {table}: {table_stats['row_count']:,} rows")
        
        # Get query performance
        query_analysis = optimizer.analyze_query_performance()
        slow_queries = query_analysis.get('slow_queries', [])
        
        if slow_queries:
            performance_issues.append(f"{len(slow_queries)} slow queries detected")
        
        health_status = "healthy"
        if performance_issues:
            health_status = "warning"
        
        return {
            "status": health_status,
            "timestamp": optimizer.generate_optimization_report()['timestamp'],
            "table_count": len(stats),
            "performance_issues": performance_issues,
            "slow_query_count": len(slow_queries),
            "recommendations": query_analysis.get('recommendations', [])
        }
        
    except Exception as e:
        logger.error(f"Error getting database health: {e}")
        return {
            "status": "error",
            "error": str(e),
            "performance_issues": ["Database health check failed"]
        }
