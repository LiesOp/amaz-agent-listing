from datetime import UTC, datetime, timedelta, timezone

APP_TIMEZONE = timezone(timedelta(hours=8), name="UTC+08:00")


def now_app_timezone() -> datetime:
    """Return the current application time in UTC+8."""
    return datetime.now(APP_TIMEZONE)


def convert_utc_to_app_timezone(value: datetime) -> datetime:
    """Convert an existing UTC datetime value to UTC+8."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(APP_TIMEZONE)
