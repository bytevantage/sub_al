#!/usr/bin/env python3
"""
Create all database tables
Run this to ensure Position table and others exist
"""

import sys
sys.path.insert(0, '/Users/srbhandary/Documents/Projects/srb-algo')

def create_tables():
    """Create all database tables"""
    try:
        print("=" * 80)
        print("Creating Database Tables")
        print("=" * 80)
        print()
        
        from backend.database.database import db
        from backend.database.models import Base, Trade, Position, DailyPerformance, OptionSnapshot
        
        print("Connecting to database...")
        
        if not db.engine:
            print("❌ Database engine not initialized")
            print("\nCheck your database configuration in:")
            print("  - config/config.yaml")
            print("  - Environment variables (DB_HOST, DB_USER, DB_PASSWORD, DB_NAME)")
            return False
        
        print(f"✓ Connected to database: {db.engine.url}")
        print()
        
        print("Creating tables...")
        print(f"  - trades")
        print(f"  - positions (← CRITICAL)")
        print(f"  - daily_performance")
        print(f"  - option_snapshots")
        print()
        
        # Create all tables
        Base.metadata.create_all(db.engine)
        
        print("✓ All tables created successfully")
        print()
        
        # Verify tables exist
        print("Verifying tables...")
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        
        required_tables = ['trades', 'positions', 'daily_performance', 'option_snapshots']
        
        for table in required_tables:
            if table in tables:
                print(f"  ✓ {table}")
            else:
                print(f"  ✗ {table} - MISSING!")
        
        print()
        
        # Check if we can query positions table
        session = db.get_session()
        try:
            from backend.database.models import Position
            count = session.query(Position).count()
            print(f"✓ Position table accessible (currently {count} records)")
        except Exception as e:
            print(f"❌ Error querying Position table: {e}")
            return False
        finally:
            session.close()
        
        print()
        print("=" * 80)
        print("SUCCESS: Database tables ready")
        print("=" * 80)
        print()
        print("Next steps:")
        print("  1. Restart backend: ./stop.sh && ./start.sh")
        print("  2. Test position creation tomorrow")
        print("  3. Verify positions persist to database")
        
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("\nMake sure backend dependencies are installed:")
        print("  pip install -r requirements.txt")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = create_tables()
    sys.exit(0 if success else 1)
