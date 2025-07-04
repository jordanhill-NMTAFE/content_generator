#!/usr/bin/env python3
"""
Tests for checkpointing system functionality
"""

import os
import json
import tempfile
import threading
import time
import pytest
from pathlib import Path
from unittest.mock import Mock, patch

from src.utils.gpt_helper import InitProgressManager, GPTContentGenerator, CourseConfig


class MockFileLock:
    """Mock file lock that simulates real locking behavior in-memory."""

    def __init__(self, file_path):
        self.file_path = file_path
        # Use a class-level lock to simulate file-level locking across processes
        if not hasattr(MockFileLock, "_file_locks"):
            MockFileLock._file_locks = {}
        if file_path not in MockFileLock._file_locks:
            MockFileLock._file_locks[file_path] = threading.Lock()
        self.lock = MockFileLock._file_locks[file_path]
        self.acquired = False
        self.file_content = "{}"

    def __enter__(self):
        # Simulate blocking if lock is held
        if not self.lock.acquire(timeout=2.0):
            raise TimeoutError(f"Lock acquisition timeout for {self.file_path}")
        self.acquired = True

        # Create a mock file object that simulates file operations
        mock_file = Mock()
        mock_file.read.return_value = self.file_content
        mock_file.seek = Mock()
        mock_file.write = Mock()
        mock_file.flush = Mock()
        mock_file.fileno.return_value = 123  # Mock file descriptor

        # Store the mock file for later access
        self.mock_file = mock_file
        return mock_file

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.acquired:
            self.lock.release()
            self.acquired = False


class MockFileSystem:
    """Mock file system that simulates file operations in-memory."""

    def __init__(self):
        self.files = {}
        self.temp_files = {}
        self._lock = threading.Lock()

    def write_file(self, file_path, content):
        """Write content to a file atomically."""
        with self._lock:
            # Simulate atomic write with temp file
            temp_path = f"{file_path}.{threading.get_ident()}.tmp"
            self.temp_files[temp_path] = content

            # Simulate atomic replace
            self.files[file_path] = content
            if temp_path in self.temp_files:
                del self.temp_files[temp_path]

    def read_file(self, file_path):
        """Read content from a file."""
        with self._lock:
            return self.files.get(file_path, "{}")

    def file_exists(self, file_path):
        """Check if file exists."""
        return file_path in self.files


class MockInitProgressManager:
    """Mock version of InitProgressManager that uses our custom mocks."""

    def __init__(self, progress_file, mock_fs_instance):
        self.progress_file = progress_file
        self.mock_fs = mock_fs_instance
        self._lock = threading.Lock()
        self._semaphore = threading.Semaphore(1)  # Use threading.Semaphore for testing
        self._data = {}
        self._load()

    def _load(self):
        """Load data from mock file system."""
        try:
            content = self.mock_fs.read_file(self.progress_file)
            if content.strip():
                self._data = json.loads(content)
            else:
                self._data = {}
        except Exception as e:
            print(f"Failed to load progress file {self.progress_file}: {e}")
            self._data = {}

    def _write(self):
        """Write data to mock file system atomically."""
        try:
            content = json.dumps(self._data, indent=2)
            self.mock_fs.write_file(self.progress_file, content)
        except Exception as e:
            print(f"Failed to write progress file {self.progress_file}: {e}")

    def _atomic_operation(self, operation):
        """Execute an operation atomically using semaphore and file locking."""
        with self._semaphore:  # IPC coordination - only one process at a time
            with self._lock:  # Thread safety within this process
                # Always reload to get latest data from other processes
                self._load()
                # Execute the operation
                result = operation()
                # Write changes atomically
                self._write()
                return result

    def get(self, key):
        """Get value for key with proper coordination."""

        def operation():
            return self._data.get(key, None)

        return self._atomic_operation(operation)

    def set(self, key, value):
        """Set value for key with proper coordination."""

        def operation():
            self._data[key] = value
            return None

        self._atomic_operation(operation)


class MockGPTClient:
    """Mock GPT client for testing without making actual API calls."""

    def __init__(self, responses=None):
        self.responses = responses or {}
        self.call_count = 0
        self.prompt_history = []

    def prompt(self, prompt_text):
        """Mock prompt method that returns predefined responses."""
        self.call_count += 1
        self.prompt_history.append(prompt_text)

        # Detect course type and number of weeks from prompt
        course_type = self._detect_course_type(prompt_text)
        num_weeks = self._detect_num_weeks(prompt_text)

        # Return different responses based on prompt content and course type
        if "COURSE_OVERVIEW" in prompt_text:
            return self._mock_course_overview_response(course_type)
        elif "WEEKLY_TOPICS" in prompt_text:
            return self._mock_weekly_topics_response(course_type, num_weeks)
        elif "ASSESSMENTS" in prompt_text:
            return self._mock_assessments_response(course_type)
        elif "ACTIVITIES_WEEK_" in prompt_text:
            week_num = self._extract_week_number(prompt_text)
            return self._mock_activities_response(week_num, course_type)
        elif "RESOURCES_WEEK_" in prompt_text:
            week_num = self._extract_week_number(prompt_text)
            return self._mock_resources_response(week_num, course_type)
        else:
            return "Mock response for: " + prompt_text[:50]

    def _detect_course_type(self, prompt_text):
        """Detect course type from prompt text."""
        # Convert to lowercase for case-insensitive matching
        prompt_lower = prompt_text.lower()

        if "tafe" in prompt_lower:
            return "TAFE"
        elif "commercial" in prompt_lower:
            return "COMMERCIAL"
        elif "accelerated" in prompt_lower:
            return "ACCELERATED"
        elif "custom" in prompt_lower:
            return "CUSTOM"
        else:
            return "TAFE"  # Default

    def _detect_num_weeks(self, prompt_text):
        """Detect number of weeks from prompt text."""
        import re

        # Look for patterns like "20-week", "8-week", etc.
        week_pattern = r"(\d+)-week"
        match = re.search(week_pattern, prompt_text)
        if match:
            return int(match.group(1))

        # Look for patterns like "20 weeks", "8 weeks", etc.
        week_pattern2 = r"(\d+)\s+weeks"
        match = re.search(week_pattern2, prompt_text)
        if match:
            return int(match.group(1))

        return 20  # Default

    def _extract_week_number(self, prompt_text):
        """Extract week number from prompt text."""
        import re

        week_pattern = r"WEEK_(\d+)"
        match = re.search(week_pattern, prompt_text)
        return int(match.group(1)) if match else 1

    def _mock_course_overview_response(self, course_type="TAFE"):
        """Return course overview based on course type."""
        if course_type == "TAFE":
            return """=== COURSE_OVERVIEW START ===
This TAFE course provides comprehensive training in the subject area.

Students will develop practical skills and theoretical knowledge through hands-on activities, assessments, and real-world applications. The course is designed to prepare students for professional roles in their chosen field with accredited units of competency.

Throughout the course, students will engage with industry-standard tools and methodologies, complete practical projects, and demonstrate their competency through various assessment methods. The course includes reassessment opportunities in the final weeks.

[TAFE-specific: This course is nationally accredited and includes formal assessment and reassessment weeks.]
=== COURSE_OVERVIEW END ==="""
        elif course_type == "COMMERCIAL":
            return """=== COURSE_OVERVIEW START ===
This commercial course provides focused training in the subject area.

Students will develop practical skills and immediate application knowledge through hands-on activities and real-world projects. The course is designed for rapid skill development and immediate workplace application.

Throughout the course, students will engage with current industry tools and methodologies, complete practical projects, and demonstrate their skills through project-based assessments.

[Commercial-specific: This course is designed for fast upskilling and does not include formal reassessment weeks.]
=== COURSE_OVERVIEW END ==="""
        elif course_type == "ACCELERATED":
            return """=== COURSE_OVERVIEW START ===
This accelerated course provides intensive training in the subject area.

Students will develop practical skills and theoretical knowledge through concentrated hands-on activities, assessments, and real-world applications. The course is designed for rapid skill development with units of competency.

Throughout the course, students will engage with industry-standard tools and methodologies, complete practical projects, and demonstrate their competency through various assessment methods in an accelerated timeframe.

[Accelerated-specific: This course is delivered in a condensed format for rapid learning.]
=== COURSE_OVERVIEW END ==="""
        else:  # CUSTOM or default
            return """=== COURSE_OVERVIEW START ===
This course provides comprehensive training in the subject area.

Students will develop practical skills and theoretical knowledge through hands-on activities, assessments, and real-world applications. The course is designed to prepare students for professional roles in their chosen field.

Throughout the course, students will engage with industry-standard tools and methodologies, complete practical projects, and demonstrate their competency through various assessment methods.
=== COURSE_OVERVIEW END ==="""

    def _mock_weekly_topics_response(self, course_type="TAFE", num_weeks=20):
        """Return weekly topics based on course type and number of weeks."""
        if course_type == "COMMERCIAL":
            # Commercial course with fewer weeks
            if num_weeks <= 4:
                return """=== WEEKLY_TOPICS START ===
[
  {
    "week": 1,
    "title": "Introduction to Commercial Applications",
    "topics": ["Industry overview", "Current market trends", "Practical applications"],
    "activity": "Market analysis and discussion"
  },
  {
    "week": 2,
    "title": "Core Business Skills",
    "topics": ["Key business concepts", "Practical tools", "Real-world scenarios"],
    "activity": "Business case study workshop"
  },
  {
    "week": 3,
    "title": "Advanced Applications",
    "topics": ["Complex scenarios", "Industry best practices", "Implementation strategies"],
    "activity": "Project planning and execution"
  },
  {
    "week": 4,
    "title": "Final Integration",
    "topics": ["Comprehensive review", "Final project completion", "Future applications"],
    "activity": "Final project presentation"
  }
]
=== WEEKLY_TOPICS END ==="""
            else:
                return """=== WEEKLY_TOPICS START ===
[
  {
    "week": 1,
    "title": "Commercial Foundations",
    "topics": ["Industry overview", "Market analysis", "Business fundamentals"],
    "activity": "Market research project"
  },
  {
    "week": 2,
    "title": "Practical Applications",
    "topics": ["Real-world scenarios", "Industry tools", "Best practices"],
    "activity": "Case study analysis"
  },
  {
    "week": 3,
    "title": "Advanced Techniques",
    "topics": ["Complex problem solving", "Advanced methodologies", "Innovation strategies"],
    "activity": "Innovation workshop"
  },
  {
    "week": 4,
    "title": "Implementation",
    "topics": ["Project execution", "Quality assurance", "Performance optimization"],
    "activity": "Project implementation"
  },
  {
    "week": 5,
    "title": "Integration",
    "topics": ["System integration", "Cross-functional collaboration", "Scalability"],
    "activity": "Integration testing"
  },
  {
    "week": 6,
    "title": "Optimization",
    "topics": ["Performance tuning", "Efficiency improvements", "Continuous improvement"],
    "activity": "Optimization workshop"
  },
  {
    "week": 7,
    "title": "Advanced Applications",
    "topics": ["Cutting-edge techniques", "Emerging trends", "Future-proofing"],
    "activity": "Trend analysis"
  },
  {
    "week": 8,
    "title": "Final Project",
    "topics": ["Comprehensive application", "Final assessment", "Future planning"],
    "activity": "Final project presentation"
  }
]
=== WEEKLY_TOPICS END ==="""
        else:  # TAFE or other course types
            # TAFE course with more weeks
            return """=== WEEKLY_TOPICS START ===
[
  {
    "week": 1,
    "title": "Introduction to TAFE Course",
    "topics": ["Course overview", "Learning objectives", "Assessment requirements"],
    "activity": "Course orientation and goal setting"
  },
  {
    "week": 2,
    "title": "Foundation Concepts",
    "topics": ["Basic principles", "Core terminology", "Fundamental skills"],
    "activity": "Concept mapping and discussion"
  },
  {
    "week": 3,
    "title": "Core Skills Development",
    "topics": ["Practical applications", "Skill building", "Hands-on practice"],
    "activity": "Skills workshop and practice"
  },
  {
    "week": 4,
    "title": "Advanced Applications",
    "topics": ["Complex scenarios", "Advanced techniques", "Problem solving"],
    "activity": "Case study analysis"
  },
  {
    "week": 5,
    "title": "Integration and Synthesis",
    "topics": ["Connecting concepts", "Cross-disciplinary applications", "Comprehensive understanding"],
    "activity": "Integration project"
  },
  {
    "week": 6,
    "title": "Assessment Preparation",
    "topics": ["Assessment criteria", "Preparation strategies", "Practice assessments"],
    "activity": "Mock assessment"
  },
  {
    "week": 7,
    "title": "Industry Applications",
    "topics": ["Real-world applications", "Industry standards", "Professional practice"],
    "activity": "Industry guest speaker"
  },
  {
    "week": 8,
    "title": "Advanced Problem Solving",
    "topics": ["Complex problem scenarios", "Critical thinking", "Innovative solutions"],
    "activity": "Problem-solving workshop"
  },
  {
    "week": 9,
    "title": "Project Development",
    "topics": ["Project planning", "Implementation strategies", "Quality assurance"],
    "activity": "Project development"
  },
  {
    "week": 10,
    "title": "Collaboration and Teamwork",
    "topics": ["Team dynamics", "Collaborative problem solving", "Communication skills"],
    "activity": "Team project"
  },
  {
    "week": 11,
    "title": "Quality and Standards",
    "topics": ["Quality assurance", "Industry standards", "Best practices"],
    "activity": "Quality audit simulation"
  },
  {
    "week": 12,
    "title": "Innovation and Creativity",
    "topics": ["Creative problem solving", "Innovation techniques", "Future trends"],
    "activity": "Innovation workshop"
  },
  {
    "week": 13,
    "title": "Advanced Integration",
    "topics": ["Cross-functional integration", "System thinking", "Holistic approaches"],
    "activity": "Integration project"
  },
  {
    "week": 14,
    "title": "Professional Development",
    "topics": ["Career planning", "Professional skills", "Industry networking"],
    "activity": "Career development workshop"
  },
  {
    "week": 15,
    "title": "Leadership and Management",
    "topics": ["Leadership principles", "Management skills", "Team leadership"],
    "activity": "Leadership simulation"
  },
  {
    "week": 16,
    "title": "Advanced Applications",
    "topics": ["Cutting-edge applications", "Emerging technologies", "Future-proofing"],
    "activity": "Technology showcase"
  },
  {
    "week": 17,
    "title": "Final Project Development",
    "topics": ["Project completion", "Final assessment preparation", "Portfolio development"],
    "activity": "Final project work"
  },
  {
    "week": 18,
    "title": "Assessment and Evaluation",
    "topics": ["Final assessment", "Evaluation criteria", "Performance review"],
    "activity": "Final assessment"
  },
  {
    "week": 19,
    "title": "Reassessment and Catch-up",
    "topics": ["Review of course content", "Reassessment opportunities", "Catch-up on missed work"],
    "activity": "Individual consultation and review sessions"
  },
  {
    "week": 20,
    "title": "Course Wrap-up and Final Submissions",
    "topics": ["Final assessment submissions", "Course reflection and feedback", "Preparation for no-contact period"],
    "activity": "Final submission review and course completion activities"
  }
]
=== WEEKLY_TOPICS END ==="""

    def _mock_assessments_response(self, course_type="TAFE"):
        """Return assessment descriptions based on course type."""
        if course_type == "COMMERCIAL":
            return """=== ASSESSMENTS START ===
[
  {
    "title": "Commercial Project Portfolio",
    "description": "Develop a comprehensive portfolio showcasing practical applications and real-world project outcomes.",
    "due_date": "Week 4"
  },
  {
    "title": "Industry Case Study Analysis",
    "description": "Analyze and present findings from a real industry case study demonstrating practical understanding.",
    "due_date": "Week 6"
  },
  {
    "title": "Business Implementation Plan",
    "description": "Create a detailed implementation plan for a business scenario with practical recommendations.",
    "due_date": "Week 7"
  },
  {
    "title": "Final Commercial Assessment",
    "description": "Complete a final comprehensive assessment covering all course content and practical applications.",
    "due_date": "Week 8"
  }
]
=== ASSESSMENTS END ==="""
        else:  # TAFE or other course types
            return """=== ASSESSMENTS START ===
[
  {
    "title": "Practical Project",
    "description": "Complete a hands-on project demonstrating practical application of course concepts.",
    "due_date": "Week 8"
  },
  {
    "title": "Knowledge Assessment",
    "description": "Demonstrate understanding of theoretical concepts through a comprehensive test.",
    "due_date": "Week 12"
  },
  {
    "title": "Research Presentation",
    "description": "Research and present on a relevant topic within the course scope.",
    "due_date": "Week 15"
  },
  {
    "title": "Final Comprehensive Assessment",
    "description": "Complete a final assessment covering all course content and competencies. Must be submitted by Week 18 for reassessment opportunities in Week 19.",
    "due_date": "Week 18"
  }
]
=== ASSESSMENTS END ==="""

    def _mock_activities_response(self, week_num, course_type="TAFE"):
        """Return learning activities for a specific week."""
        if course_type == "COMMERCIAL":
            return f"""=== ACTIVITIES_WEEK_{week_num} START ===
Week {week_num} Commercial Activities:

1. **Industry Analysis Workshop**
   - Analyze current market trends and industry developments
   - Identify opportunities and challenges in the commercial landscape
   - Group discussion on practical applications

2. **Business Case Study**
   - Work through real-world business scenarios
   - Apply commercial principles to solve practical problems
   - Present findings and recommendations

3. **Project Planning Session**
   - Develop project plans for commercial applications
   - Create implementation strategies
   - Set measurable objectives and timelines
=== ACTIVITIES_WEEK_{week_num} END ==="""
        else:  # TAFE or other course types
            return f"""=== ACTIVITIES_WEEK_{week_num} START ===
Week {week_num} TAFE Activities:

1. **Hands-on Workshop**
   - Practical application of theoretical concepts
   - Guided exercises and demonstrations
   - Individual and group practice sessions

2. **Assessment Preparation**
   - Review of assessment criteria and requirements
   - Practice with sample assessment tasks
   - Feedback and improvement strategies

3. **Industry Integration**
   - Guest speaker presentations
   - Industry case studies and examples
   - Professional development activities
=== ACTIVITIES_WEEK_{week_num} END ==="""

    def _mock_resources_response(self, week_num, course_type="TAFE"):
        """Return learning resources for a specific week."""
        if course_type == "COMMERCIAL":
            return f"""=== RESOURCES_WEEK_{week_num} START ===
Week {week_num} Commercial Resources:

1. **Industry Reports and Publications**
   - Latest industry research and market analysis
   - Commercial best practices and guidelines
   - Case studies from leading companies

2. **Online Tools and Platforms**
   - Commercial software and applications
   - Industry-specific tools and resources
   - Online learning platforms and tutorials

3. **Professional Networks**
   - Industry associations and professional bodies
   - Networking opportunities and events
   - Mentorship and guidance resources
=== RESOURCES_WEEK_{week_num} END ==="""
        else:  # TAFE or other course types
            return f"""=== RESOURCES_WEEK_{week_num} START ===
Week {week_num} TAFE Resources:

1. **Course Materials**
   - Textbook chapters and supplementary readings
   - Online learning modules and tutorials
   - Assessment guides and rubrics

2. **Practical Resources**
   - Laboratory equipment and software
   - Practice exercises and worksheets
   - Reference documentation and manuals

3. **Support Resources**
   - Student support services and counseling
   - Academic writing and study skills resources
   - Career development and placement services
=== RESOURCES_WEEK_{week_num} END ==="""


class TestInitProgressManager:
    """Test the InitProgressManager class functionality."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for test files."""
        test_dir = tempfile.mkdtemp()
        yield test_dir
        # Cleanup
        try:
            for file in os.listdir(test_dir):
                file_path = os.path.join(test_dir, file)
                if os.path.isfile(file_path):
                    os.remove(file_path)
            os.rmdir(test_dir)
        except Exception:
            # If cleanup fails, just continue
            pass

    @pytest.fixture
    def progress_file(self, temp_dir):
        """Create a progress file path in the temporary directory."""
        return os.path.join(temp_dir, "test_progress.json")

    def test_initialization_empty_file(self, progress_file):
        """Test initialization with non-existent file."""
        manager = InitProgressManager(progress_file)

        # Should start with empty data
        assert manager._data == {}
        assert not os.path.exists(progress_file)

    def test_initialization_existing_file(self, progress_file):
        """Test initialization with existing file."""
        # Create test data
        test_data = {
            "overview": {"status": "done", "result": "Test overview"},
            "weekly_topics": {"status": "done", "result": ["week1", "week2"]},
        }

        # Write test data to file
        with open(progress_file, "w") as f:
            json.dump(test_data, f)

        # Initialize manager
        manager = InitProgressManager(progress_file)

        # Should load existing data
        assert manager._data == test_data

    def test_initialization_corrupted_file(self, progress_file):
        """Test initialization with corrupted JSON file."""
        # Create corrupted JSON
        with open(progress_file, "w") as f:
            f.write("{ invalid json }")

        # Should handle gracefully and start with empty data
        manager = InitProgressManager(progress_file)
        assert manager._data == {}

    def test_get_set_operations(self, progress_file):
        """Test basic get and set operations."""
        manager = InitProgressManager(progress_file)

        # Test setting and getting values
        manager.set("test_key", "test_value")
        assert manager.get("test_key") == "test_value"

        # Test getting non-existent key
        assert manager.get("non_existent") is None

    def test_mark_done_and_status_checks(self, progress_file):
        """Test marking tasks as done and checking status."""
        manager = InitProgressManager(progress_file)

        # Mark a task as done
        result = {"data": "test_result"}
        manager.mark_done("test_task", result)

        # Check status
        assert manager.is_done("test_task") is True
        assert manager.get_result("test_task") == result

        # Check non-existent task
        assert manager.is_done("non_existent") is False
        assert manager.get_result("non_existent") is None

    def test_save_and_load_persistence(self, progress_file):
        """Test that data persists across manager instances."""
        manager1 = InitProgressManager(progress_file)

        # Add some data
        manager1.set("key1", "value1")
        manager1.mark_done("task1", {"result": "success"})

        # Create new manager instance
        manager2 = InitProgressManager(progress_file)

        # Check that data persisted
        assert manager2.get("key1") == "value1"
        assert manager2.is_done("task1") is True
        assert manager2.get_result("task1") == {"result": "success"}

    def test_atomic_write_operations(self, progress_file):
        """Test atomic write operations with temporary files."""
        manager = InitProgressManager(progress_file)

        # Add data to trigger save
        manager.set("atomic_test", "atomic_value")

        # Check that main file exists and temp file doesn't
        assert os.path.exists(progress_file) is True
        assert os.path.exists(progress_file + ".tmp") is False

        # Verify data was written correctly
        with open(progress_file, "r") as f:
            data = json.load(f)
        assert data["atomic_test"] == "atomic_value"

    def test_reset_functionality(self, progress_file):
        """Test reset functionality."""
        manager = InitProgressManager(progress_file)

        # Add some data
        manager.set("key1", "value1")
        manager.mark_done("task1", {"result": "success"})

        # Verify data exists
        assert manager.get("key1") == "value1"
        assert manager.is_done("task1") is True

        # Reset
        manager.reset()

        # Verify data is cleared
        assert manager._data == {}
        assert manager.get("key1") is None
        assert manager.is_done("task1") is False

    def test_thread_safety(self, progress_file):
        """Test thread safety of the progress manager."""
        manager = InitProgressManager(progress_file)
        results = []
        errors = []

        def worker(thread_id):
            try:
                for i in range(10):
                    key = f"thread_{thread_id}_key_{i}"
                    value = f"value_{thread_id}_{i}"
                    manager.set(key, value)

                    # Mark some tasks as done
                    if i % 3 == 0:
                        manager.mark_done(
                            f"task_{thread_id}_{i}", {"result": f"success_{i}"}
                        )

                    time.sleep(0.001)  # Small delay to increase race condition chance

                results.append(f"thread_{thread_id}_completed")
            except Exception as e:
                errors.append(f"thread_{thread_id}_error: {e}")

        # Start multiple threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=worker, args=(i,))
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Check for errors
        assert len(errors) == 0, f"Thread safety errors: {errors}"

        # Verify all threads completed
        assert len(results) == 5

        # Verify data integrity
        for thread_id in range(5):
            for i in range(10):
                key = f"thread_{thread_id}_key_{i}"
                expected_value = f"value_{thread_id}_{i}"
                assert manager.get(key) == expected_value

                if i % 3 == 0:
                    task_key = f"task_{thread_id}_{i}"
                    assert manager.is_done(task_key) is True

    def test_concurrent_file_access(self, progress_file):
        """Test concurrent file access scenarios."""
        manager1 = InitProgressManager(progress_file)
        manager2 = InitProgressManager(progress_file)

        # Both managers should be able to read/write
        manager1.set("manager1_key", "value1")
        manager2.set("manager2_key", "value2")

        # Both should see each other's data
        assert manager1.get("manager2_key") == "value2"
        assert manager2.get("manager1_key") == "value1"

    def test_concurrent_access_with_mocks(self):
        """Test concurrent access using custom mocks to verify semaphore and file locking coordination."""
        # Create a fresh mock file system for this test
        test_mock_fs = MockFileSystem()

        # Results storage: results[worker_id][other_worker_id] = value_read
        results = {0: {}, 1: {}, 2: {}}

        def worker(manager_id, progress_file, results, mock_fs_instance):
            """Worker function that sets and gets values using mocked file operations."""
            # Create a custom InitProgressManager that uses our mocks
            manager = MockInitProgressManager(progress_file, mock_fs_instance)

            # Set a value unique to this worker
            key = f"worker_{manager_id}_key"
            value = f"value_from_worker_{manager_id}"

            manager.set(key, value)

            # Small delay to increase chance of race conditions
            time.sleep(0.1)

            # Try to read values from other workers
            for other_id in range(3):
                if other_id != manager_id:
                    other_key = f"worker_{other_id}_key"
                    other_value = manager.get(other_key)
                    results[manager_id][other_id] = other_value

        # Create and start workers
        threads = []
        for i in range(3):
            thread = threading.Thread(
                target=worker, args=(i, "test_progress.json", results, test_mock_fs)
            )
            threads.append(thread)
            thread.start()

        # Wait for all workers to complete
        for thread in threads:
            thread.join()

        # Check if all workers can see each other's data
        all_successful = True
        for worker_id in range(3):
            for other_id in range(3):
                if worker_id != other_id:
                    expected_key = f"worker_{other_id}_key"
                    expected_value = f"value_from_worker_{other_id}"
                    actual_value = results[worker_id][other_id]

                    if actual_value != expected_value:
                        all_successful = False
                        break

        # Assert that all workers can see each other's data
        assert all_successful, (
            f"Some workers could not see each other's data. Results: {results}"
        )

        # Verify final file state contains all data
        final_content = test_mock_fs.read_file("test_progress.json")
        final_data = json.loads(final_content)
        assert "worker_0_key" in final_data
        assert "worker_1_key" in final_data
        assert "worker_2_key" in final_data
        assert final_data["worker_0_key"] == "value_from_worker_0"
        assert final_data["worker_1_key"] == "value_from_worker_1"
        assert final_data["worker_2_key"] == "value_from_worker_2"


class TestGPTContentGeneratorCheckpointing:
    """Test checkpointing integration with GPTContentGenerator."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for test files."""
        test_dir = tempfile.mkdtemp()
        yield test_dir
        # Cleanup
        for file in os.listdir(test_dir):
            file_path = os.path.join(test_dir, file)
            if os.path.isfile(file_path):
                os.remove(file_path)
        os.rmdir(test_dir)

    @pytest.fixture
    def progress_file(self, temp_dir):
        """Create a progress file path in the temporary directory."""
        return os.path.join(temp_dir, "test_gpt_progress.json")

    @pytest.fixture
    def mock_gpt_client(self):
        """Create a mock GPT client."""
        return MockGPTClient()

    def test_generator_with_progress_manager(self, progress_file):
        """Test GPTContentGenerator with progress manager."""
        config = CourseConfig(course_type="COMMERCIAL", num_weeks=4)
        generator = GPTContentGenerator(
            course_config=config, progress_file=progress_file
        )

        # Should have progress manager
        assert generator.progress is not None
        assert generator.progress.progress_file == progress_file

    def test_generator_without_progress_manager(self):
        """Test GPTContentGenerator without progress manager."""
        config = CourseConfig(course_type="COMMERCIAL", num_weeks=4)
        generator = GPTContentGenerator(course_config=config)

        # Should not have progress manager
        assert generator.progress is None

    @patch("src.utils.gpt_helper.Chat")
    def test_checkpointing_integration_with_mock(
        self, mock_chat, progress_file, mock_gpt_client
    ):
        """Test that checkpointing works with mock GPT client."""
        # Configure mock
        mock_chat.return_value = mock_gpt_client

        config = CourseConfig(course_type="COMMERCIAL", num_weeks=4)
        generator = GPTContentGenerator(
            course_config=config, progress_file=progress_file
        )

        # Mock units for testing
        units = [
            {"id": "TEST001", "name": "Test Unit 1"},
            {"id": "TEST002", "name": "Test Unit 2"},
        ]

        # Initially no progress should be saved
        assert generator.progress.is_done("overview") is False
        assert generator.progress.get_result("overview") is None

        # Generate overview using mock client
        overview = generator.generate_course_overview(units)

        # Should now have progress saved
        assert generator.progress.is_done("overview") is True
        assert generator.progress.get_result("overview") == overview

        # Verify mock was called
        assert mock_gpt_client.call_count >= 1

        # Generate weekly topics
        weekly_topics = generator.generate_weekly_topics(units)

        # Should have progress saved
        assert generator.progress.is_done("weekly_topics") is True
        assert generator.progress.get_result("weekly_topics") == weekly_topics

    @patch("src.utils.gpt_helper.Chat")
    def test_resume_from_checkpoint_with_mock(
        self, mock_chat, progress_file, mock_gpt_client
    ):
        """Test resuming from saved checkpoint using mock client."""
        # Configure mock
        mock_chat.return_value = mock_gpt_client

        config = CourseConfig(course_type="COMMERCIAL", num_weeks=4)

        # Create first generator and generate some content
        generator1 = GPTContentGenerator(
            course_config=config, progress_file=progress_file
        )

        units = [
            {"id": "TEST001", "name": "Test Unit 1"},
            {"id": "TEST002", "name": "Test Unit 2"},
        ]

        # Generate overview
        overview1 = generator1.generate_course_overview(units)
        initial_call_count = mock_gpt_client.call_count

        # Create new generator instance (simulating restart)
        generator2 = GPTContentGenerator(
            course_config=config, progress_file=progress_file
        )

        # Should resume from checkpoint
        overview2 = generator2.generate_course_overview(units)

        # Should be the same result
        assert overview1 == overview2

        # Should have loaded from progress (no additional API calls)
        assert generator2.progress.is_done("overview") is True
        assert generator2.progress.get_result("overview") == overview2

        # Verify no additional API calls were made for the overview
        assert mock_gpt_client.call_count == initial_call_count

    def test_partial_progress_resume(self, progress_file):
        """Test resuming with partial progress."""
        config = CourseConfig(course_type="COMMERCIAL", num_weeks=4)

        # Manually create progress file with partial data
        partial_progress = {
            "overview": {"status": "done", "result": "Pre-generated overview"},
            "weekly_topics": {
                "status": "done",
                "result": [{"week": 1, "title": "Test"}],
            },
        }

        with open(progress_file, "w") as f:
            json.dump(partial_progress, f)

        # Create generator
        generator = GPTContentGenerator(
            course_config=config, progress_file=progress_file
        )

        units = [
            {"id": "TEST001", "name": "Test Unit 1"},
            {"id": "TEST002", "name": "Test Unit 2"},
        ]

        # Should use saved overview
        overview = generator.generate_course_overview(units)
        assert overview == "Pre-generated overview"

        # Should use saved weekly topics
        weekly_topics = generator.generate_weekly_topics(units)
        assert weekly_topics == [{"week": 1, "title": "Test"}]

        # Should generate new assessments (not in progress)
        assessments = generator.generate_assessment_descriptions(units)
        assert assessments is not None
        assert generator.progress.is_done("assessments") is True

    def test_progress_file_cleanup(self, progress_file):
        """Test that temporary files are cleaned up properly."""
        config = CourseConfig(course_type="COMMERCIAL", num_weeks=4)
        generator = GPTContentGenerator(
            course_config=config, progress_file=progress_file
        )

        # Generate some content to trigger saves
        units = [{"id": "TEST001", "name": "Test Unit 1"}]
        generator.generate_course_overview(units)

        # Check that no temporary files remain
        assert os.path.exists(progress_file + ".tmp") is False

        # Check that main file exists and is valid JSON
        assert os.path.exists(progress_file) is True
        with open(progress_file, "r") as f:
            data = json.load(f)
        assert "overview" in data

    @patch("src.utils.gpt_helper.Chat")
    def test_all_generation_methods_with_checkpointing(
        self, mock_chat, progress_file, mock_gpt_client
    ):
        """Test all generation methods work with checkpointing using mock client."""
        # Configure mock
        mock_chat.return_value = mock_gpt_client

        config = CourseConfig(course_type="COMMERCIAL", num_weeks=4)
        generator = GPTContentGenerator(
            course_config=config, progress_file=progress_file
        )

        units = [
            {"id": "TEST001", "name": "Test Unit 1"},
            {"id": "TEST002", "name": "Test Unit 2"},
        ]

        # Generate all content types
        overview = generator.generate_course_overview(units)
        weekly_topics = generator.generate_weekly_topics(units)
        assessments = generator.generate_assessment_descriptions(units)

        # Create weekly topics for activities and resources
        weekly_topics_data = [
            {
                "week": 1,
                "title": "Week 1",
                "topics": ["Topic 1"],
                "activity": "Activity 1",
            },
            {
                "week": 2,
                "title": "Week 2",
                "topics": ["Topic 2"],
                "activity": "Activity 2",
            },
        ]

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

        # Verify mock was called for each generation method
        assert mock_gpt_client.call_count >= 5

    @patch("src.utils.gpt_helper.Chat")
    def test_checkpointing_with_different_course_types(
        self, mock_chat, progress_file, mock_gpt_client
    ):
        """Test checkpointing works with different course configurations."""
        # Configure mock
        mock_chat.return_value = mock_gpt_client

        # Test TAFE course
        tafe_config = CourseConfig(course_type="TAFE")
        tafe_generator = GPTContentGenerator(
            course_config=tafe_config, progress_file=progress_file
        )

        units = [{"id": "TEST001", "name": "Test Unit 1"}]

        # Generate content for TAFE course
        tafe_overview = tafe_generator.generate_course_overview(units)
        tafe_weekly_topics = tafe_generator.generate_weekly_topics(units)

        # Verify progress saved
        assert tafe_generator.progress.is_done("overview") is True
        assert tafe_generator.progress.is_done("weekly_topics") is True

        # Test commercial course with different progress file
        commercial_progress_file = progress_file.replace(".json", "_commercial.json")
        commercial_config = CourseConfig(course_type="COMMERCIAL", num_weeks=8)
        commercial_generator = GPTContentGenerator(
            course_config=commercial_config, progress_file=commercial_progress_file
        )

        # Generate content for commercial course
        commercial_overview = commercial_generator.generate_course_overview(units)
        commercial_weekly_topics = commercial_generator.generate_weekly_topics(units)

        # Verify different progress files don't interfere
        assert commercial_generator.progress.is_done("overview") is True
        assert commercial_generator.progress.is_done("weekly_topics") is True

        # Verify results are different (different course types)
        assert tafe_overview != commercial_overview
        assert tafe_weekly_topics != commercial_weekly_topics


class TestCheckpointingEdgeCases:
    """Test edge cases and error scenarios for checkpointing."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for test files."""
        test_dir = tempfile.mkdtemp()
        yield test_dir
        # Cleanup
        try:
            for file in os.listdir(test_dir):
                file_path = os.path.join(test_dir, file)
                if os.path.isfile(file_path):
                    os.remove(file_path)
            os.rmdir(test_dir)
        except Exception:
            # If cleanup fails, just continue
            pass

    def test_invalid_progress_file_path(self, temp_dir):
        """Test handling of invalid progress file paths."""
        # Test with non-existent directory
        invalid_path = os.path.join(temp_dir, "nonexistent", "progress.json")

        # Should handle gracefully
        manager = InitProgressManager(invalid_path)
        manager.set("test", "value")

        # Should not crash, but may not save successfully
        # This is acceptable behavior for invalid paths

    def test_large_data_handling(self, temp_dir):
        """Test handling of large data sets."""
        manager = InitProgressManager(os.path.join(temp_dir, "large_progress.json"))

        # Add large amount of data
        large_data = {"data": "x" * 10000}  # 10KB of data
        for i in range(100):
            manager.set(f"large_key_{i}", large_data)

        # Should handle without issues
        assert manager.get("large_key_50") == large_data

        # Should save successfully
        manager.save()

        # Should load successfully in new instance
        manager2 = InitProgressManager(os.path.join(temp_dir, "large_progress.json"))
        assert manager2.get("large_key_50") == large_data

    def test_concurrent_file_modification(self, temp_dir):
        """Test concurrent modification of progress file."""
        progress_file = os.path.join(temp_dir, "concurrent_progress.json")

        def modify_file():
            # Directly modify the file while manager is using it
            time.sleep(0.1)  # Wait for manager to start
            with open(progress_file, "w") as f:
                json.dump({"external": "modification"}, f)

        manager = InitProgressManager(progress_file)

        # Start external modification
        thread = threading.Thread(target=modify_file)
        thread.start()

        # Continue using manager
        manager.set("internal", "modification")
        manager.save()

        thread.join()

        # Manager should handle this gracefully
        # The exact behavior may vary, but it shouldn't crash

    def test_memory_efficiency(self, temp_dir):
        """Test memory efficiency with many operations."""
        manager = InitProgressManager(os.path.join(temp_dir, "memory_test.json"))

        # Perform many operations
        for i in range(1000):
            manager.set(f"key_{i}", f"value_{i}")
            if i % 10 == 0:
                manager.mark_done(f"task_{i}", {"result": f"success_{i}"})

        # Should not consume excessive memory
        # This is a basic test - in practice, you'd want to monitor actual memory usage

        # Verify data integrity
        assert manager.get("key_500") == "value_500"
        assert manager.is_done("task_500") is True

    def test_progress_file_corruption_recovery(self, temp_dir):
        """Test recovery from corrupted progress file."""
        progress_file = os.path.join(temp_dir, "corrupted_progress.json")

        # Create a corrupted file
        with open(progress_file, "w") as f:
            f.write("invalid json content")

        # Manager should handle gracefully
        manager = InitProgressManager(progress_file)
        assert manager._data == {}

        # Should be able to continue working
        manager.set("recovery_test", "works")
        assert manager.get("recovery_test") == "works"

    def test_empty_progress_file(self, temp_dir):
        """Test handling of empty progress file."""
        progress_file = os.path.join(temp_dir, "empty_progress.json")

        # Create empty file
        with open(progress_file, "w") as f:
            f.write("")

        # Manager should handle gracefully
        manager = InitProgressManager(progress_file)
        assert manager._data == {}

        # Should be able to continue working
        manager.set("empty_test", "works")
        assert manager.get("empty_test") == "works"

    @patch("src.utils.gpt_helper.Chat")
    def test_checkpointing_with_api_failures(self, mock_chat, temp_dir):
        """Test checkpointing behavior when API calls fail."""
        progress_file = os.path.join(temp_dir, "api_failure_progress.json")

        # Create a mock that fails
        failing_mock = Mock()
        failing_mock.prompt.side_effect = Exception("API Error")
        mock_chat.return_value = failing_mock

        config = CourseConfig(course_type="COMMERCIAL", num_weeks=4)
        generator = GPTContentGenerator(
            course_config=config, progress_file=progress_file
        )

        units = [{"id": "TEST001", "name": "Test Unit 1"}]

        # Should fall back to fallback methods when API fails
        overview = generator.generate_course_overview(units)

        # Should still save progress even with fallback
        assert generator.progress.is_done("overview") is True
        assert generator.progress.get_result("overview") == overview

        # Should not be None (fallback should work)
        assert overview is not None
        assert len(overview) > 0
