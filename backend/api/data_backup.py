"""
Data Backup API Endpoints
Manage automated data backups and restoration
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks, Query
from typing import Dict, Any, Optional
from datetime import datetime

from backend.core.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/backup", tags=["backup"])

@router.get("/status")
async def get_backup_status():
    """Get backup system status and statistics"""
    try:
        from backend.backup.data_backup import get_backup_manager
        backup_manager = get_backup_manager()
        
        status = backup_manager.get_backup_status()
        return status
        
    except Exception as e:
        logger.error(f"Error getting backup status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/run-daily")
async def run_daily_backup(background_tasks: BackgroundTasks):
    """Run daily backup process"""
    try:
        from backend.backup.data_backup import get_backup_manager
        backup_manager = get_backup_manager()
        
        # Run backup in background
        background_tasks.add_task(backup_manager.run_daily_backup)
        
        return {
            "status": "started",
            "message": "Daily backup process started",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error starting daily backup: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/backup/{backup_type}")
async def run_specific_backup(
    backup_type: str,
    background_tasks: BackgroundTasks
):
    """Run specific backup type"""
    try:
        from backend.backup.data_backup import get_backup_manager
        backup_manager = get_backup_manager()
        
        valid_types = ['clean_regime', 'trades', 'positions', 'config']
        
        if backup_type not in valid_types:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid backup type: {backup_type}. Valid types: {valid_types}"
            )
        
        # Map backup type to function
        backup_functions = {
            'clean_regime': backup_manager.backup_clean_regime_data,
            'trades': backup_manager.backup_trades_data,
            'positions': backup_manager.backup_positions_data,
            'config': backup_manager.backup_config_data
        }
        
        # Run specific backup in background
        background_tasks.add_task(backup_functions[backup_type])
        
        return {
            "status": "started",
            "message": f"{backup_type} backup started",
            "backup_type": backup_type,
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting {backup_type} backup: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/list/{backup_type}")
async def list_backups(backup_type: str, limit: int = Query(default=20, ge=1, le=100)):
    """List available backups for a specific type"""
    try:
        from backend.backup.data_backup import get_backup_manager
        backup_manager = get_backup_manager()
        
        # Map backup type to directory
        backup_dirs = {
            'clean_regime': backup_manager.clean_regime_dir,
            'trades': backup_manager.trades_dir,
            'positions': backup_manager.positions_dir,
            'config': backup_manager.config_dir
        }
        
        if backup_type not in backup_dirs:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid backup type: {backup_type}"
            )
        
        backup_dir = backup_dirs[backup_type]
        backups = []
        
        # List backup files
        for file_path in backup_dir.glob('*'):
            if file_path.is_file():
                stat = file_path.stat()
                backups.append({
                    'filename': file_path.name,
                    'size': stat.st_size,
                    'created': datetime.fromtimestamp(stat.st_ctime).isoformat(),
                    'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    'path': str(file_path)
                })
        
        # Sort by creation date (newest first)
        backups.sort(key=lambda x: x['created'], reverse=True)
        
        return {
            'backup_type': backup_type,
            'total_backups': len(backups),
            'backups': backups[:limit]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing {backup_type} backups: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/restore")
async def restore_from_backup(
    backup_file: str,
    table_name: str,
    background_tasks: BackgroundTasks
):
    """Restore data from backup (emergency use only)"""
    try:
        from backend.backup.data_backup import get_backup_manager
        backup_manager = get_backup_manager()
        
        # Validate table name
        valid_tables = ['clean_regime_2025', 'trades', 'positions']
        
        if table_name not in valid_tables:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid table name: {table_name}. Valid tables: {valid_tables}"
            )
        
        # Run restore in background with safety warning
        logger.warning(f"🚨 RESTORE REQUESTED: {backup_file} to {table_name}")
        
        background_tasks.add_task(backup_manager.restore_from_backup, backup_file, table_name)
        
        return {
            "status": "started",
            "message": f"Restore process started for {table_name}",
            "backup_file": backup_file,
            "table_name": table_name,
            "warning": "This is an emergency operation - verify data integrity",
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting restore: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/cleanup")
async def cleanup_old_backups(background_tasks: BackgroundTasks):
    """Clean up old backup files"""
    try:
        from backend.backup.data_backup import get_backup_manager
        backup_manager = get_backup_manager()
        
        background_tasks.add_task(backup_manager.cleanup_old_backups)
        
        return {
            "status": "started",
            "message": "Backup cleanup process started",
            "retention_days": backup_manager.backup_config['retention_days'],
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error starting backup cleanup: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/configuration")
async def get_backup_configuration():
    """Get backup system configuration"""
    try:
        from backend.backup.data_backup import get_backup_manager
        backup_manager = get_backup_manager()
        
        return {
            "configuration": backup_manager.backup_config,
            "backup_directory": str(backup_manager.backup_dir),
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting backup configuration: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/configure")
async def configure_backup_system(
    clean_regime_data: Optional[bool] = None,
    trades_data: Optional[bool] = None,
    positions_data: Optional[bool] = None,
    config_data: Optional[bool] = None,
    compression: Optional[bool] = None,
    retention_days: Optional[int] = Query(default=30, ge=1, le=365)
):
    """Configure backup system settings"""
    try:
        from backend.backup.data_backup import get_backup_manager
        backup_manager = get_backup_manager()
        
        # Update configuration
        if clean_regime_data is not None:
            backup_manager.backup_config['clean_regime_data'] = clean_regime_data
        if trades_data is not None:
            backup_manager.backup_config['trades_data'] = trades_data
        if positions_data is not None:
            backup_manager.backup_config['positions_data'] = positions_data
        if config_data is not None:
            backup_manager.backup_config['config_data'] = config_data
        if compression is not None:
            backup_manager.backup_config['compression'] = compression
        if retention_days is not None:
            backup_manager.backup_config['retention_days'] = retention_days
        
        logger.info(f"Backup configuration updated: retention_days={retention_days}")
        
        return {
            "status": "success",
            "message": "Backup configuration updated",
            "configuration": backup_manager.backup_config,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error configuring backup system: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/summary")
async def get_backup_summary():
    """Get comprehensive backup summary"""
    try:
        from backend.backup.data_backup import get_backup_manager
        backup_manager = get_backup_manager()
        
        status = backup_manager.get_backup_status()
        
        # Calculate summary metrics
        total_files = sum(status['backup_counts'].values())
        total_size = 0
        
        # Calculate total size (simplified)
        for backup_type, count in status['backup_counts'].items():
            if backup_type in status['latest_backups']:
                latest = status['latest_backups'][backup_type]
                total_size += latest['size'] * count  # Estimate based on latest file size
        
        summary = {
            "backup_system": {
                "status": "active",
                "backup_directory": status['backup_directory'],
                "total_backup_files": total_files,
                "estimated_total_size_mb": round(total_size / (1024 * 1024), 2),
                "retention_days": status['configuration']['retention_days'],
                "compression_enabled": status['configuration']['compression']
            },
            "backup_types": status['backup_counts'],
            "latest_backups": status['latest_backups'],
            "configuration": status['configuration'],
            "health_check": {
                "backup_directory_accessible": backup_manager.backup_dir.exists(),
                "all_subdirectories_created": all([
                    backup_manager.clean_regime_dir.exists(),
                    backup_manager.trades_dir.exists(),
                    backup_manager.positions_dir.exists(),
                    backup_manager.config_dir.exists()
                ])
            },
            "timestamp": datetime.now().isoformat()
        }
        
        return summary
        
    except Exception as e:
        logger.error(f"Error getting backup summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))
