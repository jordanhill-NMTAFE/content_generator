#!/usr/bin/env python3
"""
Fast tests for checkpointing system functionality
"""

import os
import json
import tempfile
import pytest
from unittest.mock import Mock, patch
import shutil

from src.gptgen.progress import InitProgressManager
from src.gptgen.content_generator import GPTContentGenerator
from src.gptgen.config import CourseConfig


class MockGPTClient:
    """Mock GPT client for testing without making actual API calls."""

    def __init__(self):
        self.call_count = 0

    def prompt(self, prompt_text):
        """Mock prompt method that returns predefined responses."""
        self.call_count += 1

        # Return different responses based on prompt content
        if "COURSE_OVERVIEW" in prompt_text:
            return """=== COURSE_OVERVIEW START ===
This comprehensive course provides students with practical skills and theoretical knowledge.
=== COURSE_OVERVIEW END ==="""
        elif "WEEKLY_TOPICS" in prompt_text:
            return """=== WEEKLY_TOPICS START ===
[
  {
    "week": 1,
    "title": "Introduction",
    "topics": ["Course overview", "Basic principles"],
    "activity": "Group discussion"
  }
]
=== WEEKLY_TOPICS END ==="""
        elif "ASSESSMENTS" in prompt_text:
            return """=== ASSESSMENTS START ===
[
  {
    "title": "Practical Project",
    "description": "Complete a hands-on project.",
    "due_date": "Week 4"
  }
]
=== ASSESSMENTS END ==="""
        elif "ACTIVITIES_WEEK_" in prompt_text:
            return """=== ACTIVITIES_WEEK_1 START ===
Week 1 Learning Activities:
1. Interactive Discussion
2. Hands-on Practice
=== ACTIVITIES_WEEK_1 END ==="""
        elif "RESOURCES_WEEK_" in prompt_text:
            return """=== RESOURCES_WEEK_1 START ===
Week 1 Learning Resources:
- Course textbook
- Online tutorials
=== RESOURCES_WEEK_1 END ==="""
        else:
            return "Mock response"


class TestInitProgressManagerFast:
    """Fast tests for InitProgressManager."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for test files."""
        test_dir = tempfile.mkdtemp()
        yield test_dir
        shutil.rmtree(test_dir)

    @pytest.fixture
    def progress_file(self, temp_dir):
        """Create a progress file path in the temporary directory."""
        return os.path.join(temp_dir, "test_progress.json")

    def test_basic_operations(self, progress_file):
        """Test basic get, set, and mark_done operations."""
        manager = InitProgressManager(progress_file)

        # Test set/get
        manager.set("test_key", "test_value")
        assert manager.get("test_key") == "test_value"
        assert manager.get("non_existent") is None

        # Test mark_done/is_done/get_result
        manager.mark_done("test_task", {"result": "success"})
        assert manager.is_done("test_task") is True
        assert manager.get_result("test_task") == {"result": "success"}
        assert manager.is_done("non_existent") is False

    def test_persistence(self, progress_file):
        """Test that data persists across instances."""
        manager1 = InitProgressManager(progress_file)
        manager1.set("key1", "value1")
        manager1.mark_done("task1", {"result": "success"})

        manager2 = InitProgressManager(progress_file)
        assert manager2.get("key1") == "value1"
        assert manager2.is_done("task1") is True
        assert manager2.get_result("task1") == {"result": "success"}

    def test_reset(self, progress_file):
        """Test reset functionality."""
        manager = InitProgressManager(progress_file)
        manager.set("key1", "value1")
        manager.mark_done("task1", {"result": "success"})

        manager.reset()
        assert manager._data == {}
        assert manager.get("key1") is None
        assert manager.is_done("task1") is False

    def test_corrupted_file_handling(self, progress_file):
        """Test handling of corrupted JSON file."""
        with open(progress_file, "w") as f:
            f.write("{ invalid json }")

        manager = InitProgressManager(progress_file)
        assert manager._data == {}

        # Should still work after corruption
        manager.set("recovery", "works")
        assert manager.get("recovery") == "works"


class TestGPTContentGeneratorCheckpointingFast:
    """Fast tests for GPTContentGenerator checkpointing."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for test files."""
        test_dir = tempfile.mkdtemp()
        yield test_dir
        shutil.rmtree(test_dir)

    @pytest.fixture
    def progress_file(self, temp_dir):
        """Create a progress file path in the temporary directory."""
        return os.path.join(temp_dir, "test_gpt_progress.json")

    def test_progress_manager_initialization(self, progress_file):
        """Test that progress manager is properly initialized."""
        config = CourseConfig(course_type="COMMERCIAL", num_weeks=4)

        # With progress file
        generator = GPTContentGenerator(
            course_config=config, progress_file=progress_file
        )
        assert generator.progress is not None
        assert generator.progress.progress_file == progress_file

        # Without progress file
        generator_no_progress = GPTContentGenerator(course_config=config)
        assert generator_no_progress.progress is None

    @patch("src.gptgen.content_generator.Chat")
    def test_checkpointing_basic_flow(self, mock_chat, progress_file):
        """Test basic checkpointing flow with mock client."""
        mock_client = MockGPTClient()
        mock_chat.return_value = mock_client

        config = CourseConfig(course_type="COMMERCIAL", num_weeks=4)
        generator = GPTContentGenerator(
            course_config=config, progress_file=progress_file
        )

        units = [{"id": "TEST001", "name": "Test Unit 1"}]

        # Initially no progress
        assert generator.progress.is_done("overview") is False

        # Generate overview
        overview = generator.generate_course_overview(units)

        # Should save progress
        assert generator.progress.is_done("overview") is True
        assert generator.progress.get_result("overview") == overview
        assert mock_client.call_count >= 1

    @patch("src.gptgen.content_generator.Chat")
    def test_resume_from_checkpoint(self, mock_chat, progress_file):
        """Test resuming from saved checkpoint."""
        mock_client = MockGPTClient()
        mock_chat.return_value = mock_client

        config = CourseConfig(course_type="COMMERCIAL", num_weeks=4)

        # First generator
        generator1 = GPTContentGenerator(
            course_config=config, progress_file=progress_file
        )
        units = [{"id": "TEST001", "name": "Test Unit 1"}]
        overview1 = generator1.generate_course_overview(units)
        initial_calls = mock_client.call_count

        # Second generator (simulating restart)
        generator2 = GPTContentGenerator(
            course_config=config, progress_file=progress_file
        )
        overview2 = generator2.generate_course_overview(units)

        # Should be same result, no additional API calls
        assert overview1 == overview2
        assert generator2.progress.is_done("overview") is True
        assert mock_client.call_count == initial_calls

    def test_partial_progress_resume(self, progress_file):
        """Test resuming with partial progress."""
        # Create partial progress file
        partial_progress = {
            "overview": {"status": "done", "result": "Pre-generated overview"},
            "weekly_topics": {
                "status": "done",
                "result": [{"week": 1, "title": "Test"}],
            },
        }

        with open(progress_file, "w") as f:
            json.dump(partial_progress, f)

        config = CourseConfig(course_type="COMMERCIAL", num_weeks=4)
        generator = GPTContentGenerator(
            course_config=config, progress_file=progress_file
        )

        units = [{"id": "TEST001", "name": "Test Unit 1"}]

        # Should use saved overview
        overview = generator.generate_course_overview(units)
        assert overview == "Pre-generated overview"

        # Should use saved weekly topics
        weekly_topics = generator.generate_weekly_topics(units)
        assert weekly_topics == [{"week": 1, "title": "Test"}]

        # Should generate new assessments
        assessments = generator.generate_assessment_descriptions(units)
        assert assessments is not None
        assert generator.progress.is_done("assessments") is True

    @patch("src.gptgen.content_generator.Chat")
    def test_all_generation_methods(self, mock_chat, progress_file):
        """Test all generation methods with checkpointing."""
        mock_client = MockGPTClient()
        mock_chat.return_value = mock_client

        config = CourseConfig(course_type="COMMERCIAL", num_weeks=4)
        generator = GPTContentGenerator(
            course_config=config, progress_file=progress_file
        )

        units = [{"id": "TEST001", "name": "Test Unit 1"}]
        weekly_topics_data = [
            {
                "week": 1,
                "title": "Week 1",
                "topics": ["Topic 1"],
                "activity": "Activity 1",
            }
        ]

        # Generate all content types
        overview = generator.generate_course_overview(units)
        weekly_topics = generator.generate_weekly_topics(units)
        assessments = generator.generate_assessment_descriptions(units)
        activities = generator.generate_learning_activities(weekly_topics_data)
        resources = generator.generate_learning_resources(weekly_topics_data)

        # Verify all progress is saved
        assert generator.progress.is_done("overview") is True
        assert generator.progress.is_done("weekly_topics") is True
        assert generator.progress.is_done("assessments") is True
        assert generator.progress.is_done("activities") is True
        assert generator.progress.is_done("resources") is True

        # Verify results match saved progress
        assert generator.progress.get_result("overview") == overview
        assert generator.progress.get_result("weekly_topics") == weekly_topics
        assert generator.progress.get_result("assessments") == assessments
        assert generator.progress.get_result("activities") == activities
        assert generator.progress.get_result("resources") == resources

    @patch("src.gptgen.content_generator.Chat")
    def test_api_failure_fallback(self, mock_chat, progress_file):
        """Test that fallback works when API fails."""
        # Create a mock that fails
        failing_mock = Mock()
        failing_mock.prompt.side_effect = Exception("API Error")
        mock_chat.return_value = failing_mock

        config = CourseConfig(course_type="COMMERCIAL", num_weeks=4)
        generator = GPTContentGenerator(
            course_config=config, progress_file=progress_file
        )

        units = [{"id": "TEST001", "name": "Test Unit 1"}]

        # Should fall back to fallback methods
        overview = generator.generate_course_overview(units)

        # Should still save progress
        assert generator.progress.is_done("overview") is True
        assert generator.progress.get_result("overview") == overview
        assert overview is not None
        assert len(overview) > 0


class TestCheckpointingEdgeCasesFast:
    """Fast tests for edge cases."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for test files."""
        test_dir = tempfile.mkdtemp()
        yield test_dir
        shutil.rmtree(test_dir)

    def test_invalid_file_path(self, temp_dir):
        """Test handling of invalid file paths."""
        invalid_path = os.path.join(temp_dir, "nonexistent", "progress.json")

        # Should handle gracefully
        manager = InitProgressManager(invalid_path)
        manager.set("test", "value")
        assert manager.get("test") == "value"

    def test_empty_file(self, temp_dir):
        """Test handling of empty file."""
        progress_file = os.path.join(temp_dir, "empty_progress.json")

        with open(progress_file, "w") as f:
            f.write("")

        manager = InitProgressManager(progress_file)
        assert manager._data == {}

        manager.set("test", "works")
        assert manager.get("test") == "works"

    def test_large_data(self, temp_dir):
        """Test handling of large data."""
        manager = InitProgressManager(os.path.join(temp_dir, "large_progress.json"))
        # Add large data
        large_data = {"data": "x" * 1000}  # 1KB of data
        for i in range(10):
            manager.set(f"large_key_{i}", large_data)
        assert manager.get("large_key_5") == large_data
        # Persistence is automatic after set()
        manager2 = InitProgressManager(os.path.join(temp_dir, "large_progress.json"))
        assert manager2.get("large_key_5") == large_data
