"""
Timezone Utilities
Centralized timezone handling for consistent datetime operations
STORAGE: All timestamps stored in UTC (raw)
DISPLAY: All timestamps converted to IST for display/calculations
"""

from datetime import datetime, time, date, timedelta
from zoneinfo import ZoneInfo
from typing import Optional

# Timezone constants
IST = ZoneInfo("Asia/Kolkata")
UTC = ZoneInfo("UTC")


def now_utc() -> datetime:
    """Get current datetime in UTC timezone (for database storage)"""
    return datetime.now(UTC)


def now_ist() -> datetime:
    """Get current datetime in IST timezone (for display/calculations)"""
    return datetime.now(IST)


def utc_to_ist(dt: datetime) -> datetime:
    """
    Convert UTC datetime to IST
    
    Args:
        dt: UTC datetime (can be naive or aware)
    
    Returns:
        IST datetime
    """
    if dt.tzinfo is None:
        # Assume naive datetime is UTC
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(IST)


def ist_to_utc(dt: datetime) -> datetime:
    """
    Convert IST datetime to UTC
    
    Args:
        dt: IST datetime (can be naive or aware)
    
    Returns:
        UTC datetime
    """
    if dt.tzinfo is None:
        # Assume naive datetime is IST
        dt = dt.replace(tzinfo=IST)
    return dt.astimezone(UTC)


def to_utc(dt: datetime) -> datetime:
    """
    Convert any datetime to UTC for database storage
    
    Args:
        dt: datetime to convert (can be naive or aware)
    
    Returns:
        UTC datetime without timezone info (for database storage)
    """
    if dt.tzinfo is None:
        # Assume naive datetime is IST (most common case)
        dt = dt.replace(tzinfo=IST)
    return dt.astimezone(UTC).replace(tzinfo=None)


def to_ist(dt: datetime) -> datetime:
    """
    Convert any datetime to IST for display/calculations
    
    Args:
        dt: datetime to convert (can be naive or aware)
    
    Returns:
        IST datetime with timezone info
    """
    if dt.tzinfo is None:
        # Assume naive datetime from database is UTC
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(IST)


def today_ist() -> date:
    """Get today's date in IST timezone"""
    return datetime.now(IST).date()


def ist_time() -> time:
    """Get current time in IST timezone"""
    return datetime.now(IST).time()


def start_of_day_ist(dt: Optional[date] = None) -> datetime:
    """
    Get start of day (00:00:00) in IST
    
    Args:
        dt: Date to get start of (defaults to today)
    
    Returns:
        datetime at 00:00:00 IST for the given date
    """
    if dt is None:
        dt = today_ist()
    return datetime.combine(dt, time(0, 0, 0)).replace(tzinfo=IST)


def end_of_day_ist(dt: Optional[date] = None) -> datetime:
    """
    Get end of day (23:59:59) in IST
    
    Args:
        dt: Date to get end of (defaults to today)
    
    Returns:
        datetime at 23:59:59 IST for the given date
    """
    if dt is None:
        dt = today_ist()
    return datetime.combine(dt, time(23, 59, 59)).replace(tzinfo=IST)


def is_market_hours() -> bool:
    """
    Check if current time is within market hours (9:15 AM - 3:25 PM IST, Mon-Fri)
    
    Returns:
        True if market is open
    """
    now = datetime.now(IST)
    
    # Check if weekend
    if now.weekday() >= 5:  # Saturday=5, Sunday=6
        return False
    
    # Check market hours
    current_time = now.time()
    market_open = time(9, 15)
    market_close = time(15, 25)  # 3:25 PM IST
    
    return market_open <= current_time <= market_close


def is_after_market_close() -> bool:
    """
    Check if current time is after market close (3:25 PM IST)
    
    Returns:
        True if after market close
    """
    current_time = datetime.now(IST).time()
    return current_time >= time(15, 25)  # 3:25 PM IST


def should_exit_eod() -> bool:
    """
    Check if positions should be closed for end-of-day (after 3:25 PM IST)
    
    Returns:
        True if positions should be closed
    """
    current_time = datetime.now(IST).time()
    return current_time >= time(15, 25)  # 3:25 PM IST


def to_ist(dt: datetime) -> datetime:
    """
    Convert datetime to IST timezone
    
    Args:
        dt: datetime to convert (can be naive or aware)
    
    Returns:
        datetime in IST timezone
    """
    if dt.tzinfo is None:
        # Assume naive datetime is already IST
        return dt.replace(tzinfo=IST)
    else:
        # Convert from other timezone to IST
        return dt.astimezone(IST)


def to_naive_ist(dt: datetime) -> datetime:
    """
    Convert datetime to naive datetime in IST (for database storage)
    
    Args:
        dt: datetime to convert
    
    Returns:
        Naive datetime representing IST time
    """
    if dt.tzinfo is None:
        return dt
    else:
        # Convert to IST and remove timezone info
        ist_dt = dt.astimezone(IST)
        return ist_dt.replace(tzinfo=None)


def format_ist(dt: datetime, fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    """
    Format datetime as string in IST
    
    Args:
        dt: datetime to format
        fmt: strftime format string
    
    Returns:
        Formatted datetime string
    """
    ist_dt = to_ist(dt)
    return ist_dt.strftime(fmt)


def parse_ist(dt_str: str, fmt: str = "%Y-%m-%d %H:%M:%S") -> datetime:
    """
    Parse datetime string as IST
    
    Args:
        dt_str: datetime string to parse
        fmt: strptime format string
    
    Returns:
        datetime in IST timezone
    """
    dt = datetime.strptime(dt_str, fmt)
    return dt.replace(tzinfo=IST)


def ist_isoformat(dt: Optional[datetime] = None) -> str:
    """
    Get ISO format string for datetime in IST
    
    Args:
        dt: datetime to format (defaults to now)
    
    Returns:
        ISO format string with IST timezone
    """
    if dt is None:
        dt = now_ist()
    else:
        dt = to_ist(dt)
    return dt.isoformat()


def market_open_time() -> time:
    """Get market open time (9:15 AM)"""
    return time(9, 15)


def market_close_time() -> time:
    """Get market close time (3:25 PM)"""
    return time(15, 25)


def eod_exit_time() -> time:
    """Get EOD exit time (3:25 PM)"""
    return time(15, 25)


def time_until_market_close() -> Optional[timedelta]:
    """
    Get time remaining until market close
    
    Returns:
        timedelta if market is open, None if market is closed
    """
    if not is_market_hours():
        return None
    
    now = datetime.now(IST)
    market_close = datetime.combine(now.date(), market_close_time()).replace(tzinfo=IST)
    
    return market_close - now


def time_since_market_open() -> Optional[timedelta]:
    """
    Get time elapsed since market open
    
    Returns:
        timedelta if market is/was open today, None otherwise
    """
    now = datetime.now(IST)
    
    # Check if we're past market open today
    market_open = datetime.combine(now.date(), market_open_time()).replace(tzinfo=IST)
    
    if now < market_open:
        return None
    
    return now - market_open
