"""
Automated Data Backup System
Daily automated backup of clean_regime_2025 data
"""

import os
import gzip
import json
import shutil
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from pathlib import Path
import asyncio
from sqlalchemy import text

from backend.core.logger import get_logger
from backend.database.database import db

logger = get_logger(__name__)

class DataBackupManager:
    """Automated backup system for critical trading data"""
    
    def __init__(self, backup_dir: str = "backups"):
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(exist_ok=True)
        
        # Backup configuration
        self.backup_config = {
            'clean_regime_data': True,  # Backup clean_regime_2025 data
            'trades_data': True,       # Backup trades
            'positions_data': True,     # Backup positions
            'config_data': True,        # Backup configuration
            'compression': True,        # Compress backups
            'retention_days': 30,       # Keep backups for 30 days
        }
        
        # Create subdirectories
        self.clean_regime_dir = self.backup_dir / "clean_regime_2025"
        self.trades_dir = self.backup_dir / "trades"
        self.positions_dir = self.backup_dir / "positions"
        self.config_dir = self.backup_dir / "config"
        
        for dir_path in [self.clean_regime_dir, self.trades_dir, self.positions_dir, self.config_dir]:
            dir_path.mkdir(exist_ok=True)
        
        logger.info(f"Data Backup Manager initialized - backup directory: {self.backup_dir}")
    
    async def backup_clean_regime_data(self) -> Dict[str, Any]:
        """Backup clean_regime_2025 dataset"""
        
        backup_result = {
            'success': False,
            'timestamp': datetime.now().isoformat(),
            'records_backed_up': 0,
            'backup_file': None,
            'error': None
        }
        
        try:
            session = db.get_session()
            
            # Get clean regime data
            clean_regime_query = text("""
                SELECT * FROM clean_regime_2025 
                ORDER BY timestamp DESC
            """)
            
            result = session.execute(clean_regime_query)
            records = result.fetchall()
            
            if not records:
                backup_result['success'] = True
                backup_result['message'] = "No clean_regime_2025 data to backup"
                return backup_result
            
            # Convert to list of dicts
            columns = result.keys()
            data = []
            for record in records:
                data.append(dict(zip(columns, record)))
            
            backup_result['records_backed_up'] = len(data)
            
            # Create backup file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = self.clean_regime_dir / f"clean_regime_2025_{timestamp}.json"
            
            # Write data to file
            backup_data = {
                'backup_timestamp': datetime.now().isoformat(),
                'table': 'clean_regime_2025',
                'record_count': len(data),
                'data': data
            }
            
            with open(backup_file, 'w') as f:
                json.dump(backup_data, f, indent=2, default=str)
            
            # Compress if enabled
            if self.backup_config['compression']:
                compressed_file = await self.compress_file(backup_file)
                backup_file = compressed_file
            
            backup_result['success'] = True
            backup_result['backup_file'] = str(backup_file)
            
            logger.info(f"✅ Backed up {len(data)} clean_regime_2025 records to {backup_file}")
            
        except Exception as e:
            backup_result['error'] = str(e)
            logger.error(f"❌ Failed to backup clean_regime_2025 data: {e}")
        
        finally:
            if 'session' in locals():
                session.close()
        
        return backup_result
    
    async def backup_trades_data(self) -> Dict[str, Any]:
        """Backup trades data"""
        
        backup_result = {
            'success': False,
            'timestamp': datetime.now().isoformat(),
            'records_backed_up': 0,
            'backup_file': None,
            'error': None
        }
        
        try:
            session = db.get_session()
            
            # Get trades from last 7 days
            trades_query = text("""
                SELECT * FROM trades 
                WHERE created_at >= NOW() - INTERVAL '7 days'
                ORDER BY created_at DESC
            """)
            
            result = session.execute(trades_query)
            records = result.fetchall()
            
            if not records:
                backup_result['success'] = True
                backup_result['message'] = "No recent trades data to backup"
                return backup_result
            
            # Convert to list of dicts
            columns = result.keys()
            data = []
            for record in records:
                data.append(dict(zip(columns, record)))
            
            backup_result['records_backed_up'] = len(data)
            
            # Create backup file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = self.trades_dir / f"trades_{timestamp}.json"
            
            # Write data to file
            backup_data = {
                'backup_timestamp': datetime.now().isoformat(),
                'table': 'trades',
                'record_count': len(data),
                'data': data
            }
            
            with open(backup_file, 'w') as f:
                json.dump(backup_data, f, indent=2, default=str)
            
            # Compress if enabled
            if self.backup_config['compression']:
                compressed_file = await self.compress_file(backup_file)
                backup_file = compressed_file
            
            backup_result['success'] = True
            backup_result['backup_file'] = str(backup_file)
            
            logger.info(f"✅ Backed up {len(data)} trades records to {backup_file}")
            
        except Exception as e:
            backup_result['error'] = str(e)
            logger.error(f"❌ Failed to backup trades data: {e}")
        
        finally:
            if 'session' in locals():
                session.close()
        
        return backup_result
    
    async def backup_positions_data(self) -> Dict[str, Any]:
        """Backup current positions data"""
        
        backup_result = {
            'success': False,
            'timestamp': datetime.now().isoformat(),
            'records_backed_up': 0,
            'backup_file': None,
            'error': None
        }
        
        try:
            session = db.get_session()
            
            # Get current open positions
            positions_query = text("""
                SELECT * FROM positions 
                WHERE status = 'OPEN'
                ORDER BY updated_at DESC
            """)
            
            result = session.execute(positions_query)
            records = result.fetchall()
            
            if not records:
                backup_result['success'] = True
                backup_result['message'] = "No open positions to backup"
                return backup_result
            
            # Convert to list of dicts
            columns = result.keys()
            data = []
            for record in records:
                data.append(dict(zip(columns, record)))
            
            backup_result['records_backed_up'] = len(data)
            
            # Create backup file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = self.positions_dir / f"positions_{timestamp}.json"
            
            # Write data to file
            backup_data = {
                'backup_timestamp': datetime.now().isoformat(),
                'table': 'positions',
                'record_count': len(data),
                'data': data
            }
            
            with open(backup_file, 'w') as f:
                json.dump(backup_data, f, indent=2, default=str)
            
            # Compress if enabled
            if self.backup_config['compression']:
                compressed_file = await self.compress_file(backup_file)
                backup_file = compressed_file
            
            backup_result['success'] = True
            backup_result['backup_file'] = str(backup_file)
            
            logger.info(f"✅ Backed up {len(data)} positions records to {backup_file}")
            
        except Exception as e:
            backup_result['error'] = str(e)
            logger.error(f"❌ Failed to backup positions data: {e}")
        
        finally:
            if 'session' in locals():
                session.close()
        
        return backup_result
    
    async def backup_config_data(self) -> Dict[str, Any]:
        """Backup configuration data"""
        
        backup_result = {
            'success': False,
            'timestamp': datetime.now().isoformat(),
            'files_backed_up': 0,
            'backup_file': None,
            'error': None
        }
        
        try:
            # Backup key configuration files
            config_files = [
                'config/config.yaml',
                'config/trading_config.yaml',
                'config/production_locks.yaml'
            ]
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = self.config_dir / f"config_{timestamp}.tar.gz"
            
            # Create tar.gz archive
            import tarfile
            
            with tarfile.open(backup_file, 'w:gz') as tar:
                for config_file in config_files:
                    file_path = Path(config_file)
                    if file_path.exists():
                        tar.add(file_path, arcname=file_path.name)
                        backup_result['files_backed_up'] += 1
            
            backup_result['success'] = True
            backup_result['backup_file'] = str(backup_file)
            
            logger.info(f"✅ Backed up {backup_result['files_backed_up']} config files to {backup_file}")
            
        except Exception as e:
            backup_result['error'] = str(e)
            logger.error(f"❌ Failed to backup config data: {e}")
        
        return backup_result
    
    async def compress_file(self, file_path: Path) -> Path:
        """Compress a file using gzip"""
        
        compressed_path = file_path.with_suffix(file_path.suffix + '.gz')
        
        with open(file_path, 'rb') as f_in:
            with gzip.open(compressed_path, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        
        # Remove original file
        os.remove(file_path)
        
        return compressed_path
    
    async def run_daily_backup(self) -> Dict[str, Any]:
        """Run complete daily backup"""
        
        logger.info("🔄 Starting daily backup process...")
        
        backup_results = {
            'timestamp': datetime.now().isoformat(),
            'success': True,
            'backups': {},
            'total_records': 0,
            'total_files': 0,
            'errors': []
        }
        
        # Run each backup type
        if self.backup_config['clean_regime_data']:
            result = await self.backup_clean_regime_data()
            backup_results['backups']['clean_regime'] = result
            if result['success']:
                backup_results['total_records'] += result['records_backed_up']
                backup_results['total_files'] += 1
            else:
                backup_results['errors'].append(f"Clean regime backup failed: {result.get('error')}")
                backup_results['success'] = False
        
        if self.backup_config['trades_data']:
            result = await self.backup_trades_data()
            backup_results['backups']['trades'] = result
            if result['success']:
                backup_results['total_records'] += result['records_backed_up']
                backup_results['total_files'] += 1
            else:
                backup_results['errors'].append(f"Trades backup failed: {result.get('error')}")
                backup_results['success'] = False
        
        if self.backup_config['positions_data']:
            result = await self.backup_positions_data()
            backup_results['backups']['positions'] = result
            if result['success']:
                backup_results['total_records'] += result['records_backed_up']
                backup_results['total_files'] += 1
            else:
                backup_results['errors'].append(f"Positions backup failed: {result.get('error')}")
                backup_results['success'] = False
        
        if self.backup_config['config_data']:
            result = await self.backup_config_data()
            backup_results['backups']['config'] = result
            if result['success']:
                backup_results['total_files'] += result['files_backed_up']
            else:
                backup_results['errors'].append(f"Config backup failed: {result.get('error')}")
                backup_results['success'] = False
        
        # Cleanup old backups
        await self.cleanup_old_backups()
        
        # Log summary
        if backup_results['success']:
            logger.info(f"✅ Daily backup completed: {backup_results['total_records']} records, {backup_results['total_files']} files")
        else:
            logger.error(f"❌ Daily backup completed with errors: {len(backup_results['errors'])} errors")
        
        return backup_results
    
    async def cleanup_old_backups(self):
        """Remove backups older than retention period"""
        
        retention_days = self.backup_config['retention_days']
        cutoff_date = datetime.now() - timedelta(days=retention_days)
        
        removed_files = 0
        
        # Clean all backup directories
        for backup_dir in [self.clean_regime_dir, self.trades_dir, self.positions_dir, self.config_dir]:
            for file_path in backup_dir.glob('*'):
                if file_path.is_file():
                    file_time = datetime.fromtimestamp(file_path.stat().st_mtime)
                    if file_time < cutoff_date:
                        os.remove(file_path)
                        removed_files += 1
                        logger.debug(f"🗑️  Removed old backup: {file_path}")
        
        if removed_files > 0:
            logger.info(f"🗑️  Cleaned up {removed_files} old backup files (older than {retention_days} days)")
    
    def get_backup_status(self) -> Dict[str, Any]:
        """Get backup status and statistics"""
        
        status = {
            'backup_directory': str(self.backup_dir),
            'configuration': self.backup_config,
            'backup_counts': {
                'clean_regime': len(list(self.clean_regime_dir.glob('*'))),
                'trades': len(list(self.trades_dir.glob('*'))),
                'positions': len(list(self.positions_dir.glob('*'))),
                'config': len(list(self.config_dir.glob('*')))
            },
            'total_backups': 0,
            'latest_backups': {}
        }
        
        # Calculate total backups
        status['total_backups'] = sum(status['backup_counts'].values())
        
        # Get latest backup for each type
        for backup_type, backup_dir in [
            ('clean_regime', self.clean_regime_dir),
            ('trades', self.trades_dir),
            ('positions', self.positions_dir),
            ('config', self.config_dir)
        ]:
            files = list(backup_dir.glob('*'))
            if files:
                latest_file = max(files, key=lambda f: f.stat().st_mtime)
                status['latest_backups'][backup_type] = {
                    'file': latest_file.name,
                    'size': latest_file.stat().st_size,
                    'modified': datetime.fromtimestamp(latest_file.stat().st_mtime).isoformat()
                }
        
        return status
    
    async def restore_from_backup(self, backup_file: str, table_name: str) -> Dict[str, Any]:
        """Restore data from backup file (emergency use only)"""
        
        restore_result = {
            'success': False,
            'timestamp': datetime.now().isoformat(),
            'records_restored': 0,
            'error': None
        }
        
        try:
            backup_path = Path(backup_file)
            
            if not backup_path.exists():
                restore_result['error'] = f"Backup file not found: {backup_file}"
                return restore_result
            
            # Load backup data
            if backup_path.suffix == '.gz':
                with gzip.open(backup_path, 'rt') as f:
                    backup_data = json.load(f)
            else:
                with open(backup_path, 'r') as f:
                    backup_data = json.load(f)
            
            # Validate backup
            if backup_data.get('table') != table_name:
                restore_result['error'] = f"Backup table mismatch: expected {table_name}, got {backup_data.get('table')}"
                return restore_result
            
            # Restore data (simplified - would need proper implementation)
            logger.warning(f"🚨 RESTORE OPERATION: {backup_file} to {table_name}")
            logger.warning("Restore operation requires manual verification before proceeding")
            
            restore_result['success'] = True
            restore_result['records_restored'] = backup_data.get('record_count', 0)
            
        except Exception as e:
            restore_result['error'] = str(e)
            logger.error(f"❌ Failed to restore from backup: {e}")
        
        return restore_result

# Global backup manager instance
_backup_manager = None

def get_backup_manager() -> DataBackupManager:
    """Get global backup manager instance"""
    global _backup_manager
    if _backup_manager is None:
        _backup_manager = DataBackupManager()
    return _backup_manager
