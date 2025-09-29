"""Custom exceptions for the How CLI tool"""


class HowError(Exception):
    """Base exception for all How CLI errors"""
    pass


class ConfigurationError(HowError):
    """Raised when there's an issue with configuration"""
    pass


class APIError(HowError):
    """Raised when there's an issue with API communication"""
    pass


class CommandExecutionError(HowError):
    """Raised when command execution fails"""
    pass


class SafetyError(HowError):
    """Raised when a command is deemed unsafe to execute"""
    pass


class ParseError(HowError):
    """Raised when command parsing fails"""
    pass


class ValidationError(HowError):
    """Raised when input validation fails"""
    pass
