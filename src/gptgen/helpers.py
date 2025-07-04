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
        pattern = rf"=== {box_type} START ===\n(.*?)\n=== {box_type} END ==="
        match = re.search(pattern, content, re.DOTALL)
        return match.group(1).strip() if match else None
