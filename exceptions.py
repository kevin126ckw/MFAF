"""
Custom exceptions for the MFAF library.
"""

class MFAFError(Exception):
    """Base exception for MFAF-related errors."""
    pass

class MFAFMagicError(MFAFError):
    """Raised when the magic number doesn't match."""
    pass

class MFAFSizeError(MFAFError):
    """Raised when size fields are inconsistent."""
    pass

class MFAFCRCError(MFAFError):
    """Raised when CRC checksum fails."""
    pass

class MFAFRangeError(MFAFError):
    """Raised when offset/size are out of bounds."""
    pass

class MFAFMsgPackError(MFAFError):
    """Raised when MessagePack parsing fails."""
    pass

class MFAFVersionError(MFAFError):
    """Raised when the version is not supported."""
    pass