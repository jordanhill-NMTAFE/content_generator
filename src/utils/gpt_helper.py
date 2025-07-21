"""
GPT Helper Module for Course Content Generation

This module provides utilities for using language models to generate
course content based on Unit of Competency information.
"""

import os
import json
import re
import fcntl
import platform
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass
from src.utils.logger import log
import threading
from multiprocessing import Semaphore


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


# Try to import GPT library, but make it optional
try:
    from gpt.models.openai_ import Chat

    GPT_AVAILABLE = True
except ImportError as e:
    log.warning(f"GPT library not available: {e}")
    Chat = None
    GPT_AVAILABLE = False


@dataclass
class CourseConfig:
    """
    Configuration for course generation with flexible parameters.
    """

    num_weeks: int = 20
    course_type: str = "TAFE"  # TAFE, COMMERCIAL, ACCELERATED, CUSTOM
    has_reassessment_weeks: bool = True
    has_units_of_competency: bool = True
    is_accredited: bool = True
    academic_weeks: Optional[int] = None
    reassessment_weeks: Optional[int] = None

    # Session hours configuration
    session_hours: float = 4.5
    out_of_class_hours: float = 3.0

    # TAFE-specific fields
    industry_context: Optional[Dict[str, Any]] = None
    assessment_criteria: Optional[Dict[str, Any]] = None
    use_competency_grading: bool = True  # TAFE uses Competent/Not Competent
    require_all_assessments: bool = True  # TAFE requires all assessments to be passed

    def __post_init__(self):
        """Set default values based on course type."""
        if self.course_type == "TAFE":
            if not hasattr(self, "num_weeks") or self.num_weeks is None:
                self.num_weeks = 20
            self.has_reassessment_weeks = True
            self.has_units_of_competency = True
            self.is_accredited = True
            if self.academic_weeks is None:
                self.academic_weeks = 18
            if self.reassessment_weeks is None:
                self.reassessment_weeks = 2
        elif self.course_type == "COMMERCIAL":
            self.has_reassessment_weeks = False
            self.has_units_of_competency = False
            self.is_accredited = False
            self.academic_weeks = self.num_weeks
            self.reassessment_weeks = 0
        elif self.course_type == "ACCELERATED":
            self.has_reassessment_weeks = False
            self.has_units_of_competency = True
            self.is_accredited = True
            self.academic_weeks = self.num_weeks
            self.reassessment_weeks = 0
        elif self.course_type == "CUSTOM":
            # Use provided values, set defaults for None
            if self.academic_weeks is None:
                self.academic_weeks = self.num_weeks - (self.reassessment_weeks or 0)
            if self.reassessment_weeks is None:
                self.reassessment_weeks = self.num_weeks - self.academic_weeks
        else:
            # Default to TAFE settings for unknown course types
            if not hasattr(self, "num_weeks") or self.num_weeks is None:
                self.num_weeks = 20
            self.has_reassessment_weeks = True
            self.has_units_of_competency = True
            self.is_accredited = True
            if self.academic_weeks is None:
                self.academic_weeks = 18
            if self.reassessment_weeks is None:
                self.reassessment_weeks = 2

    @property
    def total_session_hours(self) -> int:
        """Calculate total session hours based on session_hours and num_weeks."""
        return int(self.session_hours * self.num_weeks)

    @property
    def total_out_of_class_hours(self) -> int:
        """Calculate total out-of-class hours based on out_of_class_hours and num_weeks."""
        return int(self.out_of_class_hours * self.num_weeks)

    @property
    def total_training(self) -> int:
        """Calculate total training hours as sum of session and out-of-class hours."""
        return self.total_session_hours + self.total_out_of_class_hours

    def get_week_ranges(self) -> Dict[str, List[int]]:
        """Get week ranges for different phases of the course."""
        ranges = {
            "academic": list(range(1, self.academic_weeks + 1)),
            "reassessment": [],
            "wrap_up": [],
        }

        if self.has_reassessment_weeks and self.reassessment_weeks > 0:
            reassessment_start = self.academic_weeks + 1
            ranges["reassessment"] = list(
                range(reassessment_start, reassessment_start + self.reassessment_weeks)
            )
            ranges["wrap_up"] = ranges["reassessment"]
        else:
            # For courses without reassessment, wrap-up is the last week
            ranges["wrap_up"] = [self.academic_weeks]

        return ranges

    def get_learning_phases(self) -> Dict[str, List[int]]:
        """Get learning phases based on course configuration."""
        academic_weeks = self.academic_weeks

        if academic_weeks <= 4:
            # Short course - single phase
            return {"foundation": list(range(1, academic_weeks + 1))}
        elif academic_weeks <= 8:
            # Medium course - two phases
            mid_point = academic_weeks // 2
            return {
                "foundation": list(range(1, mid_point + 1)),
                "application": list(range(mid_point + 1, academic_weeks + 1)),
            }
        elif academic_weeks <= 12:
            # Longer course - three phases
            third = academic_weeks // 3
            return {
                "foundation": list(range(1, third + 1)),
                "development": list(range(third + 1, 2 * third + 1)),
                "application": list(range(2 * third + 1, academic_weeks + 1)),
            }
        else:
            # Full course - five phases
            fifth = academic_weeks // 5
            return {
                "foundation": list(range(1, 2 * fifth + 1)),
                "development": list(range(2 * fifth + 1, 3 * fifth + 1)),
                "application": list(range(3 * fifth + 1, 4 * fifth + 1)),
                "advanced": list(range(4 * fifth + 1, 5 * fifth + 1)),
                "synthesis": list(range(5 * fifth + 1, academic_weeks + 1)),
            }


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


class FileLock:
    """Cross-platform file locking implementation."""

    def __init__(self, file_path: str):
        self.file_path = file_path
        self.is_windows = platform.system() == "Windows"

    def __enter__(self):
        """Acquire exclusive lock."""
        # Ensure the file exists for locking
        if not os.path.exists(self.file_path):
            # Create empty file for locking
            with open(self.file_path, "w") as f:
                f.write("{}")

        self.file = open(self.file_path, "r+")

        if self.is_windows:
            # Windows file locking
            import msvcrt

            msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            # Unix file locking
            fcntl.flock(self.file.fileno(), fcntl.LOCK_EX)

        return self.file

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Release lock."""
        try:
            if self.is_windows:
                import msvcrt

                msvcrt.locking(self.file.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(self.file.fileno(), fcntl.LOCK_UN)
        finally:
            self.file.close()


# Global semaphore for coordinating access across processes
# This will be shared by all InitProgressManager instances
_progress_semaphore = None


def _get_progress_semaphore():
    """Get or create the global progress semaphore."""
    global _progress_semaphore
    if _progress_semaphore is None:
        _progress_semaphore = Semaphore(1)
    return _progress_semaphore


class InitProgressManager:
    """
    Manages progress checkpointing for course initialization steps.
    Uses IPC semaphore for coordination and file locking for safety.
    Prevents simultaneous access and lost updates.
    """

    def __init__(self, progress_file: str = "init_progress.json"):
        self.progress_file = progress_file
        self._lock = threading.Lock()  # Thread-level lock for this process
        self._semaphore = _get_progress_semaphore()  # Process-level coordination
        self._data = {}
        self._load()

    def _load(self):
        """Load data from file with proper locking."""
        try:
            if os.path.exists(self.progress_file):
                with FileLock(self.progress_file) as f:
                    f.seek(0)
                    content = f.read()
                    if content.strip():
                        self._data = json.loads(content)
                    else:
                        self._data = {}
            else:
                self._data = {}
        except Exception as e:
            log.warning(f"Failed to load progress file {self.progress_file}: {e}")
            self._data = {}

    def _write(self):
        """Write data to file with proper locking and atomic operation."""
        try:
            # Ensure parent directory exists
            parent_dir = os.path.dirname(self.progress_file)
            if parent_dir and not os.path.exists(parent_dir):
                os.makedirs(parent_dir, exist_ok=True)

            # Use atomic write with temporary file in the same directory
            tmp_file = self.progress_file + ".tmp"

            # Write to temporary file first
            with open(tmp_file, "w") as f:
                json.dump(self._data, f, indent=2)
                f.flush()  # Ensure data is written to disk
                os.fsync(f.fileno())  # Force sync to disk

            # Atomic replace using os.replace (works on all platforms)
            os.replace(tmp_file, self.progress_file)

        except Exception as e:
            log.error(f"Failed to write progress file {self.progress_file}: {e}")
            # Clean up temporary file if it exists
            if os.path.exists(tmp_file):
                try:
                    os.remove(tmp_file)
                except:
                    pass

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

    def save(self):
        """Explicitly save the current data to file."""
        with self._semaphore:
            with self._lock:
                self._write()

    def mark_done(self, key, result):
        """Mark a task as done with result."""
        self.set(key, {"status": "done", "result": result})

    def is_done(self, key):
        """Check if a task is marked as done."""
        entry = self._data.get(key)
        return entry is not None and entry.get("status") == "done"

    def get_result(self, key):
        """Get the result of a completed task."""
        entry = self._data.get(key)
        if entry and entry.get("status") == "done":
            return entry.get("result")
        return None

    def reset(self):
        """Reset all progress data."""

        def operation():
            self._data = {}
            return None

        self._atomic_operation(operation)


class CourseContextBuilder:
    """Builds comprehensive context for GPT generation"""

    def __init__(
        self, config: Dict, units: List[Dict], mission_prompt: Optional[str] = None
    ):
        self.config = config
        self.units = units
        self.mission_prompt = mission_prompt

    def build_full_context(self) -> str:
        """Build complete context string for GPT prompts"""
        context_parts = []

        # Course configuration context
        course_config = self.config.get("course", {})
        context_parts.append(f"Course Type: {course_config.get('type', 'TAFE')}")
        context_parts.append(f"Total Weeks: {course_config.get('num_weeks', 20)}")
        context_parts.append(
            f"Academic Weeks: {course_config.get('academic_weeks', 18)}"
        )
        context_parts.append(
            f"Reassessment Weeks: {course_config.get('reassessment_weeks', 2)}"
        )

        # Institutional context
        institution = self.config.get("institution", {})
        if institution.get("name"):
            context_parts.append(f"Institution: {institution['name']}")
        if institution.get("delivery_location"):
            context_parts.append(
                f"Delivery Location: {institution['delivery_location']}"
            )
        if institution.get("delivery_mode"):
            context_parts.append(f"Delivery Mode: {institution['delivery_mode']}")

        # Student context
        students = self.config.get("students", {})
        if students.get("cohort"):
            context_parts.append(f"Student Cohort: {students['cohort']}")

        # Industry contextualization (TAFE-specific)
        industry_context = self.config.get("industry_context", {})
        if industry_context:
            context_parts.append("=== INDUSTRY CONTEXTUALIZATION ===")
            if industry_context.get("primary_industry"):
                context_parts.append(
                    f"Primary Industry: {industry_context['primary_industry']}"
                )
            if industry_context.get("industry_focus"):
                context_parts.append(
                    f"Industry Focus: {industry_context['industry_focus']}"
                )
            if industry_context.get("specific_tools"):
                tools = ", ".join(industry_context["specific_tools"])
                context_parts.append(f"Industry Tools: {tools}")
            if industry_context.get("industry_standards"):
                standards = ", ".join(industry_context["industry_standards"])
                context_parts.append(f"Industry Standards: {standards}")
            if industry_context.get("workplace_context"):
                context_parts.append(
                    f"Workplace Context: {industry_context['workplace_context']}"
                )
            if industry_context.get("industry_partners"):
                partners = ", ".join(industry_context["industry_partners"])
                context_parts.append(f"Industry Partners: {partners}")

        # Assessment criteria (TAFE-specific)
        assessment_criteria = self.config.get("assessment_criteria", {})
        if assessment_criteria:
            context_parts.append("=== ASSESSMENT CRITERIA ===")
            if assessment_criteria.get("competent_standard"):
                context_parts.append(
                    f"Competency Standard: {assessment_criteria['competent_standard']}"
                )
            if assessment_criteria.get("grading_system"):
                context_parts.append(
                    f"Grading System: {assessment_criteria['grading_system']}"
                )
            if assessment_criteria.get("minimum_requirements"):
                context_parts.append(
                    f"Minimum Requirements: {assessment_criteria['minimum_requirements']}"
                )
            if assessment_criteria.get("reassessment_policy"):
                context_parts.append(
                    f"Reassessment Policy: {assessment_criteria['reassessment_policy']}"
                )

        # Unit information
        if self.units:
            unit_info = "\n".join(
                [f"- {unit['id']}: {unit['name']}" for unit in self.units]
            )
            context_parts.append(f"Units of Competency:\n{unit_info}")

        # Mission prompt
        if self.mission_prompt:
            context_parts.append(f"Mission Context:\n{self.mission_prompt}")

        return "\n\n".join(context_parts)


class GPTContentGenerator:
    """
    Handles content generation using language models for course initialization.
    """

    # Standardized prompt constants
    CHAIN_OF_THOUGHT_HEADER = """CHAIN OF THOUGHT ANALYSIS:
1. First, analyze the course structure and purpose:
   - What is the primary focus of this {course_type} course?
   - How does the {num_weeks}-week duration affect the learning approach?
   - What are the key outcomes students should achieve?
   - How does this course type differ from traditional academic programs?
   - How does the industry contextualization shape the learning approach?

2. Consider the learning journey and progression:
   - How can we create an effective learning progression in {academic_weeks} weeks?
   - What foundational concepts need to be established first?
   - How do later topics build upon earlier ones?
   - What is the overall narrative arc of the course?
   - How do industry tools and standards influence the learning sequence?

3. Reflect on the practical applications:
   - What real-world scenarios would require these skills?
   - How does this course prepare students for practical application?
   - What types of projects or assessments would demonstrate mastery?
   - How does this course align with industry needs and expectations?
   - How do industry partners and workplace context inform the learning outcomes?

4. Design the content to:
   - Clearly communicate the purpose and value
   - Highlight the key learning outcomes and benefits
   - Explain the practical relevance and applications
   - Set appropriate expectations for student engagement and workload
   - Align with the course context and goals provided
   - Emphasize industry relevance and workplace preparation"""

    THOUGHT_ANSWER_STRUCTURE = """You will think step by step within <thought> tags. e.g:
<thought>
I will now think step by step.
</thought>

and give your answer within <answer> tags. e.g:
<answer>
Your answer here
</answer>

You are also required to wrap your final answer within a response box like so:
<answer>
=== {response_type} START ===
<Your answer here>
=== {response_type} END ===
</answer>"""

    FORMATTING_REQUIREMENTS = """CRITICAL FORMATTING REQUIREMENTS:
- Each description must be plain text without any special formatting
- Avoid using colons (:) in descriptions as they break YAML parsing
- Use semicolons (;) or periods (.) instead of colons for lists or explanations
- Keep descriptions concise but detailed (2-3 sentences each)
- Use bullet points or numbered lists within each activity description
- Ensure all text is properly escaped and won't interfere with markdown or YAML parsing
- Each item should be self-contained and clear
- When mentioning book titles or references, use quotes or italics instead of colons"""

    # Activity structure examples and guidelines
    ACTIVITY_STRUCTURE_GUIDE = """
ACTIVITY STRUCTURE EXAMPLES AND GUIDELINES:

Based on the provided examples, activities should follow these patterns:

1. TAFE/Technical Courses (like BSBINS401-ICT40120):
   - Structured with clear sections: "Required Tasks", "Optional Activities", "Preparation for Next Week"
   - Include specific readings, videos, tutorials, and practical exercises
   - Time estimates for each session
   - Progressive skill building with industry tools
   - Assessment preparation activities

Example structure:
### Out of Class Activities
**Required Tasks:**
- **Read:** [Specific resource with link]
- **Watch:** [Video tutorial]
- **Complete:** [Practical exercise]
- **Review:** [Previous materials]

**Optional Activities:**
- **Explore:** [Additional resources]
- **Practice:** [Extended exercises]

**Preparation for Next Week:**
- Specific tasks to complete
- Tools to install or configure
- Materials to review

*Expected time: ~3 hours*

2. AI/Conceptual Courses (like AISS-ICTSS00120):
   - Focus on reading assignments and conceptual understanding
   - Include science fiction literature for context
   - Mathematical foundations when relevant
   - Current events and industry developments
   - Philosophical and ethical discussions

Example structure:
This week's extension reading is:
**"Title" by Author** (Year)
   - Brief description of the reading and its relevance to AI concepts.

Additional activities:
- Mathematical foundations (optional but recommended)
- Current industry readings
- Interactive exercises
- Assessment preparation

3. Key Formatting Requirements:
   - Use markdown headers (###) for session titles
   - Include HTML comments for session markers: <!-- Session X Activities Go Here -->
   - Use bold formatting for activity types: **Read:**, **Watch:**, **Complete:**
   - Provide specific links and references
   - Include time estimates where appropriate
   - Use bullet points for lists
   - Maintain consistent structure across weeks
   - Include both required and optional activities
   - Provide clear preparation instructions for next week

4. Content Diversity Guidelines:
   - Mix different types of activities (reading, watching, doing, exploring)
   - Include both theoretical and practical components
   - Provide industry-relevant resources and tools
   - Include assessment preparation activities
   - Offer optional activities for deeper engagement
   - Consider different learning styles and preferences
   - Include current events and industry developments where relevant
   - Provide clear progression from basic to advanced concepts
"""

    def __init__(
        self,
        api_key: Optional[str] = "USE_ENV",
        course_config: Optional[CourseConfig] = None,
        progress_file: Optional[str] = None,
    ):
        """
        Initialize the GPT content generator.

        Args:
            api_key: Optional API key for the language model service.
                    If "USE_ENV" (default), tries to get from environment variable.
                    If None, forces fallback mode without GPT client.
                    If string, uses that API key.
            course_config: Optional course configuration (defaults to TAFE 20-week course)
            progress_file: Optional progress file for checkpointing
        """
        # Handle API key logic
        if api_key == "USE_ENV":
            # Default behavior - check environment variable
            self.api_key = os.getenv("OPENAI_API_KEY")
        else:
            # Explicitly provided (could be None for testing or a string)
            self.api_key = api_key

        if not self.api_key:
            log.warning("No API key provided. Some features may not work.")

        # Set course configuration
        self.course_config = course_config or CourseConfig()
        self.progress = InitProgressManager(progress_file) if progress_file else None

        # Initialize GPT client if available
        try:
            if GPT_AVAILABLE and self.api_key:
                self.client = Chat(
                    model_name="gpt-4.1-nano-2025-04-14",
                    max_completion_tokens=32768,
                    context=1,
                )
            else:
                self.client = None
        except Exception as e:
            log.warning(f"Failed to initialize GPT client: {e}")
            self.client = None

    def _safe_prompt_with_retries(
        self,
        prompt: str,
        max_retries: int = 3,
        response_type: str = "RESPONSE",
        json_expected: bool = False,
    ) -> Tuple[Optional[str], bool]:
        """
        Safely prompt the model with retry logic and error handling.

        Args:
            prompt: The prompt to send to the model
            max_retries: Maximum number of retries before clearing context
            response_type: Type of response box to expect
            json_expected: Whether the response should be valid JSON

        Returns:
            Tuple of (extracted_response, success_flag)
        """
        if not self.client:
            return None, False

        for attempt in range(max_retries):
            try:
                log.info(
                    f"{Colors.CYAN}🔄 Attempt {attempt + 1}/{max_retries}...{Colors.END}"
                )

                response = self.client.prompt(prompt)
                content = response.strip()

                # Try to extract from response box
                extracted = ResponseBox.extract(content, response_type)
                if extracted:
                    content = extracted

                # Validate JSON if expected
                if json_expected:
                    try:
                        # Try to extract JSON from the response
                        if "```json" in content:
                            content = content.split("```json")[1].split("```")[0]
                        elif "```" in content:
                            content = content.split("```")[1]

                        # Validate JSON
                        json.loads(content)
                        log.info(
                            f"{Colors.GREEN}✅ Valid JSON response on attempt {attempt + 1}{Colors.END}"
                        )
                        return content, True
                    except (json.JSONDecodeError, IndexError) as e:
                        log.warning(
                            f"{Colors.YELLOW}⚠️  Invalid JSON on attempt {attempt + 1}: {e}{Colors.END}"
                        )
                        if attempt < max_retries - 1:
                            continue
                        else:
                            # Final attempt - try to get a direct response
                            return self._get_direct_response(
                                prompt, response_type, json_expected
                            )

                # For non-JSON responses, just return the content
                log.info(
                    f"{Colors.GREEN}✅ Valid response on attempt {attempt + 1}{Colors.END}"
                )
                return content, True

            except Exception as e:
                log.error(
                    f"{Colors.RED}❌ Error on attempt {attempt + 1}: {e}{Colors.END}"
                )
                if attempt < max_retries - 1:
                    continue
                else:
                    # Final attempt - try to get a direct response
                    return self._get_direct_response(
                        prompt, response_type, json_expected
                    )

        return None, False

    def _get_direct_response(
        self, prompt: str, response_type: str, json_expected: bool
    ) -> Tuple[Optional[str], bool]:
        """
        Get a direct response after clearing context and simplifying the prompt.

        Args:
            prompt: Original prompt
            response_type: Type of response box
            json_expected: Whether JSON is expected

        Returns:
            Tuple of (response, success_flag)
        """
        log.info(
            f"{Colors.YELLOW}🔄 Clearing context and requesting direct response...{Colors.END}"
        )

        # Simplify the prompt for direct response
        if json_expected:
            direct_prompt = f"""Please provide a direct JSON response to the following request. 
            Format your response exactly as requested without additional explanation.
            
            {prompt}
            
            {ResponseBox.wrap("", response_type)}"""
        else:
            direct_prompt = f"""Please provide a direct response to the following request.
            Format your response exactly as requested without additional explanation.
            
            {prompt}
            
            {ResponseBox.wrap("", response_type)}"""

        try:
            response = self.client.prompt(direct_prompt)
            content = response.strip()

            # Extract from response box
            extracted = ResponseBox.extract(content, response_type)
            if extracted:
                content = extracted

            # Validate JSON if expected
            if json_expected:
                try:
                    if "```json" in content:
                        content = content.split("```json")[1].split("```")[0]
                    elif "```" in content:
                        content = content.split("```")[1]

                    json.loads(content)
                    log.info(f"{Colors.GREEN}✅ Direct response successful{Colors.END}")
                    return content, True
                except (json.JSONDecodeError, IndexError) as e:
                    log.error(f"{Colors.RED}❌ Direct response failed: {e}{Colors.END}")
                    return None, False

            log.info(f"{Colors.GREEN}✅ Direct response successful{Colors.END}")
            return content, True

        except Exception as e:
            log.error(f"{Colors.RED}❌ Direct response failed: {e}{Colors.END}")
            return None, False

    def generate_course_overview(
        self, units: List[Dict[str, Any]], mission_prompt: Optional[str] = None
    ) -> str:
        """
        Generate a course overview based on unit information.

        Args:
            units: List of unit dictionaries with 'name' and 'id' keys
            mission_prompt: Optional guiding prompt for course context and goals

        Returns:
            Generated course overview text
        """
        if self.progress and self.progress.is_done("overview"):
            return self.progress.get_result("overview")

        if not self.client:
            log.info(
                f"{Colors.YELLOW}GPT client not available, using fallback course overview{Colors.END}"
            )
            fallback = self._fallback_course_overview(units)
            if self.progress:
                self.progress.mark_done("overview", fallback)
            return fallback

        log.info(
            f"{Colors.BLUE}{Colors.BOLD}🔄 Generating course overview with chain of thought reasoning for {self.course_config.course_type} course...{Colors.END}"
        )

        mission_context = ""
        if mission_prompt:
            mission_context = f"\n\nCourse Context and Goals:\n{mission_prompt}\n"

        # Build standardized contexts using helper methods
        unit_info, unit_context = self._build_unit_context(units, mission_prompt)
        course_type_context = self._build_course_structure_context()
        industry_context = self._build_industry_context()

        prompt = f"""

{unit_info}

{course_type_context}
{industry_context}

{self._format_chain_of_thought_header()}

The overview should:
- Explain what students will learn
- Describe the key skills and knowledge areas
- Mention the practical applications
- Be written in a professional but accessible tone
- Align with the course context and goals provided
- Reflect the {self.course_config.course_type.lower()} nature of the course
- Highlight industry contextualization and workplace relevance

{self._format_thought_answer_structure("COURSE_OVERVIEW")}

{unit_context}
"""

        response, success = self._safe_prompt_with_retries(
            prompt, max_retries=3, response_type="COURSE_OVERVIEW", json_expected=False
        )

        if success and response:
            log.info(
                f"{Colors.GREEN}{Colors.BOLD}✅ Successfully generated course overview with chain of thought reasoning{Colors.END}"
            )
            if self.progress:
                self.progress.mark_done("overview", response.strip())
            return response.strip()
        else:
            log.error(
                f"{Colors.RED}Failed to generate course overview after all retries{Colors.END}"
            )
            log.info(f"{Colors.YELLOW}⚠️  Using fallback course overview{Colors.END}")
            fallback = self._fallback_course_overview(units)
            if self.progress:
                self.progress.mark_done("overview", fallback)
            return fallback

    def generate_weekly_topics(
        self,
        units: List[Dict[str, Any]],
        mission_prompt: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Generate weekly topics based on unit information.

        Args:
            units: List of unit dictionaries
            mission_prompt: Optional guiding prompt for course context and goals

        Returns:
            List of weekly topic dictionaries
        """
        if self.progress and self.progress.is_done("weekly_topics"):
            return self.progress.get_result("weekly_topics")

        if not self.client:
            log.info(
                f"{Colors.YELLOW}GPT client not available, using fallback weekly topics{Colors.END}"
            )
            fallback = self._fallback_weekly_topics(units, self.course_config.num_weeks)
            if self.progress:
                self.progress.mark_done("weekly_topics", fallback)
            return fallback

        log.info(
            f"{Colors.BLUE}{Colors.BOLD}🔄 Generating {self.course_config.num_weeks} weekly topics with chain of thought reasoning for {self.course_config.course_type} course...{Colors.END}"
        )

        mission_context = ""
        if mission_prompt:
            mission_context = f"\n\nCourse Context and Goals:\n{mission_prompt}\n"

        # Build standardized contexts using helper methods
        unit_info, base_unit_context = self._build_unit_context(units, mission_prompt)
        unit_context = f"{base_unit_context} Generate a {self.course_config.num_weeks}-week course structure with weekly topics."
        course_structure_context = self._build_course_structure_context()
        industry_context = self._build_industry_context()

        # Custom steps for weekly topics
        learning_phases_context = self._build_learning_phases_context()
        custom_steps = [
            f"First, analyze the course structure and learning phases: What are the foundational concepts that need to be taught first? How can we create a progressive learning journey in {self.course_config.academic_weeks} academic weeks? What are the logical prerequisites and dependencies? How do the learning phases align with the course duration? How do industry tools and standards influence the learning sequence?",
            f"Consider the course structure and timing: {learning_phases_context}",
            "Plan the curriculum progression: Start with fundamental concepts that other topics depend on; Gradually increase complexity and depth; Include regular review and integration points; Ensure practical application opportunities throughout; Build toward comprehensive assessment readiness; Integrate industry tools and standards progressively",
            f"Design weekly topics that: Have clear learning objectives; Build upon previous weeks' content; Include both theoretical and practical components; Are appropriate for the learning phase; Consider student workload and cognitive load; Align with the {self.course_config.course_type.lower()} course structure; Incorporate industry-relevant tools and practices; Prepare students for workplace application",
        ]

        prompt = f"""

{unit_info}

{course_structure_context}
{industry_context}

{self._format_chain_of_thought_header(custom_steps)}

For each week, provide:
1. A clear topic title that reflects the learning phase
2. 3-5 key learning points that show progression
3. An appropriate in-class activity that reinforces the learning

Format the response as a JSON array with objects containing:
- week: week number
- title: topic title
- topics: array of learning points
- activity: in-class activity description

{self._format_formatting_requirements("weekly topics")}

{self._format_thought_answer_structure("WEEKLY_TOPICS")}

{unit_context}
"""

        response, success = self._safe_prompt_with_retries(
            prompt, max_retries=3, response_type="WEEKLY_TOPICS", json_expected=True
        )

        if success and response:
            try:
                result = json.loads(response)
                log.info(
                    f"{Colors.GREEN}{Colors.BOLD}✅ Successfully generated {len(result)} weekly topics with chain of thought reasoning{Colors.END}"
                )
                if self.progress:
                    self.progress.mark_done("weekly_topics", result)
                return result
            except json.JSONDecodeError as e:
                log.error(f"{Colors.RED}Failed to parse JSON response: {e}{Colors.END}")
                log.info(f"{Colors.YELLOW}⚠️  Using fallback weekly topics{Colors.END}")
                fallback = self._fallback_weekly_topics(
                    units, self.course_config.num_weeks
                )
                if self.progress:
                    self.progress.mark_done("weekly_topics", fallback)
                return fallback
        else:
            log.error(
                f"{Colors.RED}Failed to generate weekly topics after all retries{Colors.END}"
            )
            log.info(f"{Colors.YELLOW}⚠️  Using fallback weekly topics{Colors.END}")
            fallback = self._fallback_weekly_topics(units, self.course_config.num_weeks)
            if self.progress:
                self.progress.mark_done("weekly_topics", fallback)
            return fallback

    def generate_assessment_descriptions(
        self, units: List[Dict[str, Any]], mission_prompt: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Generate assessment descriptions based on unit information.

        Args:
            units: List of unit dictionaries
            mission_prompt: Optional guiding prompt for course context and goals

        Returns:
            List of assessment dictionaries
        """
        if self.progress and self.progress.is_done("assessments"):
            return self.progress.get_result("assessments")

        if not self.client:
            log.info(
                f"{Colors.YELLOW}GPT client not available, using fallback assessment descriptions{Colors.END}"
            )
            fallback = self._fallback_assessment_descriptions(units)
            if self.progress:
                self.progress.mark_done("assessments", fallback)
            return fallback

        log.info(
            f"{Colors.BLUE}{Colors.BOLD}🔄 Generating assessment descriptions with chain of thought reasoning...{Colors.END}"
        )

        # Build standardized contexts using helper methods
        unit_info, base_unit_context = self._build_unit_context(units, mission_prompt)
        unit_context = f"{base_unit_context} Generate 4 assessment descriptions."
        industry_context = self._build_industry_context()

        # Custom steps for assessment descriptions
        custom_steps = [
            f"First, analyze the {self.course_config.course_type} competency-based assessment strategy: What types of evidence do we need to demonstrate competency? How can we assess both theoretical knowledge and practical skills? What is the logical progression of assessment complexity? How do assessments align with the learning phases? How do we ensure ALL assessments must be passed for competency?",
            f"Consider {self.course_config.course_type} assessment timing and progression: Early assessments (Weeks 4-8) focus on foundational concepts and basic skills; Mid-course assessments (Weeks 9-12) test application and integration; Advanced assessments (Weeks 13-16) evaluate complex problem-solving; Final assessment (Week 18) comprehensive demonstration of all competencies; Reassessment period (Weeks 19-20) for students not yet competent",
            f"Design {self.course_config.course_type} assessment types that: Align with {self.course_config.course_type} competency-based assessment principles (Competent/Not Competent); Provide multiple opportunities for demonstration; Allow for reassessment in Week 19-20; Cover different learning domains (cognitive, psychomotor, affective); Include both individual and collaborative elements; Focus on industry-relevant skills and tools",
            f"Plan {self.course_config.course_type} assessment logistics: Consider student workload and preparation time; Ensure assessments build upon each other; Provide clear competency criteria and expectations; Allow for formative feedback before summative assessment; Ensure all assessments must be completed and passed",
        ]

        # Add Elements/Criteria guidance
        elements_criteria_guidance = """
CRITICAL ASSESSMENT MAPPING STRUCTURE GUIDANCE:

ELEMENTS vs CRITERIA HIERARCHY:
- ELEMENTS are the main sections of a unit (numbered 1, 2, 3, 4, etc.)
- CRITERIA are sub-points within elements (numbered 1.1, 1.2, 1.3, 2.1, 2.2, etc.)
- Each element contains multiple criteria that must ALL be satisfied together

ASSESSMENT DESIGN RULES:
1. ALL criteria for an element must be satisfied within the same assessment
   - Example: Assessment 1 covers Element 1 (criteria 1.1, 1.2, 1.3) and Element 2 (criteria 2.1, 2.2)
   - Example: Assessment 2 covers Element 3 (criteria 3.1, 3.2) and Element 4 (criteria 4.1, 4.2, 4.3)

2. Assessments must be mapped at the CRITERIA level to questions
   - Each question should map to specific criteria (e.g., 1.1, 1.2, 2.1)
   - NOT to simplified descriptions like "1. Specify software requirements"


When designing assessments, ensure they properly map to specific criteria within elements, not to general element descriptions.
"""

        prompt = f"""{unit_context}

{unit_info}

{industry_context}

{elements_criteria_guidance}

{self._format_chain_of_thought_header(custom_steps)}

Generate different types of assessments, for example:
1. A practical project/assignment (early-mid course) - Industry application
2. A knowledge-based assessment (mid course) - Industry standards
3. A research/presentation task (mid-late course) - Industry communication
4. A final comprehensive assessment (end of course) - Overall competency

For each assessment, provide:
- title: Assessment title that reflects the type, purpose, and industry focus
- description: Detailed description of what students need to do, including:
  * Clear learning objectives aligned with industry needs
  * Specific requirements and competency criteria
  * Expected outcomes and deliverables
  * Assessment methods and evidence types
  * Industry tools and standards to be demonstrated
- due_date: Suggested due week (Week X format) with rationale
- competency_focus: What specific competency this assessment demonstrates
- assessment_method: How competency will be assessed (portfolio, test, presentation, etc.)

Consider the course context, industry focus, and {self.course_config.course_type} competency requirements when designing assessments.

Format as JSON array with objects containing title, description, due_date, competency_focus, and assessment_method.

{self._format_formatting_requirements("assessment descriptions")}

{self._format_thought_answer_structure("ASSESSMENTS")}
"""

        response, success = self._safe_prompt_with_retries(
            prompt, max_retries=3, response_type="ASSESSMENTS", json_expected=True
        )

        if success and response:
            try:
                result = json.loads(response)
                log.info(
                    f"{Colors.GREEN}{Colors.BOLD}✅ Successfully generated {len(result)} assessment descriptions with chain of thought reasoning{Colors.END}"
                )
                if self.progress:
                    self.progress.mark_done("assessments", result)
                return result
            except json.JSONDecodeError as e:
                log.error(f"{Colors.RED}Failed to parse JSON response: {e}{Colors.END}")
                log.info(
                    f"{Colors.YELLOW}⚠️  Using fallback assessment descriptions{Colors.END}"
                )
                fallback = self._fallback_assessment_descriptions(units)
                if self.progress:
                    self.progress.mark_done("assessments", fallback)
                return fallback
        else:
            log.error(
                f"{Colors.RED}Failed to generate assessment descriptions after all retries{Colors.END}"
            )
            log.info(
                f"{Colors.YELLOW}⚠️  Using fallback assessment descriptions{Colors.END}"
            )
            fallback = self._fallback_assessment_descriptions(units)
            if self.progress:
                self.progress.mark_done("assessments", fallback)
            return fallback

    def generate_learning_activities(
        self, weekly_topics: List[Dict[str, Any]], mission_prompt: Optional[str] = None
    ) -> List[str]:
        """
        Generate learning activities for all weeks using chain of thought reasoning.

        Args:
            weekly_topics: List of weekly topic dictionaries (18 academic weeks + 2 reassessment weeks)
            mission_prompt: Optional guiding prompt for course context and goals

        Returns:
            List of activity descriptions
        """
        if self.progress and self.progress.is_done("activities"):
            return self.progress.get_result("activities")

        if not self.client:
            log.info(
                f"{Colors.YELLOW}GPT client not available, using fallback activities{Colors.END}"
            )
            fallback = self._fallback_learning_activities(weekly_topics)
            if self.progress:
                self.progress.mark_done("activities", fallback)
            return fallback

        log.info(
            f"{Colors.PURPLE}{Colors.BOLD}🔄 Generating learning activities for all {len(weekly_topics)} weeks with chain of thought reasoning and full context awareness (18 academic + 2 reassessment)...{Colors.END}"
        )

        # Build standardized contexts using helper methods
        course_context = self._build_course_context(weekly_topics, mission_prompt)
        industry_context = self._build_industry_context()

        # Build weekly topics context
        weekly_context = "\n".join(
            [
                f"Week {week['week']}: {week['title']}\nTopics: {', '.join(week['topics'])}"
                for week in weekly_topics
            ]
        )

        # Custom steps for learning activities
        custom_steps = [
            f"First, analyze the overall course structure and learning progression: What is the learning journey from Week 1 to Week {len(weekly_topics)}? How do concepts build upon each other across the weeks? What are the key learning phases and transitions? How do industry tools and standards influence the learning progression? What is the overall narrative arc of the course?",
            "Consider the learning objectives and assessment alignment: How do activities prepare students for competency-based assessment? What types of activities would best reinforce learning objectives? How can we ensure both individual and collaborative learning? How do industry practices and workplace contexts inform activities? How do activities align with the course context and goals?",
            "Design a coherent activity progression: Start with foundational activities and progress to complex applications; Ensure activities build upon and complement previous weeks; Include both theoretical understanding and practical application; Provide opportunities for formative assessment and feedback; Engage different learning styles and preferences; Incorporate industry-relevant tools and practices progressively",
            "Plan for different week types: Weeks 1-18: Regular academic content with hands-on activities; Week 19: Focus on reassessment opportunities, catch-up activities, and review; Week 20: Focus on final submissions, course wrap-up, and preparation for no-contact period",
            "Ensure activities are: Practical and hands-on; Appropriate for classroom completion; Include both individual and group work; Avoid repetition of concepts; Incorporate industry tools and workplace scenarios; Prepare students for workplace application",
        ]

        prompt = f"""Generate learning activities for all {len(weekly_topics)} weeks using chain of thought reasoning with full course context.

{course_context}
{industry_context}

WEEKLY TOPICS:
{weekly_context}

{self.ACTIVITY_STRUCTURE_GUIDE}

{self._format_chain_of_thought_header(custom_steps)}

{self._format_formatting_requirements("learning activities")}

{self._format_thought_answer_structure("LEARNING_ACTIVITIES")}
"""

        response, success = self._safe_prompt_with_retries(
            prompt,
            max_retries=3,
            response_type="LEARNING_ACTIVITIES",
            json_expected=True,
        )

        if success and response:
            try:
                # Parse JSON response
                if "```json" in response:
                    response = response.split("```json")[1].split("```")[0]
                elif "```" in response:
                    response = response.split("```")[1]

                activities_data = json.loads(response)

                # Extract activities in order and sanitize them
                activities = []
                for week_data in activities_data:
                    if isinstance(week_data, dict) and "activities" in week_data:
                        # Sanitize each activity to ensure YAML compatibility
                        sanitized_activities = []
                        for activity in week_data["activities"]:
                            # Replace problematic characters and ensure proper formatting
                            sanitized_activity = self._sanitize_activity_text(activity)
                            sanitized_activities.append(sanitized_activity)
                        activities.append("\n\n".join(sanitized_activities))
                    else:
                        # Fallback if format is unexpected
                        activities.append(str(week_data))

                log.info(
                    f"{Colors.GREEN}{Colors.BOLD}✅ Successfully generated activities for all {len(weekly_topics)} weeks with chain of thought reasoning{Colors.END}"
                )
                if self.progress:
                    self.progress.mark_done("activities", activities)
                return activities

            except (json.JSONDecodeError, KeyError, IndexError) as e:
                log.error(
                    f"{Colors.RED}Failed to parse activities JSON: {e}{Colors.END}"
                )
                log.info(f"{Colors.YELLOW}⚠️  Using fallback activities{Colors.END}")
                fallback = self._fallback_learning_activities(weekly_topics)
                if self.progress:
                    self.progress.mark_done("activities", fallback)
                return fallback
        else:
            log.error(
                f"{Colors.RED}Failed to generate activities after all retries{Colors.END}"
            )
            log.info(f"{Colors.YELLOW}⚠️  Using fallback activities{Colors.END}")
            fallback = self._fallback_learning_activities(weekly_topics)
            if self.progress:
                self.progress.mark_done("activities", fallback)
            return fallback

    def generate_learning_resources(
        self, weekly_topics: List[Dict[str, Any]], mission_prompt: Optional[str] = None
    ) -> List[str]:
        """
        Generate learning resources for all weeks using chain of thought reasoning.

        Args:
            weekly_topics: List of weekly topic dictionaries (18 academic weeks + 2 reassessment weeks)
            mission_prompt: Optional guiding prompt for course context and goals

        Returns:
            List of resource descriptions
        """
        if self.progress and self.progress.is_done("resources"):
            return self.progress.get_result("resources")

        if not self.client:
            log.info(
                f"{Colors.YELLOW}GPT client not available, using fallback resources{Colors.END}"
            )
            fallback = self._fallback_learning_resources(weekly_topics)
            if self.progress:
                self.progress.mark_done("resources", fallback)
            return fallback

        log.info(
            f"{Colors.PURPLE}{Colors.BOLD}🔄 Generating learning resources for all {len(weekly_topics)} weeks with chain of thought reasoning and full context awareness (18 academic + 2 reassessment)...{Colors.END}"
        )

        # Build standardized contexts using helper methods
        course_context = self._build_course_context(weekly_topics, mission_prompt)
        industry_context = self._build_industry_context()

        # Build weekly topics context
        weekly_context = "\n".join(
            [
                f"Week {week['week']}: {week['title']}\nTopics: {', '.join(week['topics'])}"
                for week in weekly_topics
            ]
        )

        # Custom steps for learning resources
        custom_steps = [
            f"First, analyze the overall course structure and learning progression: What is the learning journey from Week 1 to Week {len(weekly_topics)}? How do concepts build upon each other across the weeks? What are the key learning phases and transitions? How do industry tools and standards influence the learning progression? What is the overall narrative arc of the course?",
            "Consider the learning objectives and assessment alignment: How do resources support students for competency-based assessment? What types of resources would best reinforce learning objectives? How can we ensure both theoretical and practical resource coverage? How do industry practices and workplace contexts inform resource selection? How do resources align with the course context and goals?",
            "Design a coherent resource progression: Start with foundational resources and progress to complex applications; Ensure resources build upon and complement previous weeks; Include both theoretical understanding and practical application; Provide opportunities for self-directed learning and exploration; Engage different learning styles and preferences; Incorporate industry-relevant tools and practices progressively",
            "Plan for different week types: Weeks 1-18: Regular academic content with comprehensive resources; Week 19: Focus on review materials, reassessment preparation, and catch-up resources; Week 20: Focus on final submission guidelines, course wrap-up, and preparation for no-contact period",
            "Ensure resources are: Accessible and appropriate for the target audience; Include both required and recommended materials; Cover theoretical foundations and practical applications; Include industry-relevant tools, platforms, and documentation; Provide opportunities for deeper exploration and self-directed learning; Prepare students for workplace application",
        ]

        prompt = f"""Generate learning resources for all {len(weekly_topics)} weeks using chain of thought reasoning with full course context.

{course_context}
{industry_context}

WEEKLY TOPICS:
{weekly_context}

{self.ACTIVITY_STRUCTURE_GUIDE}

{self._format_chain_of_thought_header(custom_steps)}

{self._format_formatting_requirements("learning resources")}

{self._format_thought_answer_structure("LEARNING_RESOURCES")}
"""

        response, success = self._safe_prompt_with_retries(
            prompt,
            max_retries=3,
            response_type="LEARNING_RESOURCES",
            json_expected=True,
        )

        if success and response:
            try:
                # Parse JSON response
                if "```json" in response:
                    response = response.split("```json")[1].split("```")[0]
                elif "```" in response:
                    response = response.split("```")[1]

                resources_data = json.loads(response)

                # Extract resources in order and sanitize them
                resources = []
                for week_data in resources_data:
                    if isinstance(week_data, dict) and "resources" in week_data:
                        # Sanitize each resource to ensure YAML compatibility
                        sanitized_resources = []
                        for resource in week_data["resources"]:
                            # Replace problematic characters and ensure proper formatting
                            sanitized_resource = self._sanitize_activity_text(resource)
                            sanitized_resources.append(sanitized_resource)
                        resources.append("\n\n".join(sanitized_resources))
                    else:
                        # Fallback if format is unexpected
                        resources.append(str(week_data))

                log.info(
                    f"{Colors.GREEN}{Colors.BOLD}✅ Successfully generated resources for all {len(weekly_topics)} weeks with chain of thought reasoning{Colors.END}"
                )
                if self.progress:
                    self.progress.mark_done("resources", resources)
                return resources

            except (json.JSONDecodeError, KeyError, IndexError) as e:
                log.error(
                    f"{Colors.RED}Failed to parse resources JSON: {e}{Colors.END}"
                )
                log.info(f"{Colors.YELLOW}⚠️  Using fallback resources{Colors.END}")
                fallback = self._fallback_learning_resources(weekly_topics)
                if self.progress:
                    self.progress.mark_done("resources", fallback)
                return fallback
        else:
            log.error(
                f"{Colors.RED}Failed to generate resources after all retries{Colors.END}"
            )
            log.info(f"{Colors.YELLOW}⚠️  Using fallback resources{Colors.END}")
            fallback = self._fallback_learning_resources(weekly_topics)
            if self.progress:
                self.progress.mark_done("resources", fallback)
            return fallback

    def _sanitize_activity_text(self, activity_text: str) -> str:
        """
        Sanitize activity text to ensure it's compatible with YAML and markdown parsing.

        Args:
            activity_text: Raw activity text from GPT

        Returns:
            Sanitized activity text safe for YAML/markdown
        """
        if not activity_text:
            return "Activity description not available."

        # Replace problematic characters that break YAML parsing
        sanitized = activity_text

        # Replace colons with semicolons or periods to avoid YAML key-value confusion
        sanitized = sanitized.replace(": ", "; ")
        sanitized = sanitized.replace(":\n", ".\n")

        # Ensure proper line breaks and formatting
        sanitized = sanitized.replace("\n\n", "\n").strip()

        # Remove any remaining problematic YAML characters at the start of lines
        lines = sanitized.split("\n")
        cleaned_lines = []
        for line in lines:
            line = line.strip()
            if line.startswith("-") or line.startswith("*"):
                # Keep bullet points but ensure proper formatting
                cleaned_lines.append(line)
            elif line and not line.startswith("#"):
                # Regular text line
                cleaned_lines.append(line)

        return "\n".join(cleaned_lines)

    def generate_learning_materials(
        self,
        weekly_topics: List[Dict[str, Any]],
        mission_prompt: Optional[str] = None,
        slide_theme: Optional[str] = None,
    ) -> Dict[int, Dict[str, str]]:
        """
        Generate learning materials for all weeks using a direct approach:
        For each week, generate slides.md and demo.md using the current topic and context.
        This replaces the old two-stage planning approach.
        """
        if self.progress and self.progress.is_done("learning_materials"):
            return self.progress.get_result("learning_materials")

        if not self.client:
            log.info(
                f"{Colors.YELLOW}GPT client not available, using fallback learning materials{Colors.END}"
            )
            fallback = self._fallback_learning_materials(weekly_topics)
            if self.progress:
                self.progress.mark_done("learning_materials", fallback)
            return fallback

        log.info(
            f"{Colors.PURPLE}{Colors.BOLD}🔄 Generating learning materials for {len(weekly_topics)} weeks (direct approach)...{Colors.END}"
        )

        # Build a minimal materials_plan for each week: slides.md and demo.md
        materials_plan = []
        for week in weekly_topics:
            materials_plan.append(
                {
                    "filename": "slides.md",
                    "title": f"{week['title']} Slides",
                    "description": f"Comprehensive presentation slides for Week {week['week']}",
                    "week": week["week"],
                    "justification": f"Slides for Week {week['week']} help visualize and structure the content.",
                }
            )
            materials_plan.append(
                {
                    "filename": "demo.md",
                    "title": f"{week['title']} Workshop",
                    "description": f"Hands-on workshop for Week {week['week']} concepts",
                    "week": week["week"],
                    "justification": f"Practical application for Week {week['week']} reinforces learning.",
                }
            )

        learning_materials = self._generate_individual_materials(
            materials_plan, weekly_topics, mission_prompt, slide_theme=slide_theme
        )

        if learning_materials:
            log.info(
                f"{Colors.GREEN}{Colors.BOLD}✅ Successfully generated all learning materials{Colors.END}"
            )
            if self.progress:
                self.progress.mark_done("learning_materials", learning_materials)
            return learning_materials
        else:
            log.error(f"{Colors.RED}Failed to generate learning materials{Colors.END}")
            fallback = self._fallback_learning_materials(weekly_topics)
            if self.progress:
                self.progress.mark_done("learning_materials", fallback)
            return fallback

    def _generate_individual_materials(
        self,
        materials_plan: List[Dict[str, Any]],
        weekly_topics: List[Dict[str, Any]],
        mission_prompt: Optional[str] = None,
        slide_theme: Optional[str] = None,
    ) -> Dict[int, Dict[str, str]]:
        """
        Stage 2: Generate each individual material with progress tracking.

        Args:
            materials_plan: List of material specifications from Stage 1
            weekly_topics: List of weekly topic dictionaries
            mission_prompt: Optional guiding prompt for course context and goals
            slide_theme: Optional theme name for slides.md (default: nmt-theme)

        Returns:
            Dictionary mapping week numbers to learning materials
        """
        log.info(
            f"{Colors.BLUE}📝 Stage 2: Generating {len(materials_plan)} individual materials...{Colors.END}"
        )

        # Build course context
        course_context = self._build_course_context(weekly_topics, mission_prompt)
        industry_context = self._build_industry_context()

        # Create a mapping of week numbers to topics for easy lookup
        week_topics = {week["week"]: week for week in weekly_topics}

        # Initialize results dictionary
        learning_materials = {}

        # Generate each material with progress tracking
        for i, material_spec in enumerate(materials_plan, 1):
            try:
                filename = material_spec.get("filename", "")
                title = material_spec.get("title", "")
                week_num = material_spec.get("week", 0)

                log.info(
                    f"{Colors.CYAN}🔄 Generating {filename} for Week {week_num}: {title} ({i}/{len(materials_plan)}){Colors.END}"
                )

                # Get the week's topics
                week_topic = week_topics.get(week_num, {})
                if not week_topic:
                    log.warning(
                        f"{Colors.YELLOW}⚠️  No topics found for Week {week_num}, skipping{Colors.END}"
                    )
                    continue

                # Build previous weeks context for continuity
                previous_weeks_context = self._build_previous_weeks_context(
                    weekly_topics, week_num
                )

                # Generate the material content
                content = self._generate_single_material(
                    material_spec,
                    week_topic,
                    course_context,
                    industry_context,
                    previous_weeks_context,
                    mission_prompt,
                    slide_theme=slide_theme if "slides" in filename.lower() else None,
                )

                if content:
                    # Initialize week entry if it doesn't exist
                    if week_num not in learning_materials:
                        learning_materials[week_num] = {}

                    # Store the content with the filename as key
                    learning_materials[week_num][filename] = content

                    log.info(
                        f"{Colors.GREEN}✅ Generated {filename} for Week {week_num} ({i}/{len(materials_plan)}){Colors.END}"
                    )
                else:
                    log.error(
                        f"{Colors.RED}❌ Failed to generate {filename} for Week {week_num}{Colors.END}"
                    )

            except Exception as e:
                log.error(
                    f"{Colors.RED}❌ Error generating material {i}: {e}{Colors.END}"
                )
                continue

        log.info(
            f"{Colors.GREEN}✅ Completed generation of {len(materials_plan)} materials{Colors.END}"
        )
        return learning_materials

    def _generate_single_material(
        self,
        material_spec: Dict[str, Any],
        week_topic: Dict[str, Any],
        course_context: str,
        industry_context: str,
        previous_weeks_context: str,
        mission_prompt: Optional[str] = None,
        slide_theme: Optional[str] = None,
    ) -> Optional[str]:
        """
        Generate a single learning material based on its specification.

        Args:
            material_spec: Material specification from the plan
            week_topic: Topic information for the specific week
            course_context: Overall course context
            industry_context: Industry contextualization
            previous_weeks_context: Context about previous weeks for continuity
            mission_prompt: Optional mission prompt
            slide_theme: Optional theme name for slides.md (default: nmt-theme)

        Returns:
            Generated content as string, or None if failed
        """
        filename = material_spec.get("filename", "")
        title = material_spec.get("title", "")
        week_num = material_spec.get("week", 0)
        description = material_spec.get("description", "")
        justification = material_spec.get("justification", "")

        # Determine material type and create appropriate prompt
        if "slides" in filename.lower():
            return self._generate_slides_content(
                week_topic,
                course_context,
                industry_context,
                previous_weeks_context,
                title,
                description,
                justification,
                slide_theme=slide_theme,
            )
        elif "demo" in filename.lower():
            return self._generate_demo_content(
                week_topic,
                course_context,
                industry_context,
                previous_weeks_context,
                title,
                description,
                justification,
            )
        else:
            log.warning(
                f"{Colors.YELLOW}⚠️  Unknown material type: {filename}{Colors.END}"
            )
            return None

    def _generate_slides_content(
        self,
        week_topic: Dict[str, Any],
        course_context: str,
        industry_context: str,
        previous_weeks_context: str,
        title: str,
        description: str,
        justification: str,
        slide_theme: Optional[str] = None,  # NEW: allow theme override
    ) -> Optional[str]:
        """Generate slides content for a specific week with Marp/YAML compliance and theme support."""

        # Determine theme: user override or default
        theme = slide_theme or "nmt-theme"
        theme_path_comment = """
# To override the default theme, provide a custom CSS file and set the 'theme' field in the YAML front matter to the theme name defined in your CSS (e.g., @theme my-custom-theme). Place your CSS in the appropriate location and ensure Marp can access it during conversion.
"""

        # Marp/YAML/slide structure guidelines (from real examples):
        marp_guidelines = f"""
CRITICAL SLIDES.MD FORMAT REQUIREMENTS:
- The file MUST start with a YAML front matter block delimited by '---' at the top and bottom.
- The YAML front matter MUST include at least:
    marp: true
    theme: {theme}
    title: <Session Title>
    footer: "![height:50px](footer.png)"
    (Optionally: paginate: true, and any other Marp YAML fields)
- Each slide is separated by a line with only '---'.
- Use Markdown headings (#, ##, ###) for slide titles and structure.
- You MAY use HTML (e.g., <style>, <table>, <img>, <!-- _class: ... -->) for advanced formatting.
- Images can be included with Markdown or HTML. For footers, use: footer: "![height:50px](footer.png)" in YAML.
- You MAY use Marp slide classes (e.g., <!-- _class: lead -->) for layout.
- All content must be valid Markdown/HTML and render correctly in Marp.
- The slides.md must be visually engaging, using the provided theme for consistent branding.
- {theme_path_comment if not slide_theme else ""}
"""

        # Custom steps for slides generation
        custom_steps = [
            f"First, analyze the slide structure and flow for Week {week_topic.get('week', 0)}: Start with clear learning objectives and agenda; Present concepts in logical progression; Include practical examples and case studies; Provide opportunities for student engagement; End with summary and next steps",
            f"Design slides that: Are Marp-compliant, start with YAML front matter, use the '{theme}' theme, and follow the provided guidelines; Include both theoretical and practical content; Incorporate industry-relevant examples; Support different learning styles; Prepare students for assessments; Build upon and complement previous weeks",
            f"Plan for the specific week type: Regular academic content with comprehensive slides; Focus on review materials, practice content, and reassessment preparation; Focus on final submission guidelines, course completion content, and no-contact period information",
        ]

        prompt = f"""Generate a Marp-compliant slides.md for Week {week_topic.get("week", 0)}: {title}

DESCRIPTION: {description}
JUSTIFICATION: {justification}

WEEK TOPIC: {week_topic.get("title", "")}
WEEK TOPICS: {", ".join(week_topic.get("topics", []))}

{course_context}
{industry_context}
{previous_weeks_context}

{marp_guidelines}

{self._format_chain_of_thought_header(custom_steps)}

Generate slides in Markdown format with:
- YAML front matter as described above
- Clear headings and subheadings
- Bullet points for key concepts
- Code examples where appropriate
- Practical exercises and activities
- Industry case studies and examples
- Assessment preparation content
- References to previous weeks' content for continuity

{self._format_formatting_requirements("slides content")}

{self._format_thought_answer_structure("SLIDES_CONTENT")}
"""

        max_retries = 3
        for attempt in range(max_retries):
            response, success = self._safe_prompt_with_retries(
                prompt,
                max_retries=1,  # Only one try per outer attempt
                response_type="SLIDES_CONTENT",
                json_expected=False,
            )
            if success and response and self._validate_slides_md(response, theme):
                return response
        return None

    def _validate_slides_md(self, content: str, theme: str) -> bool:
        """Validate that slides.md is Marp-compliant with required YAML and structure."""
        import re

        # Check for YAML front matter at the top
        yaml_match = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
        if not yaml_match:
            return False
        yaml_block = yaml_match.group(1)
        # Check required YAML fields
        required_fields = ["marp: true", f"theme: {theme}", "title:", "footer:"]
        for field in required_fields:
            if field not in yaml_block:
                return False
        # Check for at least one slide separator after YAML
        after_yaml = content[yaml_match.end() :]
        if re.search(r"^---\s*$", after_yaml, re.MULTILINE) is None:
            return False
        return True

    def _generate_demo_content(
        self,
        week_topic: Dict[str, Any],
        course_context: str,
        industry_context: str,
        previous_weeks_context: str,
        title: str,
        description: str,
        justification: str,
    ) -> Optional[str]:
        """Generate demo content for a specific week."""

        # Custom steps for demo generation
        custom_steps = [
            f"First, analyze the demo structure for Week {week_topic.get('week', 0)}: Start with setup and introduction; Include step-by-step tutorials; Provide hands-on exercises; Include troubleshooting and best practices; End with reflection and next steps",
            f"Design demo content that: Is practical and hands-on; Uses industry-relevant tools; Includes code examples and exercises; Provides real-world scenarios; Supports assessment preparation; Builds upon and complements previous weeks",
            f"Plan for the specific week type: Regular academic content with comprehensive demos; Focus on review exercises, practice demos, and reassessment preparation; Focus on final project demos, course completion exercises, and no-contact period guidance",
        ]

        prompt = f"""Generate comprehensive demo/workshop content for Week {week_topic.get("week", 0)}: {title}

DESCRIPTION: {description}
JUSTIFICATION: {justification}

WEEK TOPIC: {week_topic.get("title", "")}
WEEK TOPICS: {", ".join(week_topic.get("topics", []))}

{course_context}
{industry_context}
{previous_weeks_context}

{self._format_chain_of_thought_header(custom_steps)}

Generate demo content in Markdown format that can be converted to Jupyter notebook via jupytext:
- Use markdown cells for explanations
- Include code cells with Python examples
- Add practical exercises and challenges
- Include industry case studies
- Provide troubleshooting guidance
- Add reflection and assessment questions
- Build upon concepts from previous weeks

{self._format_formatting_requirements("demo content")}

{self._format_thought_answer_structure("DEMO_CONTENT")}
"""

        response, success = self._safe_prompt_with_retries(
            prompt,
            max_retries=3,
            response_type="DEMO_CONTENT",
            json_expected=False,
        )

        return response if success else None

    def _format_chain_of_thought_header(
        self, custom_steps: Optional[List[str]] = None
    ) -> str:
        """Format the chain of thought header with course-specific values."""
        base_header = self.CHAIN_OF_THOUGHT_HEADER.format(
            course_type=self.course_config.course_type.lower(),
            num_weeks=self.course_config.num_weeks,
            academic_weeks=self.course_config.academic_weeks,
        )

        if custom_steps:
            # Replace the default steps with custom ones
            lines = base_header.split("\n")
            # Find where the numbered steps start and replace them
            for i, line in enumerate(lines):
                if line.strip().startswith("1. First,"):
                    # Replace the existing steps with custom ones
                    new_lines = lines[:i]
                    for j, step in enumerate(custom_steps, 1):
                        new_lines.append(f"{j}. {step}")
                    new_lines.extend(lines[i + 4 :])  # Skip the original 4 steps
                    return "\n".join(new_lines)

        return base_header

    def _format_thought_answer_structure(self, response_type: str) -> str:
        """Format the thought and answer structure with the specified response type."""
        return self.THOUGHT_ANSWER_STRUCTURE.format(response_type=response_type)

    def _format_formatting_requirements(
        self, content_type: str = "descriptions"
    ) -> str:
        """Format the formatting requirements with content-specific language."""
        return self.FORMATTING_REQUIREMENTS.replace("descriptions", content_type)

    def _build_industry_context(self) -> str:
        """Build standardized industry contextualization context."""
        industry = getattr(self.course_config, "industry_context", None)
        if not industry:
            return ""

        if isinstance(industry, dict):
            return f"""
INDUSTRY CONTEXTUALIZATION:
- Primary Industry: {industry.get("primary_industry", "Information Technology")}
- Industry Focus: {industry.get("industry_focus", "Software Development and Data Analytics")}
- Industry Tools: {", ".join(industry.get("specific_tools", ["Python", "SQL", "Power BI", "Azure"]))}
- Industry Standards: {", ".join(industry.get("industry_standards", ["Agile methodologies", "DevOps practices"]))}
- Workplace Context: {industry.get("workplace_context", "Modern software development environments with cloud-based tools")}
- Industry Partners: {", ".join(industry.get("industry_partners", ["Local software companies", "Government departments"]))}
"""
        elif isinstance(industry, str):
            return f"""
INDUSTRY CONTEXTUALIZATION:
{industry}
"""
        else:
            return """"""

    def _build_course_context(
        self, weekly_topics: List[Dict[str, Any]], mission_prompt: Optional[str] = None
    ) -> str:
        """Build standardized course context for learning materials generation."""
        context_parts = []

        # Course configuration context
        context_parts.append(f"Course Type: {self.course_config.course_type}")
        context_parts.append(f"Total Weeks: {self.course_config.num_weeks}")
        context_parts.append(f"Academic Weeks: {self.course_config.academic_weeks}")
        context_parts.append(
            f"Reassessment Weeks: {self.course_config.reassessment_weeks}"
        )

        # Learning phases context
        learning_phases = self.course_config.get_learning_phases()
        if learning_phases:
            phases_info = []
            for phase, weeks in learning_phases.items():
                phases_info.append(f"{phase.title()}: Weeks {min(weeks)}-{max(weeks)}")
            context_parts.append(f"Learning Phases: {', '.join(phases_info)}")

        # Mission prompt context
        if mission_prompt:
            context_parts.append(f"Course Context and Goals:\n{mission_prompt}")

        # Weekly topics summary
        if weekly_topics:
            topics_summary = []
            for week in weekly_topics:
                topics_summary.append(f"Week {week['week']}: {week['title']}")
            context_parts.append(f"Weekly Topics:\n" + "\n".join(topics_summary))

        return "\n\n".join(context_parts)

    def _build_course_structure_context(self) -> str:
        """Build standardized course structure context."""
        context_parts = []

        # Course structure information
        context_parts.append(
            f"Course Structure: {self.course_config.num_weeks}-week {self.course_config.course_type} course"
        )
        context_parts.append(
            f"Academic Period: {self.course_config.academic_weeks} weeks"
        )

        if self.course_config.has_reassessment_weeks:
            context_parts.append(
                f"Reassessment Period: {self.course_config.reassessment_weeks} weeks"
            )
            context_parts.append(
                "Assessment Strategy: All assessments must be passed for competency"
            )
        else:
            context_parts.append(
                "Assessment Strategy: Continuous assessment throughout the course"
            )

        # Learning phases
        learning_phases = self.course_config.get_learning_phases()
        if learning_phases:
            phases_info = []
            for phase, weeks in learning_phases.items():
                phases_info.append(f"{phase.title()}: Weeks {min(weeks)}-{max(weeks)}")
            context_parts.append(f"Learning Progression: {', '.join(phases_info)}")

        return "\n".join(context_parts)

    def _build_learning_phases_context(self) -> str:
        """Build standardized learning phases context."""
        learning_phases = self.course_config.get_learning_phases()

        if not learning_phases:
            return "Learning Structure: Single-phase course with progressive skill development"

        phases_info = []
        for phase, weeks in learning_phases.items():
            week_range = f"Weeks {min(weeks)}-{max(weeks)}"
            if phase == "foundation":
                phases_info.append(
                    f"{phase.title()} ({week_range}): Establish core concepts and fundamental skills"
                )
            elif phase == "development":
                phases_info.append(
                    f"{phase.title()} ({week_range}): Build upon foundations with intermediate concepts"
                )
            elif phase == "application":
                phases_info.append(
                    f"{phase.title()} ({week_range}): Apply knowledge to practical scenarios"
                )
            elif phase == "advanced":
                phases_info.append(
                    f"{phase.title()} ({week_range}): Master complex concepts and advanced techniques"
                )
            elif phase == "synthesis":
                phases_info.append(
                    f"{phase.title()} ({week_range}): Integrate all learning into comprehensive understanding"
                )
            else:
                phases_info.append(
                    f"{phase.title()} ({week_range}): Continue skill development and knowledge application"
                )

        return "Learning Phases:\n" + "\n".join(phases_info)

    def _build_unit_context(
        self, units: List[Dict[str, Any]], mission_prompt: Optional[str] = None
    ) -> Tuple[str, str]:
        """Build standardized unit context and unit information."""
        mission_context = ""
        if mission_prompt:
            mission_context = f"\n\nCourse Context and Goals:\n{mission_prompt}\n"

        if self.course_config.has_units_of_competency and units:
            unit_info = "\n".join([f"- {unit['id']}: {unit['name']}" for unit in units])
            unit_context = f"Based on the following units of competency{mission_context}, generate the requested content using chain of thought reasoning:"
        else:
            unit_info = (
                "This course focuses on practical skills and knowledge development."
            )
            unit_context = (
                f"Generate the requested content using chain of thought reasoning:"
            )

        return unit_info, unit_context

    def _build_previous_weeks_context(
        self, weekly_topics: List[Dict[str, Any]], current_week: int, window: int = 3
    ) -> str:
        """
        Build context about previous weeks' content for continuity.

        Args:
            weekly_topics: List of all weekly topic dictionaries
            current_week: The week number for which we're generating content
            window: Number of previous weeks to include (default: 3)

        Returns:
            String containing context about previous weeks
        """
        if not weekly_topics or current_week <= 1:
            return ""

        context_parts = ["PREVIOUS WEEKS CONTEXT:"]

        # Calculate the range of previous weeks to include
        start_week = max(1, current_week - window)
        end_week = current_week - 1

        # Get previous weeks within the window
        previous_weeks = [
            week
            for week in weekly_topics
            if start_week <= week.get("week", 0) <= end_week
        ]

        if not previous_weeks:
            return ""

        # Sort by week number to ensure proper order
        previous_weeks.sort(key=lambda x: x.get("week", 0))

        for week in previous_weeks:
            context_parts.append(
                f"Week {week.get('week', 'N/A')}: {week.get('title', 'Previous Content')}"
            )
            if week.get("topics"):
                topics = [f"  - {topic}" for topic in week["topics"]]
                context_parts.extend(topics)

        return "\n".join(context_parts)

    def _fallback_learning_materials(
        self, weekly_topics: List[Dict[str, Any]]
    ) -> Dict[int, Dict[str, str]]:
        """Fallback learning materials when GPT is not available."""
        materials = {}
        for week in weekly_topics:
            materials[week["week"]] = self._fallback_learning_materials_week(week)
        return materials

    def _fallback_learning_materials_week(self, week: Dict[str, Any]) -> Dict[str, str]:
        """Fallback learning materials for a single week."""
        slides_content = f"""# Session {week["week"]}: {week["title"]}

## Learning Objectives
- Understand the key concepts of {week["title"]}
- Apply theoretical knowledge to practical scenarios
- Develop hands-on skills in relevant tools and technologies

## Topics Covered
{chr(10).join([f"- {topic}" for topic in week["topics"]])}

## Key Concepts
- Concept 1: Description and importance
- Concept 2: Practical applications
- Concept 3: Industry relevance

## Practical Applications
- Real-world examples and case studies
- Industry tools and technologies
- Best practices and methodologies

## Assessment Preparation
- Review of assessment criteria
- Practice exercises and activities
- Feedback and improvement strategies

## Summary
- Key takeaways from this session
- Connection to previous and upcoming content
- Next steps and preparation for future sessions
"""

        demo_content = f"""# Session {week["week"]}: {week["title"]} - Practical Workshop

## Introduction
This workshop provides hands-on experience with {week["title"]} concepts and tools.

## Setup and Preparation
```python
# Import required libraries
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
```

## Main Concepts
### Concept 1: {week["topics"][0] if week["topics"] else "Key Concept"}
```python
# Example code demonstrating the concept
print("Practical example of the concept")
```

### Concept 2: {week["topics"][1] if len(week["topics"]) > 1 else "Advanced Concept"}
```python
# More advanced example
def practical_function():
    return "Hands-on implementation"
```

## Hands-on Exercises
### Exercise 1: Basic Practice
Complete the following exercise to reinforce your understanding.

### Exercise 2: Applied Learning
Apply the concepts to a real-world scenario.

## Industry Case Study
Work through a real industry example that demonstrates practical application.

## Assessment Preparation
Review assessment requirements and practice relevant skills.

## Reflection and Next Steps
- What did you learn today?
- How will you apply these concepts?
- What questions do you have for next session?
"""

        return {"slides.md": slides_content, "demo.md": demo_content}

    def _fallback_course_overview(self, units: List[Dict[str, Any]]) -> str:
        """Fallback course overview when GPT is not available."""
        unit_list = []
        for unit in units:
            unit_id = unit.get("id", "Unit")
            unit_name = unit.get("name", "Unit")
            unit_list.append(f"- {unit_id}: {unit_name}")

        unit_list_str = "\n".join(unit_list)

        return f"""Course Overview

This {self.course_config.course_type} course provides comprehensive training in practical skills and knowledge development. The course is designed to prepare students for real-world applications in their chosen field.

Course Structure:
- Duration: {self.course_config.num_weeks} weeks
- Academic Period: {self.course_config.academic_weeks} weeks
- Assessment Strategy: {self.course_config.course_type} competency-based assessment

Units of Competency:
{unit_list_str}

Learning Outcomes:
Students will develop practical skills and theoretical knowledge through hands-on activities, industry-relevant projects, and comprehensive assessments. The course emphasizes real-world application and workplace readiness.

Assessment Approach:
All assessments must be completed successfully to achieve competency. The course provides multiple opportunities for demonstration of skills and knowledge throughout the learning journey.

Industry Context:
The course content is aligned with industry standards and practices, ensuring graduates are well-prepared for workplace challenges and opportunities."""

    def _fallback_weekly_topics(
        self, units: List[Dict[str, Any]], num_weeks: int
    ) -> List[Dict[str, Any]]:
        """Fallback weekly topics when GPT is not available."""
        topics = []
        learning_phases = self.course_config.get_learning_phases()

        for week in range(1, num_weeks + 1):
            # Determine which phase this week belongs to
            phase = "foundation"
            for phase_name, weeks in learning_phases.items():
                if week in weeks:
                    phase = phase_name
                    break

            # Generate topic based on phase
            if phase == "foundation":
                title = f"Introduction to {units[0]['name'] if units else 'Course Concepts'}"
                topics_list = [
                    "Basic concepts and terminology",
                    "Fundamental principles",
                    "Introduction to tools and technologies",
                ]
                activity = "Hands-on workshop introducing basic concepts and tools"
            elif phase == "development":
                title = f"Building {units[0]['name'] if units else 'Core Skills'}"
                topics_list = [
                    "Intermediate concepts and techniques",
                    "Skill development and practice",
                    "Problem-solving approaches",
                ]
                activity = "Practical exercises focusing on skill development"
            elif phase == "application":
                title = f"Applying {units[0]['name'] if units else 'Knowledge'}"
                topics_list = [
                    "Real-world applications",
                    "Case studies and scenarios",
                    "Practical implementation",
                ]
                activity = "Case study analysis and practical application"
            elif phase == "advanced":
                title = f"Advanced {units[0]['name'] if units else 'Techniques'}"
                topics_list = [
                    "Advanced concepts and methodologies",
                    "Complex problem-solving",
                    "Industry best practices",
                ]
                activity = "Advanced workshop with complex scenarios"
            elif phase == "synthesis":
                title = f"Integration and {units[0]['name'] if units else 'Synthesis'}"
                topics_list = [
                    "Integration of all concepts",
                    "Comprehensive understanding",
                    "Final project preparation",
                ]
                activity = "Comprehensive project work and integration"
            else:
                title = f"Week {week}: Continued Learning"
                topics_list = [
                    "Continued skill development",
                    "Knowledge application",
                    "Assessment preparation",
                ]
                activity = "Guided practice and assessment preparation"

            topics.append(
                {
                    "week": week,
                    "title": title,
                    "topics": topics_list,
                    "activity": activity,
                }
            )

        return topics

    def _fallback_assessment_descriptions(
        self, units: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Fallback assessment descriptions when GPT is not available."""
        assessments = []

        # Assessment 1: Early assessment (Weeks 4-8)
        assessments.append(
            {
                "assessment_number": 1,
                "title": "Foundation Assessment",
                "description": "Assessment of foundational concepts and basic skills. Students will demonstrate understanding of core principles and complete practical exercises.",
                "week_range": "Weeks 4-8",
                "assessment_type": "Practical and Written",
                "weighting": "25%",
            }
        )

        # Assessment 2: Mid-course assessment (Weeks 9-12)
        assessments.append(
            {
                "assessment_number": 2,
                "title": "Application Assessment",
                "description": "Assessment of applied knowledge and intermediate skills. Students will work on case studies and demonstrate practical application of concepts.",
                "week_range": "Weeks 9-12",
                "assessment_type": "Project-based",
                "weighting": "30%",
            }
        )

        # Assessment 3: Advanced assessment (Weeks 13-16)
        assessments.append(
            {
                "assessment_number": 3,
                "title": "Advanced Skills Assessment",
                "description": "Assessment of advanced techniques and complex problem-solving. Students will tackle challenging scenarios and demonstrate mastery of advanced concepts.",
                "week_range": "Weeks 13-16",
                "assessment_type": "Complex Problem-solving",
                "weighting": "25%",
            }
        )

        # Assessment 4: Final assessment (Week 18)
        assessments.append(
            {
                "assessment_number": 4,
                "title": "Final Comprehensive Assessment",
                "description": "Comprehensive assessment covering all course content. Students will demonstrate complete competency across all learning outcomes.",
                "week_range": "Week 18",
                "assessment_type": "Comprehensive",
                "weighting": "20%",
            }
        )

        return assessments

    def _fallback_learning_activities(
        self, weekly_topics: List[Dict[str, Any]]
    ) -> List[str]:
        """Fallback learning activities when GPT is not available."""
        activities = []

        for week_topic in weekly_topics:
            activity = f"""Week {week_topic["week"]}: {week_topic["title"]}

Learning Activity: {week_topic["activity"]}

Key Learning Points:
{chr(10).join([f"- {topic}" for topic in week_topic["topics"]])}

Activity Description:
This week's activity focuses on practical application of the concepts covered. Students will engage in hands-on exercises, group discussions, and individual practice to reinforce their understanding.

Learning Outcomes:
- Demonstrate understanding of key concepts
- Apply theoretical knowledge to practical scenarios
- Develop hands-on skills and competencies
- Prepare for assessment requirements

Assessment Preparation:
- Review assessment criteria and requirements
- Practice relevant skills and techniques
- Seek feedback and clarification as needed
- Complete preparatory exercises and activities"""

            activities.append(activity)

        return activities

    def _fallback_learning_resources(
        self, weekly_topics: List[Dict[str, Any]]
    ) -> List[str]:
        """Fallback learning resources when GPT is not available."""
        resources = []

        for week_topic in weekly_topics:
            resource = f"""Week {week_topic["week"]}: {week_topic["title"]}

Required Resources:
- Course textbook and supplementary materials
- Online learning platform access
- Industry-standard tools and software
- Practice datasets and case studies

Recommended Reading:
- Chapter {week_topic["week"]} of the main textbook
- Industry articles and case studies
- Online tutorials and documentation
- Best practice guides and standards

Additional Resources:
- Video tutorials and demonstrations
- Interactive exercises and simulations
- Peer learning opportunities
- Industry expert guest lectures

Assessment Resources:
- Assessment criteria and rubrics
- Practice questions and exercises
- Sample assessments and solutions
- Feedback and improvement guidelines"""

            resources.append(resource)

        return resources


def create_gpt_generator(
    course_config: Optional[CourseConfig] = None,
    progress_file: Optional[str] = None,
) -> GPTContentGenerator:
    """
    Create a GPT content generator instance.

    Args:
        course_config: Optional course configuration (defaults to TAFE 20-week course)
        progress_file: Optional progress file for checkpointing

    Returns:
        GPTContentGenerator instance
    """
    return GPTContentGenerator(course_config=course_config, progress_file=progress_file)
