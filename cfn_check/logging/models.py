from async_logging import Entry, LogLevel


class DebugLog(Entry, kw_only=True):
    level: LogLevel = LogLevel.DEBUG

class InfoLog(Entry, kw_only=True):
    level: LogLevel = LogLevel.INFO

class ErrorLog(Entry, kw_only=True):
    error: str | bytes
    level: LogLevel = LogLevel.ERROR

class FatalLog(Entry, kw_only=True):
    error: str | bytes
    level: LogLevel = LogLevel.FATAL

class CriticalLog(Entry, kw_only=True):
    error: str | bytes
    level: LogLevel = LogLevel.CRITICAL