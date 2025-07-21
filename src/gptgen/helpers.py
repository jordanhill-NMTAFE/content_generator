from typing import Optional
import re


# ANSI color codes for logging
class Colors:
    BLUE = "\033[94m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    PURPLE = "\033[95m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    END = "\033[0m"


class ResponseBox:
    """Helper class for structured response boxes."""

    @staticmethod
    def wrap(content: str, box_type: str = "RESPONSE") -> str:
        """Wrap content in a structured response box."""
        return f"""
=== {box_type} START ===
{content}
=== {box_type} END ===
"""

    @staticmethod
    def extract(content: str, box_type: str = "RESPONSE") -> Optional[str]:
        """Extract content from a structured response box."""
        # Try the standard pattern first
        pattern = rf"=== {box_type} START ===\n(.*?)\n=== {box_type} END ==="
        match = re.search(pattern, content, re.DOTALL)
        if match:
            return match.group(1).strip()

        # Fallback: try without newlines around the content
        pattern2 = rf"=== {box_type} START ===(.*?)=== {box_type} END ==="
        match = re.search(pattern2, content, re.DOTALL)
        if match:
            return match.group(1).strip()

        # Fallback: try with different spacing
        pattern3 = rf"=== {box_type} START ===\s*(.*?)\s*=== {box_type} END ==="
        match = re.search(pattern3, content, re.DOTALL)
        if match:
            return match.group(1).strip()

        # If no response box found, return None
        return None
