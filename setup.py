#!/usr/bin/env python3
"""
Quick Setup Script
Prepares the environment and runs the trading system
"""

import os
import sys
from pathlib import Path
import subprocess


def print_banner():
    """Print welcome banner"""
    print("=" * 70)
    print("🚀  ADVANCED OPTIONS TRADING SYSTEM - QUICK SETUP  🚀")
    print("=" * 70)
    print()


def check_python_version():
    """Check Python version"""
    print("✓ Checking Python version...")
    if sys.version_info < (3, 10):
        print("❌ Python 3.10+ required")
        sys.exit(1)
    print(f"  Python {sys.version_info.major}.{sys.version_info.minor} detected")
    print()


def check_token():
    """Check if Upstox token exists"""
    print("✓ Checking Upstox token...")
    
    token_paths = [
        Path("config/upstox_token.json"),
        Path.home() / "Algo" / "upstoxtoken.json"
    ]
    
    for path in token_paths:
        if path.exists():
            print(f"  Token found: {path}")
            return True
    
    print("⚠️  No Upstox token found!")
    print("   Please run: python upstox_auth_working.py")
    print()
    return False


def create_env_file():
    """Create .env file if it doesn't exist"""
    print("✓ Setting up environment...")
    
    env_file = Path(".env")
    if not env_file.exists():
        example = Path(".env.example")
        if example.exists():
            import shutil
            shutil.copy(example, env_file)
            print("  Created .env file from template")
        else:
            # Create minimal .env
            with open(env_file, 'w') as f:
                f.write("MODE=paper\n")
                f.write("INITIAL_CAPITAL=100000\n")
                f.write("RISK_PERCENT=3\n")
                f.write("MIN_SIGNAL_STRENGTH=75\n")
            print("  Created minimal .env file")
    else:
        print("  .env file already exists")
    print()


def check_dependencies():
    """Check if dependencies are installed"""
    print("✓ Checking dependencies...")
    
    try:
        import fastapi
        import uvicorn
        import pandas
        print("  Core dependencies installed")
        return True
    except ImportError:
        print("⚠️  Some dependencies missing")
        print("   Installing dependencies...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("  ✓ Dependencies installed")
        return True


def create_directories():
    """Create necessary directories"""
    print("✓ Creating directories...")
    
    dirs = [
        "data/logs",
        "data/trades",
        "data/historical",
        "models",
        "config"
    ]
    
    for dir_path in dirs:
        Path(dir_path).mkdir(parents=True, exist_ok=True)
    
    print(f"  Created {len(dirs)} directories")
    print()


def run_system():
    """Run the trading system"""
    print("=" * 70)
    print("🎯  STARTING TRADING SYSTEM")
    print("=" * 70)
    print()
    print("Mode: PAPER TRADING (Safe)")
    print("API: http://localhost:8000")
    print("Logs: data/logs/")
    print()
    print("Press Ctrl+C to stop")
    print("-" * 70)
    print()
    
    try:
        # Run with uvicorn
        subprocess.run([
            sys.executable, "-m", "uvicorn",
            "backend.main:app",
            "--host", "0.0.0.0",
            "--port", "8000",
            "--reload"
        ])
    except KeyboardInterrupt:
        print("\n\n✓ Trading system stopped")


def main():
    """Main setup function"""
    print_banner()
    
    check_python_version()
    create_directories()
    create_env_file()
    
    if not check_token():
        print("⚠️  Warning: No token found. System may not connect to Upstox.")
        print("   Continue anyway? (y/n): ", end="")
        response = input().strip().lower()
        if response != 'y':
            print("   Please run: python upstox_auth_working.py")
            return
        print()
    
    check_dependencies()
    
    print("✅  Setup complete!")
    print()
    
    # Ask to start
    print("Start trading system now? (y/n): ", end="")
    response = input().strip().lower()
    
    if response == 'y':
        print()
        run_system()
    else:
        print("\nTo start later, run:")
        print("  python backend/main.py")
        print("  or")
        print("  uvicorn backend.main:app --reload")


if __name__ == "__main__":
    main()
