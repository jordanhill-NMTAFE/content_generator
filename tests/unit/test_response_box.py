#!/usr/bin/env python3
"""
Unit tests for ResponseBox utility class
"""

import sys
import os
import unittest

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from src.gptgen.helpers import ResponseBox


class TestResponseBox(unittest.TestCase):
    """Unit tests for the ResponseBox utility class."""

    def test_wrap_content(self):
        """Test wrapping content in response box."""
        content = "Test content with multiple\nlines and special characters: !@#$%"
        wrapped = ResponseBox.wrap(content, "TEST_BOX")

        self.assertIn("=== TEST_BOX START ===", wrapped)
        self.assertIn("=== TEST_BOX END ===", wrapped)
        self.assertIn(content, wrapped)

    def test_extract_content(self):
        """Test extracting content from response box."""
        content = "Test content with multiple\nlines and special characters: !@#$%"
        wrapped = ResponseBox.wrap(content, "TEST_BOX")
        extracted = ResponseBox.extract(wrapped, "TEST_BOX")

        self.assertEqual(extracted, content)

    def test_extract_from_mixed_content(self):
        """Test extraction from mixed content."""
        content = "Test content with multiple\nlines and special characters: !@#$%"
        wrapped = ResponseBox.wrap(content, "TEST_BOX")
        mixed = f"Preamble\n{wrapped}\nTrailing"
        extracted_mixed = ResponseBox.extract(mixed, "TEST_BOX")

        self.assertEqual(extracted_mixed, content)

    def test_extract_missing_box(self):
        """Test extraction when box doesn't exist."""
        extracted_none = ResponseBox.extract("No box here", "MISSING")
        self.assertIsNone(extracted_none)

    def test_response_box_functionality(self):
        """Test ResponseBox wrap and extract functionality."""
        content = "Test content with multiple\nlines and special characters: !@#$%"

        # Test wrapping
        wrapped = ResponseBox.wrap(content, "TEST_BOX")
        self.assertIn("=== TEST_BOX START ===", wrapped)
        self.assertIn("=== TEST_BOX END ===", wrapped)
        self.assertIn(content, wrapped)

        # Test extraction
        extracted = ResponseBox.extract(wrapped, "TEST_BOX")
        self.assertEqual(extracted, content)

        # Test extraction from mixed content
        mixed = f"Preamble\n{wrapped}\nTrailing"
        extracted_mixed = ResponseBox.extract(mixed, "TEST_BOX")
        self.assertEqual(extracted_mixed, content)

        # Test extraction when box doesn't exist
        extracted_none = ResponseBox.extract("No box here", "MISSING")
        self.assertIsNone(extracted_none)


if __name__ == "__main__":
    unittest.main()
