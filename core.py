"""
Core implementation of the MFAF library.
Provides classes and methods to read, create, and modify MFAF files.
"""

import os
import struct
import msgpack
import zlib
from typing import Dict, List, Any, Optional, Union
from .exceptions import (
    MFAFMagicError, MFAFSizeError, MFAFCRCError, 
    MFAFRangeError, MFAFMsgPackError, MFAFVersionError
)

# Magic numbers
HEADER_MAGIC = b'MAFFILE\x01'
FOOTER_MAGIC = b'ENDMAF\x00\x00'

# Constants
HEADER_SIZE = 64
FOOTER_SIZE = 64


class MFAFEntry:
    """
    Represents a single file entry in an MFAF archive.
    """
    
    def __init__(self, name: str, content: bytes = b'', mime_type: str = 'application/octet-stream', 
                 attributes: Optional[Dict[str, Any]] = None):
        self.name = name
        self.content = content
        self.mime_type = mime_type
        self.attributes = attributes or {}
        self.offset = 0
        self.size = len(content)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert entry to dictionary representation for serialization."""
        result = {
            'n': self.name,
            'o': self.offset,
            's': self.size,
            'm': self.mime_type
        }
        
        if self.attributes:
            result['a'] = self.attributes
            
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MFAFEntry':
        """Create entry from dictionary representation."""
        entry = cls(
            name=data.get('n', ''),
            mime_type=data.get('m', 'application/octet-stream'),
            attributes=data.get('a', {})
        )
        entry.offset = data.get('o', 0)
        entry.size = data.get('s', 0)
        return entry


class MFAFFile:
    """
    Main class for handling MFAF files.
    Provides methods to read, create, and modify MFAF archives.
    """
    
    def __init__(self):
        self.entries: List[MFAFEntry] = []
        self.version = 1
        self.flags = 0
        self.total_size = HEADER_SIZE + FOOTER_SIZE
        
    def add_entry(self, entry: MFAFEntry):
        """Add an entry to the archive."""
        self.entries.append(entry)
        
    def add_file(self, file_path: str, name: Optional[str] = None, 
                 mime_type: str = 'application/octet-stream',
                 attributes: Optional[Dict[str, Any]] = None):
        """
        Add a file from the filesystem to the archive.
        
        Args:
            file_path: Path to the file to add
            name: Name to store the file as in the archive (defaults to filename)
            mime_type: MIME type of the file
            attributes: Additional attributes to store with the file
        """
        if name is None:
            name = os.path.basename(file_path)
            
        with open(file_path, 'rb') as f:
            content = f.read()
            
        entry = MFAFEntry(name, content, mime_type, attributes)
        self.add_entry(entry)
        
    def save(self, file_path: str):
        """
        Save the MFAF archive to a file.
        
        Args:
            file_path: Path where to save the archive
        """
        # Calculate content offset and metadata offset
        content_offset = HEADER_SIZE
        content_size = sum(len(entry.content) for entry in self.entries)
        
        # Set offsets for each entry
        current_offset = content_offset
        for entry in self.entries:
            entry.offset = current_offset
            current_offset += entry.size
            
        metadata_offset = content_offset + content_size
        
        # Serialize metadata
        metadata_list = [entry.to_dict() for entry in self.entries]
        metadata_bytes = msgpack.packb(metadata_list)
        metadata_end = metadata_offset + len(metadata_bytes)
        
        # Calculate total size
        self.total_size = metadata_end + FOOTER_SIZE
        
        # Write the file
        with open(file_path, 'wb') as f:
            # Write header
            header = struct.pack(
                '<8sQQQIHH24x',
                HEADER_MAGIC,
                self.total_size,
                content_offset,
                metadata_offset,
                len(self.entries),
                self.version,
                self.flags
            )
            f.write(header)
            
            # Write content
            for entry in self.entries:
                f.write(entry.content)
                
            # Write metadata
            f.write(metadata_bytes)
            
            # Write footer
            checksum = zlib.crc32(metadata_bytes) & 0xffffffff
            footer = struct.pack(
                '<8sQI44x',
                FOOTER_MAGIC,
                metadata_end,
                checksum
            )
            f.write(footer)
            
    @classmethod
    def load(cls, file_path: str) -> 'MFAFFile':
        """
        Load an MFAF archive from a file.
        
        Args:
            file_path: Path to the MFAF file to load
            
        Returns:
            Loaded MFAFFile instance
        """
        with open(file_path, 'rb') as f:
            # Read header
            header_data = f.read(HEADER_SIZE)
            if len(header_data) < HEADER_SIZE:
                raise MFAFSizeError("File too small to contain a valid header")
                
            header = struct.unpack('<8sQQQIHH24x', header_data)
            
            # Check magic number
            if header[0] != HEADER_MAGIC:
                raise MFAFMagicError("Invalid header magic number")
                
            # Extract header fields
            magic, total_size, content_offset, metadata_offset, file_count, version, flags = header
            
            # Check version
            if version > 1:
                raise MFAFVersionError(f"Unsupported version: {version}")
                
            # Read footer
            f.seek(-FOOTER_SIZE, os.SEEK_END)
            footer_data = f.read(FOOTER_SIZE)
            if len(footer_data) < FOOTER_SIZE:
                raise MFAFSizeError("File too small to contain a valid footer")
                
            footer = struct.unpack('<8sQI44x', footer_data)
            
            # Check footer magic number
            if footer[0] != FOOTER_MAGIC:
                raise MFAFMagicError("Invalid footer magic number")
                
            # Extract footer fields
            footer_magic, metadata_end, checksum = footer
            
            # Validate sizes
            if metadata_offset + (metadata_end - metadata_offset) + FOOTER_SIZE != total_size:
                raise MFAFSizeError("Inconsistent size fields")
                
            # Read metadata
            metadata_length = metadata_end - metadata_offset
            f.seek(metadata_offset)
            metadata_bytes = f.read(metadata_length)
            
            # Verify checksum
            calculated_checksum = zlib.crc32(metadata_bytes) & 0xffffffff
            if calculated_checksum != checksum:
                raise MFAFCRCError("Metadata checksum mismatch")
                
            # Parse metadata
            try:
                metadata_list = msgpack.unpackb(metadata_bytes)
            except Exception as e:
                raise MFAFMsgPackError(f"Failed to parse metadata: {str(e)}")
                
            # Create MFAFFile instance
            mfaf = cls()
            mfaf.version = version
            mfaf.flags = flags
            mfaf.total_size = total_size
            
            # Process entries
            for item in metadata_list:
                entry = MFAFEntry.from_dict(item)
                # Read content
                f.seek(entry.offset)
                entry.content = f.read(entry.size)
                mfaf.entries.append(entry)
                
            return mfaf
            
    def get_entry(self, name: str) -> Optional[MFAFEntry]:
        """
        Get an entry by name.
        
        Args:
            name: Name of the entry to retrieve
            
        Returns:
            The entry if found, None otherwise
        """
        for entry in self.entries:
            if entry.name == name:
                return entry
        return None
        
    def extract_entry(self, name: str, output_path: str):
        """
        Extract an entry to a file.
        
        Args:
            name: Name of the entry to extract
            output_path: Path where to save the extracted file
        """
        entry = self.get_entry(name)
        if not entry:
            raise KeyError(f"Entry '{name}' not found")
            
        with open(output_path, 'wb') as f:
            f.write(entry.content)
            
    def list_entries(self) -> List[str]:
        """
        List all entry names in the archive.
        
        Returns:
            List of entry names
        """
        return [entry.name for entry in self.entries]