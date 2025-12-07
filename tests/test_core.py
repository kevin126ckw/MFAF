"""
Unit tests for the MFAF core module.
"""

import os
import tempfile
import pytest
from core import MFAFFile, MFAFEntry
from exceptions import MFAFMagicError, MFAFSizeError, MFAFCRCError, MFAFMsgPackError


def test_create_empty_archive():
    """Test creating an empty MFAF archive."""
    mfaf = MFAFFile()
    assert len(mfaf.entries) == 0
    assert mfaf.version == 1
    assert mfaf.flags == 0


def test_add_entry():
    """Test adding an entry to an MFAF archive."""
    mfaf = MFAFFile()
    entry = MFAFEntry("test.txt", b"Hello, World!", "text/plain")
    mfaf.add_entry(entry)
    
    assert len(mfaf.entries) == 1
    assert mfaf.entries[0].name == "test.txt"
    assert mfaf.entries[0].content == b"Hello, World!"
    assert mfaf.entries[0].mime_type == "text/plain"


def test_save_and_load_archive():
    """Test saving and loading an MFAF archive."""
    # Create a temporary file for testing
    with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
        tmp_path = tmp_file.name
    
    try:
        # Create and save archive
        mfaf = MFAFFile()
        entry1 = MFAFEntry("file1.txt", b"Content of file 1", "text/plain")
        entry2 = MFAFEntry("file2.bin", b"\x00\x01\x02\x03", "application/octet-stream")
        mfaf.add_entry(entry1)
        mfaf.add_entry(entry2)
        mfaf.save(tmp_path)
        
        # Load archive
        loaded_mfaf = MFAFFile.load(tmp_path)
        
        # Verify loaded content
        assert len(loaded_mfaf.entries) == 2
        assert loaded_mfaf.entries[0].name == "file1.txt"
        assert loaded_mfaf.entries[0].content == b"Content of file 1"
        assert loaded_mfaf.entries[0].mime_type == "text/plain"
        assert loaded_mfaf.entries[1].name == "file2.bin"
        assert loaded_mfaf.entries[1].content == b"\x00\x01\x02\x03"
        assert loaded_mfaf.entries[1].mime_type == "application/octet-stream"
        
    finally:
        # Clean up temporary file
        os.unlink(tmp_path)


def test_extract_entry():
    """Test extracting an entry from an MFAF archive."""
    # Create a temporary file for testing
    with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
        tmp_path = tmp_file.name
    
    with tempfile.NamedTemporaryFile(delete=False) as extracted_file:
        extracted_path = extracted_file.name
    
    try:
        # Create and save archive
        mfaf = MFAFFile()
        entry = MFAFEntry("test.txt", b"Hello, World!", "text/plain")
        mfaf.add_entry(entry)
        mfaf.save(tmp_path)
        
        # Load archive and extract entry
        loaded_mfaf = MFAFFile.load(tmp_path)
        loaded_mfaf.extract_entry("test.txt", extracted_path)
        
        # Verify extracted content
        with open(extracted_path, 'rb') as f:
            content = f.read()
            assert content == b"Hello, World!"
        
    finally:
        # Clean up temporary files
        os.unlink(tmp_path)
        os.unlink(extracted_path)


def test_list_entries():
    """Test listing entries in an MFAF archive."""
    mfaf = MFAFFile()
    entry1 = MFAFEntry("file1.txt", b"Content 1")
    entry2 = MFAFEntry("file2.txt", b"Content 2")
    entry3 = MFAFEntry("subdir/file3.txt", b"Content 3")
    mfaf.add_entry(entry1)
    mfaf.add_entry(entry2)
    mfaf.add_entry(entry3)
    
    entries = mfaf.list_entries()
    assert len(entries) == 3
    assert "file1.txt" in entries
    assert "file2.txt" in entries
    assert "subdir/file3.txt" in entries


def test_get_entry():
    """Test getting a specific entry from an MFAF archive."""
    mfaf = MFAFFile()
    entry = MFAFEntry("test.txt", b"Hello, World!", "text/plain", {"author": "tester"})
    mfaf.add_entry(entry)
    
    found_entry = mfaf.get_entry("test.txt")
    assert found_entry is not None
    assert found_entry.name == "test.txt"
    assert found_entry.content == b"Hello, World!"
    assert found_entry.mime_type == "text/plain"
    assert found_entry.attributes["author"] == "tester"
    
    # Test non-existent entry
    not_found = mfaf.get_entry("nonexistent.txt")
    assert not_found is None