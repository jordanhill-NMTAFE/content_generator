"""
Shared test configuration and fixtures.
This file is automatically loaded by pytest and provides shared setup.
"""

import os
import sys
from pathlib import Path
import shutil

# Add src to Python path for imports
# This ensures tests can import from the src directory
src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

# Import common test utilities
import pytest
from unittest.mock import Mock, patch


# Common fixtures can be defined here
@pytest.fixture
def mock_gpt_client():
    """Mock GPT client to avoid API calls during testing."""
    with patch("gpt.models.openai_.Chat") as mock_client:
        mock_client.return_value = Mock()
        yield mock_client


@pytest.fixture
def temp_test_dir(tmp_path):
    """Create a temporary directory for test outputs."""
    return tmp_path


@pytest.fixture
def sample_config():
    """Sample configuration for testing."""
    return {
        "course_name": "Test Course",
        "course_type": "TAFE",
        "weeks": 20,
        "delivery_mode": "Face-to-face",
        "institution": "Test Institution",
        "student_cohort": "Test Cohort",
        "mission": "Test mission statement",
        "units": [
            {"id": "TEST001", "name": "Test Unit 1"},
            {"id": "TEST002", "name": "Test Unit 2"},
        ],
    }


@pytest.fixture(scope="session", autouse=True)
def clean_test_outputs():
    """Clean the test_outputs directory before running tests."""
    test_outputs_dir = os.path.join(os.getcwd(), "test_outputs")
    if os.path.exists(test_outputs_dir):
        for entry in os.listdir(test_outputs_dir):
            entry_path = os.path.join(test_outputs_dir, entry)
            if os.path.isdir(entry_path):
                shutil.rmtree(entry_path, ignore_errors=True)
            else:
                try:
                    os.remove(entry_path)
                except Exception:
                    pass
