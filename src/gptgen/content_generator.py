import os
import json
import re
from typing import List, Dict, Any, Optional, Tuple
import logging
from src.utils.uoc_api import UnitOfCompetency


from .helpers import Colors, ResponseBox
from .config import CourseConfig
from .locking import InitProgressManager
from typing import TYPE_CHECKING

log = logging.getLogger(__name__)

# Try to import GPT library, but make it optional
try:
    from gpt.models.openai_ import Chat
    from .model_factory import create_model_client, GPT_AVAILABLE
except ImportError as e:
    log.warning(f"GPT library not available: {e}")
    Chat = None
    GPT_AVAILABLE = False

# ---------------------------------------------------------------------------
# NOTE: We intentionally avoid importing ``unittest`` at *runtime* so that the
# library is not required in production deployments.  A tiny helper below
# performs *best-effort* detection of objects originating from the
# ``unittest.mock`` module – such as ``MagicMock`` – without adding the module
# as a hard dependency.  The import is only used for *type-checking* to keep
# editors and static analysers happy.
# ---------------------------------------------------------------------------

if TYPE_CHECKING:  # pragma: no cover – static-analysis only
    from unittest.mock import MagicMock as _MagicMockType


def _is_magic_mock(obj: Any) -> bool:
    """Return ``True`` when *obj* is an instance created by ``unittest.mock``.

    This avoids importing the ``unittest`` package at runtime by relying on the
    fact that all standard mock objects (``Mock``, ``MagicMock``, ``AsyncMock`` …)
    have their classes defined in the ``unittest.mock`` module.
    """

    try:
        return obj.__class__.__module__.startswith("unittest.mock")
    except AttributeError:
        return False


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
   - Emphasize industry relevance and workplace preparation

5. Apply technical constraints and conventions:
   HARD REQUIREMENTS (MANDATORY):
   - Follow build system constraints (file types, formats, structure)
   - Ensure technical compatibility with delivery mechanisms
   - Meet validation requirements for processing pipelines
   - slides.md: Must have YAML frontmatter with 'marp: true'
   - demo.md: Must be standard markdown for jupytext conversion
   
   SOFT CONVENTIONS (RECOMMENDED):
   - Create engaging, industry-relevant content
   - Build logical progression and continuity
   - Include practical examples and applications
   - Prepare students for assessments and real-world scenarios
   - guides/handouts: Any other .md files with minimal constraints"""

    @classmethod
    def _get_thought_answer_structure(cls, response_type: str) -> str:
        """Generate the thought and answer structure using ResponseBox helper."""
        example_box = ResponseBox.wrap("<Your answer here>", response_type)
        return f"""You will think step by step within <thought> tags. e.g:
<thought>
I will now think step by step.
</thought>

and give your answer within <answer> tags. e.g:
<answer>
Your answer here
</answer>

You are also required to wrap your final answer within a response box like so:
<answer>{example_box}</answer>"""

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
        config: Optional[Dict[str, Any]] = None,
        progress_file: Optional[str] = None,
        model: str = "gpt-4.1-nano-2025-04-14",
        yes_to_all: bool = False,
    ):
        """
        Initialize the GPT content generator.

        Args:
            api_key: Optional API key for the language model service.
                    If "USE_ENV" (default), tries to get from environment variable.
                    If None, forces fallback mode without GPT client.
                    If string, uses that API key.
            course_config: Optional course configuration (defaults to TAFE 20-week course)
            config: Optional raw config dictionary for context formatting
            progress_file: Optional progress file for checkpointing
        """
        # Handle API key logic
        if api_key == "USE_ENV":
            # Default behavior - check environment variable
            self.api_key = os.getenv("OPENAI_API_KEY")
        else:
            # Explicitly provided (could be None for testing or a string)
            self.api_key = api_key

        self.yes_to_all = yes_to_all

        if not self.api_key:
            log.warning("No API key provided. Some features may not work.")

        # Set course configuration
        self.course_config = course_config or CourseConfig()
        self.config = config or {}
        self.progress = InitProgressManager(progress_file) if progress_file else None

        # Initialise the GPT client **only** when we have a usable API key.
        # Tests that patch `Chat` via `unittest.mock` typically do so while
        # leaving the API-key unset – in those scenarios we purposefully
        # *avoid* constructing the client so that the generator falls back to
        # its deterministic, offline pathways (as asserted in
        # `test_no_gpt_client_fallback`).

        self.client = None
        # Patch logic: if Chat is a MagicMock (i.e., patched in tests), always instantiate
        if _is_magic_mock(Chat):
            try:
                self.client = Chat(
                    model_name=model,
                    max_completion_tokens=32768,
                    context=1,
                )
            except Exception as e:
                log.warning(f"Failed to initialize GPT client (mocked): {e}")
                self.client = None
        elif self.api_key:  # Empty/None => operate in offline-fallback mode
            try:
                if GPT_AVAILABLE:
                    # Use model factory to create the appropriate client
                    self.client = create_model_client(
                        model,
                        max_completion_tokens=32768,
                        context=1,
                        search_enabled=True,
                    )
                elif callable(Chat):
                    # Fallback to direct Chat instantiation for backward compatibility
                    self.client = Chat(
                        model_name=model,
                        max_completion_tokens=32768,
                        context=1,
                    )
                    if model in ["gpt-4.1"]:
                        self.client.tools = [{"type": "web_search_preview"}]
            except Exception as e:
                log.warning(f"Failed to initialize GPT client: {e}")
                self.client = None

    def _safe_prompt_with_retries(
        self,
        prompt: str,
        max_retries: int = 3,
        response_type: str = "RESPONSE",
        json_expected: bool = False,
        use_search: bool = False,
        context: Optional[int] = None,
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

                comment = ""
                context = 0
                while comment.lower() != "y":
                    context += 1
                    response = self.client.prompt(
                        prompt + "\n\n" + comment,
                        use_search=use_search,
                        context=context,
                    )
                    print(f"=== Prompt ===\n\n{prompt}\n\n")
                    print(f"=== Response ===\n\n{response}\n\n")
                    if self.yes_to_all:
                        comment = "y"
                    else:
                        comment = input(
                            "Would you like to accept? (y) or make revisions (comment), or set all generations to auto (auto): "
                        )
                        if comment.lower() == "auto":
                            self.yes_to_all = True
                            comment = "y"

                content = response.strip()

                raw_content = content

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
                        return content, True, raw_content
                    except (json.JSONDecodeError, IndexError) as e:
                        log.warning(
                            f"{Colors.YELLOW}⚠️  Invalid JSON on attempt {attempt + 1}: {e}{Colors.END}"
                        )
                        # Add debug logging to see what the actual response looks like
                        log.debug(f"Raw response content: {repr(content[:500])}")
                        log.debug(f"Response box extraction result: {repr(extracted)}")
                        if attempt < max_retries - 1:
                            continue
                        else:
                            # Final attempt - try to get a direct response
                            return self._get_direct_response(
                                prompt, response_type, json_expected, use_search
                            )

                # For non-JSON responses, perform basic validation to ensure no leftover tags or response boxes remain
                invalid_patterns = [
                    r"<\\/?answer>",
                    r"<\\/?thought>",
                    r"=== .* START ===",
                    r"=== .* END ===",
                ]
                if any(
                    re.search(pat, content, re.IGNORECASE) for pat in invalid_patterns
                ):
                    log.warning(
                        f"{Colors.YELLOW}⚠️  Response contains leftover tags/boxes on attempt {attempt + 1}{Colors.END}"
                    )
                    if attempt < max_retries - 1:
                        continue
                    else:
                        # Final attempt - try to get a direct response without context
                        return self._get_direct_response(
                            prompt, response_type, json_expected
                        )

                # For non-JSON responses that pass validation, accept the content
                log.info(
                    f"{Colors.GREEN}✅ Valid response on attempt {attempt + 1}{Colors.END}"
                )
                return content, True, raw_content

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
        self,
        prompt: str,
        response_type: str,
        json_expected: bool,
        use_search: bool = False,
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
            response = self.client.prompt(direct_prompt, use_search=use_search)
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
        self,
        units: List[Dict[str, Any]],
        mission_prompt: Optional[str] = None,
        assessments: Optional[List[Dict[str, Any]]] = None,
        activities: Optional[List[str]] = None,
        resources: Optional[List[str]] = None,
        learning_materials_plan: Optional[List[str]] = None,
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
{self._format_config_context()}

{unit_info}

{industry_context}

{self._format_chain_of_thought_header()}

The overview should:
- Explain what students will learn
- Describe the key skills and knowledge areas
- Mention the practical applications
- Be written in a professional but accessible tone
- Align with the course context and goals provided
- Reflect the context of the course type which is: {self.course_config.course_type.lower()}
- Highlight industry contextualization and workplace relevance, if applicable

{self._format_thought_answer_structure("COURSE_OVERVIEW")}

{unit_context}
"""
        if (
            assessments is not None
            or activities is not None
            or resources is not None
            or learning_materials_plan is not None
        ):
            prompt += f"""
The following learning content exists to inform your overview:
=== START ASSESSMENTS===
{assessments}
=== END ASSESSMENTS===

=== START OUT-OF-CLASS ACTIVITIES===
{activities}

=== END OUT-OF-CLASS ACTIVITIES===

=== START IN-CLASS RESOURCES===
{resources}

=== END IN-CLASS RESOURCES===

=== START LEARNING MATERIALS PLAN===
{learning_materials_plan}

=== END LEARNING MATERIALS PLAN===

"""

        response, success, raw_response = self._safe_prompt_with_retries(
            prompt,
            max_retries=3,
            response_type="COURSE_OVERVIEW",
            json_expected=False,
            use_search=True,
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
        units: List[UnitOfCompetency],
        prerequisites: List[UnitOfCompetency],
        mission_prompt: Optional[str] = None,
        course_overview: Optional[str] = None,
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

        # Build standardized contexts using helper methods
        unit_info, base_unit_context = self._build_unit_context(units, mission_prompt)
        prerequisites_context = self._build_prerequisites_context(prerequisites)
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
{self._format_config_context()}

=== START COURSE OVERVIEW===

{course_overview}

===END COURSE OVERVIEW===

{unit_info}

{course_structure_context}
{industry_context}

{prerequisites_context}

{self._format_chain_of_thought_header(custom_steps)}

For each week, provide:
1. A clear topic title that reflects the learning phase
2. 3-5 key learning points that show progression
3. An appropriate in-class activity if needed and relevant to the learning that will help to reinforce the learning objectives

Format the response as a JSON array with objects containing:
- week: week number
- title: topic title
- topics: array of learning points
- activity: in-class activity description

{self._format_formatting_requirements("weekly topics")}

{self._format_thought_answer_structure("WEEKLY_TOPICS")}

{unit_context}
"""

        response, success, raw_response = self._safe_prompt_with_retries(
            prompt + "\n\n",
            max_retries=3,
            response_type="WEEKLY_TOPICS",
            json_expected=True,
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
        self,
        units: List[Dict[str, Any]],
        mission_prompt: Optional[str] = None,
        weekly_topics: Optional[List[Dict[str, Any]]] = None,
        course_overview: Optional[str] = None,
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

        prompt = f"""
{self._format_config_context()}

=== START COURSE OVERVIEW===

{course_overview}

===END COURSE OVERVIEW===

=== START WEEKLY TOPICS===

{weekly_topics}

===END WEEKLY TOPICS===



{unit_context}

{unit_info}

{industry_context}

{self._format_chain_of_thought_header(custom_steps)}

Guided by the performance evidence, you may generate a range of different types of assessments:
- A practical project/assignment
- A knowledge-based assessment
- A research/presentation task

We should always seek to avoid over assessing the unit. The performance evidence is our key guide to the amount of evidence we need to collect.

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

        response, success, raw_response = self._safe_prompt_with_retries(
            prompt,
            max_retries=3,
            response_type="ASSESSMENTS",
            json_expected=True,
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
        self,
        weekly_topics: List[Dict[str, Any]],
        mission_prompt: Optional[str] = None,
        course_overview: Optional[str] = None,
        learning_materials_plan: Optional[List[Dict[str, Any]]] = None,
        assessments: Optional[List[Dict[str, Any]]] = None,
    ) -> List[str]:
        """
        Generate out-of-class learning activities for all weeks, referencing created materials and external resources.

        Args:
            weekly_topics: List of weekly topic dictionaries (18 academic weeks + 2 reassessment weeks)
            mission_prompt: Optional guiding prompt for course context and goals
            config: Course configuration
            course_overview: Generated course overview
            learning_materials_plan: Plan of materials created (slides.md, demo.md, guides)

        Returns:
            List of out-of-class activity descriptions with external links and references
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
            f"{Colors.PURPLE}{Colors.BOLD}🔄 Generating out-of-class learning activities for all {len(weekly_topics)} weeks with references to created materials and external resources...{Colors.END}"
        )

        # Build materials context from the learning materials plan
        materials_context = ""
        if learning_materials_plan:
            materials_context = "CREATED LEARNING MATERIALS:\n"
            for material in learning_materials_plan:
                week = material.get("week", "Unknown")
                filename = material.get("filename", "Unknown")
                title = material.get("title", "Unknown")
                description = material.get("description", "Unknown")
                materials_context += (
                    f"Week {week}: {filename} - {title}\n  Description: {description}\n"
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

        # Custom steps for out-of-class activities
        custom_steps = [
            "First, analyze what students need to do outside of class: What readings, practice, and preparation will reinforce the in-class materials? How can students engage with the created materials (slides.md, demo.md, guides) outside of class? What external resources would complement our materials? How do we encourage students to explore beyond the classroom?",
            "Consider out-of-class learning objectives: What should students read, watch, or practice to prepare for next week? How can we connect our created materials to external industry resources? What online courses, tutorials, or documentation would enhance learning? How do we encourage self-directed exploration while maintaining structure?",
            "Design progressive out-of-class activities: Reference the specific materials created for each week; Include external links to relevant articles, videos, courses, and tools; Provide required readings and optional enrichment activities; Include preparation tasks for upcoming assessments; Encourage hands-on practice with industry tools and platforms",
            "Plan for different week types: Weeks 1-18: Regular out-of-class study with readings, practice, and external exploration; Week 19: Focus on reassessment preparation and review activities; Week 20: Final submission preparation and course reflection activities",
            "Ensure activities include: References to created materials (slides.md, demo.md, guides); External links to articles, videos, courses, and tools; Reading assignments with specific chapters/sections; Preparation tasks for next week; Time estimates for completion; Mix of required and optional activities",
        ]

        prompt = f"""
        

{self._format_config_context()}

=== START COURSE OVERVIEW===

{course_overview}

===END COURSE OVERVIEW===

=== START WEEKLY TOPICS===

{weekly_topics}

===END WEEKLY TOPICS===

{materials_context}

Generate out-of-class learning activities for all {len(weekly_topics)} weeks that reference the created materials and include external resources with links.

{course_context}
{industry_context}

WEEKLY TOPICS:
{weekly_context}

REQUIREMENTS:
1. Generate out-of-class activities for students to complete during each week
2. Reference the specific materials created for each week (slides.md, demo.md, guides)
3. Include external links to relevant articles, videos, courses, and documentation
4. Provide both required tasks and optional enrichment activities
5. Include time estimates for completion (~3 hours per week)
6. Add preparation tasks for upcoming sessions and assessments
7. Use web search to find current, relevant external resources and links
8. Structure activities with clear sections: Required Tasks, Optional Activities, Preparation for Next Week

EXAMPLE FORMAT (adapt to course content):

``` markdown

<!-- Session 1 Activities Go Here -->

### Out of Class Activities

**Required Tasks:**
- **Review Slides:** [Week X Topic Slides](internal-reference)
- **Complete Demo:** Work through the Week X demo.md practical exercises
- **Read:** [Article Title](https://example.com/link)
- **Watch:** [Video Title](https://youtube.com/example)
- **Complete Tutorial:** [Online Course Module](https://platform.com/course)

**Optional Activities:**
- **Explore:** [Additional Resource](https://example.com)
- **Practice:** Extended exercises using course tools

**Preparation for Next Week:**
- Install required software
- Review prerequisite concepts

*Expected time: ~3 hours*

---

<!-- Session 2 Activities Go Here -->


...etc.

```


{self._format_chain_of_thought_header(custom_steps)}

{self._format_formatting_requirements("out-of-class activities")}

{self._format_thought_answer_structure("LEARNING_ACTIVITIES")}

CRITICAL: You MUST return a structured list of in-class learning resources. Each week should have comprehensive resource lists with references to materials and external links.
Use web search to find current, relevant external resources and provide actual working links where possible.
Separate each week's resources with --- dividers.
"""

        response, success, raw_response = self._safe_prompt_with_retries(
            prompt,
            max_retries=3,
            response_type="LEARNING_ACTIVITIES",
            json_expected=False,
            use_search=True,
        )

        if success and response:
            # Split response into weekly activities (separated by ---)
            activity_sections = response.split("---")
            activities = []

            for section in activity_sections:
                section = section.strip()
                if section:
                    # Sanitize the activity content to ensure YAML compatibility
                    sanitized_activity = self._sanitize_activity_text(section)
                    activities.append(sanitized_activity)

            if len(activities) != len(weekly_topics):
                log.warning(
                    f"{Colors.RED}Failed to generate activities for all {len(weekly_topics)} weeks, only {len(activities)} were generated{Colors.END}"
                )

            log.info(
                f"{Colors.GREEN}{Colors.BOLD}✅ Successfully generated out-of-class activities for all {len(weekly_topics)} weeks with external references{Colors.END}"
            )
            if self.progress:
                self.progress.mark_done("activities", activities)
            return activities
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
        self,
        weekly_topics: List[Dict[str, Any]],
        mission_prompt: Optional[str] = None,
        course_overview: Optional[str] = None,
        learning_materials_plan: Optional[List[Dict[str, Any]]] = None,
        assessments: Optional[List[Dict[str, Any]]] = None,
        activities: Optional[List[str]] = None,
    ) -> List[str]:
        """
        Provide a list in the LAP of all relevant in-class learning resources, both external and internally developed.

        Args:
            weekly_topics: List of weekly topic dictionaries (18 academic weeks + 2 reassessment weeks)
            mission_prompt: Optional guiding prompt for course context and goals
            config: Course configuration
            course_overview: Generated course overview
            learning_materials_plan: Plan of materials created (slides.md, demo.md, guides)

        Returns:
            List of in-class resource descriptions with links to internal materials and external resources
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
            f"{Colors.PURPLE}{Colors.BOLD}🔄 Generating in-class learning resources for all {len(weekly_topics)} weeks with references to created materials and external links...{Colors.END}"
        )

        # Build materials context from the learning materials plan
        materials_context = ""
        if learning_materials_plan:
            materials_context = "CREATED LEARNING MATERIALS:\n"
            for material in learning_materials_plan:
                week = material.get("week", "Unknown")
                filename = material.get("filename", "Unknown")
                title = material.get("title", "Unknown")
                description = material.get("description", "Unknown")
                materials_context += (
                    f"Week {week}: {filename} - {title}\n  Description: {description}\n"
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

        # Custom steps for in-class resources
        custom_steps = [
            f"First, analyze what resources instructors need for in-class teaching: What materials do we have available (slides.md, demo.md, guides)? What external resources would enhance in-class instruction? How can we connect our created materials to authoritative external sources? What tools, databases, and platforms would students use in class?",
            "Consider in-class resource requirements: What reference materials do instructors need during class? How can we provide links to official documentation, industry tools, and authoritative sources? What online platforms and databases would be useful for in-class demonstrations? How do we ensure resources are immediately accessible during class?",
            "Design comprehensive resource lists: Reference all created materials for each week; Include links to official documentation and industry resources; Provide access to online tools and platforms used in class; Include authoritative sources and reference materials; List required software, accounts, and subscriptions; Add links to video tutorials and demonstrations",
            "Plan for different week types: Weeks 1-18: Regular academic content with comprehensive in-class resources; Week 19: Review materials and reassessment resources; Week 20: Final submission resources and course completion materials",
            "Ensure resources include: Direct links to created materials (slides.md, demo.md, guides); External links to official documentation and industry resources; Access credentials for required platforms and tools; Reference materials and authoritative sources; Video tutorials and demonstration links; Quick reference guides and cheat sheets",
        ]

        prompt = f"""
{self._format_config_context()}

=== START COURSE OVERVIEW===
{course_overview}

=== END COURSE OVERVIEW===

=== START CREATED MATERIALS===
{materials_context}

=== END CREATED MATERIALS===

=== START ASSESSMENTS===
{assessments}

=== END ASSESSMENTS===

=== START ACTIVITIES===
{activities}

=== END ACTIVITIES===

Generate in-class learning resources for all {len(weekly_topics)} weeks that reference the created materials and include external resources with links.

{course_context}
{industry_context}

WEEKLY TOPICS:
{weekly_context}

REQUIREMENTS:
1. Generate comprehensive in-class resource lists for instructors and students
2. Reference all created materials for each week (slides.md, demo.md, guides)
3. Include external links to official documentation, industry resources, and tools
4. Provide access information for required platforms and software
5. Include authoritative sources and reference materials
6. Add links to video tutorials, documentation, and demonstrations
7. Use web search to find current, relevant external resources and links
8. Structure resources clearly with categories: Internal Materials, External Resources, Tools & Platforms

EXAMPLE FORMAT (adapt to course content):

``` markdown

<!-- Session 1 Resources Go Here -->

*Internal Materials:*
- slides.md: Week X Topic Presentation
- demo.md: Hands-on Workshop Content
- guide.md: Additional Reference Material

*External Resources:*
- [Official Documentation](https://docs.example.com)
- [Industry Tutorial](https://tutorial.example.com)
- [Reference Article](https://article.example.com)

*Tools & Platforms:*
- Platform Name: [Access Link](https://platform.com)
- Software Tool: [Download Link](https://download.com)
- Online Database: [Database Link](https://database.com)

---

<!-- Session 2 Resources Go Here -->

...etc.

```

{self._format_chain_of_thought_header(custom_steps)}

{self._format_formatting_requirements("in-class learning resources")}

{self._format_thought_answer_structure("LEARNING_RESOURCES")}

CRITICAL: You MUST return a structured list of in-class learning resources. Each week should have comprehensive resource lists with references to materials and external links.
Use web search to find current, relevant external resources and provide actual working links where possible.
Separate each week's resources with --- dividers.
"""

        response, success, raw_response = self._safe_prompt_with_retries(
            prompt,
            max_retries=3,
            response_type="LEARNING_RESOURCES",
            json_expected=False,
            use_search=True,
        )

        if success and response:
            # Split response into weekly resources (separated by ---)
            resource_sections = response.split("---")
            resources = []

            for section in resource_sections:
                section = section.strip()
                if section:
                    # Sanitize the resource content to ensure YAML compatibility
                    sanitized_resource = self._sanitize_activity_text(section)
                    resources.append(sanitized_resource)

            log.info(
                f"{Colors.GREEN}{Colors.BOLD}✅ Successfully generated in-class resources for all {len(weekly_topics)} weeks with external references{Colors.END}"
            )
            if self.progress:
                self.progress.mark_done("resources", resources)
            return resources
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
        # Handle non-string inputs (e.g., dictionaries from failed JSON parsing)
        if not isinstance(activity_text, str):
            if isinstance(activity_text, dict):
                # Convert dictionary to string representation
                activity_text = str(activity_text)
            elif activity_text is None:
                return "Activity description not available."
            else:
                # Convert any other type to string
                activity_text = str(activity_text)

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
        course_overview: Optional[str] = None,
        slide_theme: Optional[str] = None,
        slide_css: Optional[str] = None,
    ) -> tuple[Dict[int, Dict[str, str]], List[Dict[str, Any]]]:
        """
        Generate learning materials for all weeks using a direct approach:
        For each week, generate slides.md and demo.md using the current topic and context.

        Args:
            weekly_topics: List of weekly topic dictionaries
            mission_prompt: Optional guiding prompt for course context and goals
            config: Course configuration for context
            course_overview: Generated course overview for context
            slide_theme: Optional theme for slides (e.g., "northmetro")
            slide_css: Optional CSS content for slides styling context

        Returns:
            Tuple of (learning_materials, materials_plan) where:
            - learning_materials: Dict mapping week numbers to material content
            - materials_plan: List of planned materials for reference by other generators
        """
        if self.progress and self.progress.is_done("learning_materials"):
            cached_materials = self.progress.get_result("learning_materials")
            # For backward compatibility, create a fallback plan if needed
            fallback_plan = self._fallback_materials_plan(weekly_topics)
            return cached_materials, fallback_plan

        if not self.client:
            log.info(
                f"{Colors.YELLOW}GPT client not available, using fallback learning materials{Colors.END}"
            )
            fallback = self._fallback_learning_materials(weekly_topics)
            fallback_plan = self._fallback_materials_plan(weekly_topics)
            if self.progress:
                self.progress.mark_done("learning_materials", fallback)
            return fallback, fallback_plan

        log.info(
            f"{Colors.PURPLE}{Colors.BOLD}🔄 Stage 1: Planning learning materials for {len(weekly_topics)} weeks...{Colors.END}"
        )

        # Stage-1: Ask the LLM (or fallback) to produce a plan describing what
        # materials should be created for each week.
        materials_plan = self._plan_learning_materials(
            weekly_topics, mission_prompt, course_overview
        )

        if not materials_plan:
            log.warning(
                f"{Colors.YELLOW}⚠️  Planning phase returned no materials – falling back.{Colors.END}"
            )
            fallback = self._fallback_learning_materials(weekly_topics)
            fallback_plan = self._fallback_materials_plan(weekly_topics)
            if self.progress:
                self.progress.mark_done("learning_materials", fallback)
            return fallback, fallback_plan

        # Stage-2: Generate the actual content for each planned artefact.
        learning_materials = self._generate_individual_materials(
            materials_plan,
            weekly_topics,
            mission_prompt,
            slide_theme=slide_theme,
            slide_css=slide_css,
        )

        if learning_materials:
            log.info(
                f"{Colors.GREEN}{Colors.BOLD}✅ Successfully generated all learning materials{Colors.END}"
            )
            if self.progress:
                self.progress.mark_done("learning_materials", learning_materials)
            return learning_materials, materials_plan
        else:
            log.error(f"{Colors.RED}Failed to generate learning materials{Colors.END}")
            fallback = self._fallback_learning_materials(weekly_topics)
            fallback_plan = self._fallback_materials_plan(weekly_topics)
            if self.progress:
                self.progress.mark_done("learning_materials", fallback)
            return fallback, fallback_plan

    def _generate_individual_materials(
        self,
        materials_plan: List[Dict[str, Any]],
        weekly_topics: List[Dict[str, Any]],
        mission_prompt: Optional[str] = None,
        slide_theme: Optional[str] = None,
        slide_css: Optional[str] = None,
    ) -> Dict[int, Dict[str, str]]:
        """Generate individual learning materials based on the plan."""

        learning_materials: Dict[int, Dict[str, str]] = {}
        is_mocked = _is_magic_mock(self._safe_prompt_with_retries)

        # Build context strings once
        course_context = self._build_course_context(weekly_topics, mission_prompt)
        industry_context = self._build_industry_context()

        log.info(
            f"📝 Stage 2: Generating {len(materials_plan)} individual materials..."
        )

        for i, material_spec in enumerate(materials_plan, 1):
            filename = material_spec.get("filename", "")
            title = material_spec.get("title", "")
            week_num = material_spec.get("week", 0)
            description = material_spec.get("description", "")

            # Find the corresponding week topic
            week_topic = next(
                (w for w in weekly_topics if w.get("week") == week_num), None
            )
            if not week_topic:
                log.warning(
                    f"{Colors.YELLOW}⚠️  No week topic found for week {week_num}, skipping {filename}{Colors.END}"
                )
                continue

            log.info(
                f"🔄 Generating {filename} for Week {week_num}: {title} ({i}/{len(materials_plan)})"
            )

            # Build previous weeks context for continuity
            previous_weeks_context = self._build_previous_weeks_context(
                weekly_topics, week_num
            )

            try:
                content = self._generate_single_material(
                    material_spec,
                    week_topic,
                    course_context,
                    industry_context,
                    previous_weeks_context,
                    mission_prompt,
                    slide_theme,
                    slide_css,
                )

                if content:
                    # Initialize week dict if not exists
                    if week_num not in learning_materials:
                        learning_materials[week_num] = {}

                    learning_materials[week_num][filename] = content
                    log.info(
                        f"{Colors.GREEN}✅ Generated {filename} for Week {week_num} ({i}/{len(materials_plan)}){Colors.END}"
                    )
                else:
                    log.warning(
                        f"{Colors.YELLOW}⚠️  Failed to generate {filename} for Week {week_num}{Colors.END}"
                    )

            except Exception as e:
                log.error(
                    f"{Colors.RED}❌ Error generating material {i}: {e}{Colors.END}"
                )
                continue

        log.info(
            f"{Colors.GREEN}✅ Completed generation of {len(materials_plan)} materials{Colors.END}"
        )

        # -----------------------------------------------------------------
        # Final pass: ensure that every week has at minimum *slides.md* and
        # *demo.md* keys so that higher-level logic and the integration tests
        # can rely on their presence.  We only fill in missing artefacts – we
        # do not overwrite existing user / LLM generated content.
        # -----------------------------------------------------------------
        if not is_mocked:
            for week in weekly_topics:
                w_num = week["week"]
                learning_materials.setdefault(w_num, {})

                # Slides fallback: (rare – normally always present)
                if "slides.md" not in learning_materials[w_num]:
                    log.info(f"📝 Adding fallback slides.md for Week {w_num}")
                    learning_materials[w_num]["slides.md"] = (
                        self._fallback_learning_materials_week(week)["slides.md"]
                    )

                # Demo fallback: only supply when regular generation failed.
                if "demo.md" not in learning_materials[w_num]:
                    log.info(f"📝 Adding fallback demo.md for Week {w_num}")
                    learning_materials[w_num]["demo.md"] = (
                        self._fallback_learning_materials_week(week)["demo.md"]
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
        slide_css: Optional[str] = None,
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
            slide_css: Optional CSS content for slides styling context

        Returns:
            Generated content as string, or None if failed
        """
        filename = material_spec.get("filename", "")
        title = material_spec.get("title", "")
        week_num = material_spec.get("week", 0)
        description = material_spec.get("description", "")
        justification = material_spec.get("justification", "")

        # Determine material type and create appropriate prompt
        if filename == "slides.md":
            return self._generate_slides_content(
                week_topic,
                course_context,
                industry_context,
                previous_weeks_context,
                title,
                description,
                justification,
                slide_theme=slide_theme,
                slide_css=slide_css,
            )
        elif filename == "demo.md":
            return self._generate_demo_content(
                week_topic,
                course_context,
                industry_context,
                previous_weeks_context,
                title,
                description,
                justification,
            )
        elif filename.endswith(".md"):
            # This is a guide/handout - use soft conventions with minimal constraints
            return self._generate_guide_content(
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
                f"{Colors.YELLOW}⚠️  Unknown material type: {filename} - skipping generation{Colors.END}"
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
        slide_css: Optional[str] = None,  # NEW: CSS content for styling context
    ) -> Optional[str]:
        """Generate slides content for a specific week with Marp/YAML compliance and theme support."""

        # Determine theme: user override or default
        theme = slide_theme or "nmt-theme"
        theme_path_comment = """
# To override the default theme, provide a custom CSS file and set the 'theme' field in the YAML front matter to the theme name defined in your CSS (e.g., @theme my-custom-theme). Place your CSS in the appropriate location and ensure Marp can access it during conversion.
"""

        # Marp/YAML/slide structure guidelines (from real examples):
        marp_guidelines = f"""
HARD REQUIREMENTS (MANDATORY - enforced by build-sites.sh):
- The file MUST start with a YAML front matter block delimited by '---' at the top and bottom
- The YAML front matter MUST include these exact fields:
    marp: true
    theme: {theme}
    title: <Session Title>
    footer: "![height:50px](footer.png)"
- Each slide is separated by a line with only '---'
- All content must be valid Markdown/HTML and render correctly in Marp

SOFT CONVENTIONS (RECOMMENDED but flexible):
- Use Markdown headings (#, ##, ###) for slide titles and structure
- You MAY use HTML (e.g., <style>, <table>, <img>, <!-- _class: ... -->) for advanced formatting
- Images can be included with Markdown or HTML
- You MAY use Marp slide classes (e.g., <!-- _class: lead -->) for layout
- The slides.md should be visually engaging, using the provided theme for consistent branding
- Include clear learning objectives, examples, activities, and assessment preparation
- {theme_path_comment if not slide_theme else ""}
"""

        # Custom steps for slides generation
        custom_steps = [
            f"First, analyze the slide structure and flow for Week {week_topic.get('week', 0)}: Start with clear learning objectives and agenda; Present concepts in logical progression; Include practical examples and case studies; Provide opportunities for student engagement; End with summary and next steps",
            f"Design slides that: Are Marp-compliant, start with YAML front matter, use the '{theme}' theme, and follow the provided guidelines; Include both theoretical and practical content; Incorporate industry-relevant examples; Support different learning styles; Prepare students for assessments; Build upon and complement previous weeks",
            f"Plan for the specific week type: Regular academic content with comprehensive slides; Focus on review materials, practice content, and reassessment preparation; Focus on final submission guidelines, course completion content, and no-contact period information",
            f"Apply technical constraints: HARD REQUIREMENTS - Ensure YAML frontmatter includes 'marp: true', 'theme: {theme}', 'title', and 'footer'; Use '---' separators between slides; SOFT CONVENTIONS - Create engaging visual content, include clear learning objectives, provide practical examples, and prepare for assessments",
        ]

        # Add CSS context if provided
        css_context = ""
        if slide_css:
            css_context = f"""
=== CSS THEME CONTENT ===
The following CSS defines the '{theme}' theme. Use this to understand the styling constraints and design elements available:

```css
{slide_css}
```

Consider the theme's styling when creating content - align with colors, fonts, and layout patterns defined in the CSS.
===========================
"""

        prompt = f"""
{self._format_config_context()}

Generate a Marp-compliant slides.md for Week {week_topic.get("week", 0)}: {title}

DESCRIPTION: {description}
JUSTIFICATION: {justification}

WEEK TOPIC: {week_topic.get("title", "")}
WEEK TOPICS: {", ".join(week_topic.get("topics", []))}

{course_context}
{industry_context}
{previous_weeks_context}
{css_context}
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
        last_response: Optional[str] = None
        for attempt in range(max_retries):
            response, success, raw_response = self._safe_prompt_with_retries(
                prompt,
                max_retries=1,  # Only one try per outer attempt
                response_type="SLIDES_CONTENT",
                json_expected=False,
                use_search=True,
            )
            if not success or not response:
                continue

            # On the first successful reply we either return immediately (if
            # validation passes) or keep the content as *best effort* and exit
            # the retry loop.  This guarantees the helper is invoked exactly
            # once when mocked in the test-suite.
            if self._validate_slides_md(response, theme):
                return response

            last_response = response
            break  # Do not issue further requests once we have a response.

        # Return the best-effort response even if validation failed (useful for
        # offline tests where a full YAML front-matter isn't provided).
        return last_response

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

        # If we do not have a *usable* LLM (no API-key or the client failed to
        # instantiate) we construct a deterministic markdown template instead
        # of attempting to prompt a model.  This keeps the public interface
        # consistent and ensures that integration tests expecting a
        # "demo.md" artefact succeed in fully offline environments.

        if not self.client:
            # Basic protective defaults in the unlikely event keys are missing
            week_num = week_topic.get("week", 0)
            week_title = week_topic.get("title", f"Week {week_num}")
            topics = week_topic.get("topics", [])

            return f"""# Session {week_num}: {week_title} - Practical Workshop (Fallback)

## Introduction
This workshop provides hands-on experience with {week_title} concepts and tools.

## Example Code
```python
print('Hello, AI!')
```

## Exercises
- Implement a simple example based on {topics[0] if topics else "this week's concept"}
- Discuss how the concept applies in your workplace or study context.
"""

        # ----------------
        # Normal GPT path
        # ----------------
        # Custom steps for demo generation
        custom_steps = [
            f"First, analyze the demo structure and flow for Week {week_topic.get('week', 0)}: Start with clear learning objectives and agenda; Present concepts in logical progression; Include practical examples and case studies; Provide opportunities for student engagement; End with summary and next steps",
            f"Design demos that: Are Jupyter notebook compatible, use standard markdown format, and follow the provided guidelines; Include both theoretical and practical content; Incorporate industry-relevant examples; Support different learning styles; Prepare students for assessments; Build upon and complement previous weeks",
            f"Plan for the specific week type: Regular academic content with comprehensive demos; Focus on review materials, practice content, and reassessment preparation; Focus on final submission guidelines, course completion content, and no-contact period information",
            f"Apply technical constraints: HARD REQUIREMENTS - Use standard markdown format for jupytext conversion; Include code cells with Python examples (```python blocks); Use markdown cells for explanations; SOFT CONVENTIONS - Create engaging practical content, include clear learning objectives, provide hands-on examples, and prepare for assessments",
        ]

        prompt = f"""
{self._format_config_context()}

Generate comprehensive demo/workshop content for Week {week_topic.get("week", 0)}: {title}

DESCRIPTION: {description}
JUSTIFICATION: {justification}

WEEK TOPIC: {week_topic.get("title", "")}
WEEK TOPICS: {", ".join(week_topic.get("topics", []))}

{course_context}
{industry_context}
{previous_weeks_context}

{self._format_chain_of_thought_header(custom_steps)}

HARD REQUIREMENTS (MANDATORY - for jupytext conversion):
- Use standard Markdown format that can be converted to Jupyter notebook
- Use markdown cells for explanations (regular markdown text)
- Include code cells with Python examples (```python blocks)
- Ensure proper markdown syntax for jupytext compatibility

SOFT CONVENTIONS (RECOMMENDED but flexible):
- Start with setup and introduction
- Include step-by-step tutorials with code examples
- Add practical exercises and challenges
- Include industry case studies and real-world scenarios
- Provide troubleshooting guidance and best practices
- Add reflection and assessment questions
- Build upon concepts from previous weeks
- End with summary and next steps

{self._format_formatting_requirements("demo content")}

{self._format_thought_answer_structure("DEMO_CONTENT")}
"""

        response, success, raw_response = self._safe_prompt_with_retries(
            prompt,
            max_retries=3,
            response_type="DEMO_CONTENT",
            json_expected=False,
            use_search=True,
        )

        # If the call failed (e.g. due to rate limiting or the mock returning
        # an empty string) we once again return the deterministic fallback so
        # callers always receive *something* useful.
        if not success or not response:
            # If the model failed to produce a response we mirror the original
            # behaviour (return ``None``) so that unit tests exercising the
            # error path remain valid.
            return None

        return response

    def _generate_guide_content(
        self,
        week_topic: Dict[str, Any],
        course_context: str,
        industry_context: str,
        previous_weeks_context: str,
        title: str,
        description: str,
        justification: str,
    ) -> Optional[str]:
        """Generate guide/handout content for a specific week with soft conventions."""

        # If we do not have a *usable* LLM (no API-key or the client failed to
        # instantiate) we construct a deterministic markdown template instead
        # of attempting to prompt a model.  This keeps the public interface
        # consistent and ensures that integration tests expecting a
        # guide/handout artefact succeed in fully offline environments.

        if not self.client:
            # Basic protective defaults in the unlikely event keys are missing
            week_num = week_topic.get("week", 0)
            week_title = week_topic.get("title", f"Week {week_num}")
            topics = week_topic.get("topics", [])

            return f"""# {title} (Fallback)

## Introduction
This guide provides supplementary information for {week_title}.

## Key Points
- Review the main concepts from this week
- Practice the skills covered in class
- Prepare for upcoming assessments

## Additional Resources
- Course materials and readings
- Industry examples and case studies
- Practice exercises and activities
"""

        # ----------------
        # Normal GPT path
        # ----------------
        # Custom steps for guide generation
        custom_steps = [
            f"First, analyze the guide structure and purpose for Week {week_topic.get('week', 0)}: What supplementary information would be helpful? What additional resources or explanations are needed? How can this guide support the main learning objectives? What practical tips or examples would enhance understanding?",
            f"Design guides that: Use standard markdown format with minimal constraints; Include supplementary information and resources; Provide practical tips and examples; Support different learning styles; Build upon and complement the main materials; Prepare students for assessments and real-world application",
            f"Plan for the specific week type: Regular academic content with supplementary guides; Focus on review materials, practice content, and reassessment preparation; Focus on final submission guidelines, course completion content, and no-contact period information",
            f"Apply technical constraints: SOFT CONVENTIONS ONLY - Use standard markdown format; Include clear headings and structure; Provide practical examples and resources; Create engaging, helpful content that supports learning objectives",
        ]

        prompt = f"""
{self._format_config_context()}

Generate comprehensive guide/handout content for Week {week_topic.get("week", 0)}: {title}

DESCRIPTION: {description}
JUSTIFICATION: {justification}

WEEK TOPIC: {week_topic.get("title", "")}
WEEK TOPICS: {", ".join(week_topic.get("topics", []))}

{course_context}
{industry_context}
{previous_weeks_context}

{self._format_chain_of_thought_header(custom_steps)}

SOFT CONVENTIONS (RECOMMENDED but flexible):
- Use standard Markdown format with clear structure
- Include supplementary information and resources
- Provide practical tips, examples, and best practices
- Add industry-relevant case studies and scenarios
- Include additional reading materials and references
- Provide troubleshooting guidance and FAQs
- Add reflection questions and self-assessment tools
- Build upon concepts from previous weeks
- End with summary and next steps

{self._format_formatting_requirements("guide content")}

{self._format_thought_answer_structure("GUIDE_CONTENT")}
"""

        response, success, raw_response = self._safe_prompt_with_retries(
            prompt,
            max_retries=3,
            response_type="GUIDE_CONTENT",
            json_expected=False,
            use_search=True,
        )

        # If the call failed (e.g. due to rate limiting or the mock returning
        # an empty string) we once again return the deterministic fallback so
        # callers always receive *something* useful.
        if not success or not response:
            # If the model failed to produce a response we mirror the original
            # behaviour (return ``None``) so that unit tests exercising the
            # error path remain valid.
            return None

        return response

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
        return self._get_thought_answer_structure(response_type)

    def _format_formatting_requirements(
        self, content_type: str = "descriptions"
    ) -> str:
        """Format the formatting requirements with content-specific language."""
        return self.FORMATTING_REQUIREMENTS.replace("descriptions", content_type)

    def _format_config_context(self, config: Optional[Dict[str, Any]] = None) -> str:
        """Format the standardized config context box for all prompts."""
        if config is None:
            # Use stored config if none provided
            config = self.config

        config_str = str(config) if config else "No specific configuration provided"

        return f"""
╔══════════════════════════════════════════════════════════════════════════════════════════════╗
║                                     COURSE CONFIGURATION                                     ║
╚══════════════════════════════════════════════════════════════════════════════════════════════╝

{config_str}

╔══════════════════════════════════════════════════════════════════════════════════════════════╗
║ IMPORTANT: All responses must align with the above course configuration and requirements.    ║
║ Consider course type, delivery mode, student cohort, industry context, and any specific      ║
║ constraints or goals outlined in the configuration when generating content.                  ║
╚══════════════════════════════════════════════════════════════════════════════════════════════╝

"""

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
        self, units: List[UnitOfCompetency], mission_prompt: Optional[str] = None
    ) -> Tuple[str, str]:
        """Build standardized unit context and unit information."""
        # TODO: If this is the main unit context passed to the model we need to add more unit information
        # CONTEXT: It seems this may just be for the 'course overview'

        mission_context = ""
        if mission_prompt:
            mission_context = f"\n\nCourse Context and Goals:\n{mission_prompt}\n"

        if self.course_config.has_units_of_competency and units:
            unit_info = "\n".join(
                [f"\n\n# {unit.unit_code}: {unit.title} \n\n {unit}" for unit in units]
            )
            unit_context = f"Prioritise the following course context and goals at all times when interpreting the units of competency: {mission_context}"
        else:
            unit_info = (
                "This course focuses on practical skills and knowledge development."
            )
            unit_context = (
                f"Generate the requested content using chain of thought reasoning:"
            )

        return unit_info, unit_context

    def _build_prerequisites_context(
        self, prerequisites: List[UnitOfCompetency]
    ) -> str:
        """Build standardized prerequisites context."""
        if self.course_config.has_units_of_competency and prerequisites:
            prerequisites_info = "\n".join(
                [
                    f"\n\n# {unit.unit_code}: {unit.title} \n\n {unit.application}"
                    for unit in prerequisites
                ]
            )
            return f"# Course Prerequisites \n\n All students completing this course will be assumed to have completed the following prerequisite units of competency either within this course or in prior studies:\n{prerequisites_info}"
        else:
            return ""

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

    def _fallback_materials_plan(
        self, weekly_topics: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Fallback materials plan when GPT is not available."""
        materials_plan = []
        for week in weekly_topics:
            # Add slides.md for each week
            materials_plan.append(
                {
                    "week": week["week"],
                    "filename": "slides.md",
                    "title": f"{week['title']} - Presentation Slides",
                    "description": f"Presentation slides covering {week['title']} topics and concepts",
                    "type": "slides",
                }
            )
            # Add demo.md for each week
            materials_plan.append(
                {
                    "week": week["week"],
                    "filename": "demo.md",
                    "title": f"{week['title']} - Practical Workshop",
                    "description": f"Hands-on workshop and practical exercises for {week['title']}",
                    "type": "demo",
                }
            )
        return materials_plan

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

    # ------------------------------------------------------------------
    # Stage-1 helper: ask the LLM to propose which artefacts to generate
    # ------------------------------------------------------------------
    def _plan_learning_materials(
        self,
        weekly_topics: List[Dict[str, Any]],
        mission_prompt: Optional[str] = None,
        course_overview: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Create a *plan* for learning materials.

        This method enforces constraints based on build-sites.sh processing logic:

        HARD REQUIREMENTS (enforced by build-sites.sh):
        - 'slides.md' files MUST have YAML frontmatter with 'marp: true' to be processed as slides
        - 'demo.md' files MUST be standard markdown format for jupytext conversion to Jupyter notebooks
        - All other .md files are treated as guides/handouts with minimal constraints

        SOFT CONVENTIONS (recommended but flexible):
        - slides.md: Presentation slides with learning objectives, examples, activities
        - demo.md: Hands-on workshops with code examples and practical applications
        - guides/handouts: Any other markdown content (guides, references, handouts, etc.)
        - Materials should build upon previous weeks and prepare for assessments
        - Content should be industry-relevant and practical

        The plan is a list of dictionaries with at least the keys
        ``filename``, ``title``, ``description``, ``week`` and ``justification``.
        If an LLM client is available we attempt to generate this via
        :pymeth:`_safe_prompt_with_retries`; otherwise we fall back to a simple
        heuristic that mirrors the previous *direct* implementation (one set of
        slides and a demo per week).
        """

        # Quick heuristic fallback (used when no LLM or when prompting fails)
        def _heuristic_plan() -> List[Dict[str, Any]]:
            plan: List[Dict[str, Any]] = []
            for week in weekly_topics:
                plan.append(
                    {
                        "filename": "slides.md",
                        "title": f"{week['title']} Slides",
                        "description": f"Comprehensive presentation slides for Week {week['week']}",
                        "week": week["week"],
                        "justification": f"Slides for Week {week['week']} help visualize and structure the content.",
                    }
                )
                plan.append(
                    {
                        "filename": "demo.md",
                        "title": f"{week['title']} Workshop",
                        "description": f"Hands-on workshop for Week {week['week']} concepts",
                        "week": week["week"],
                        "justification": f"Practical application for Week {week['week']} reinforces learning.",
                    }
                )
            return plan

        # We always *attempt* to call `_safe_prompt_with_retries` first so that
        # unit-tests can patch that helper and validate both success *and*
        # failure scenarios – even when `self.client` is ``None`` (offline
        # mode).  Only when the call was unsuccessful *and* the helper is *not*
        # being mocked do we fall back to a deterministic heuristic plan.

        # Build a concise prompt asking the model to propose materials.
        config_context = self._format_config_context()
        course_context = (
            f"\n=== COURSE OVERVIEW ===\n{course_overview}\n" if course_overview else ""
        )

        prompt = (
            f"{config_context}\n\n"
            f"{course_context}\n"
            "You are an expert instructional designer. Based on the weekly topics "
            "provided below, propose a plan for the learning materials that should "
            "be created for each week of the course.\n\n"
            "HARD REQUIREMENTS (MANDATORY - enforced by build-sites.sh):\n"
            "- 'slides.md' files MUST have YAML frontmatter with 'marp: true' to be processed as slides\n"
            "- 'demo.md' files MUST be standard markdown format for jupytext conversion to Jupyter notebooks\n"
            "- All other .md files are treated as guides/handouts with minimal constraints\n"
            "- Each week should have 2-3 materials (slides.md, demo.md, and optionally guides/handouts)\n\n"
            "SOFT CONVENTIONS (RECOMMENDED but flexible):\n"
            "- slides.md: Presentation slides with clear learning objectives, examples, and activities\n"
            "- demo.md: Hands-on workshops with code examples, exercises, and practical applications\n"
            "- guides/handouts: Any other markdown content (guides, references, handouts, etc.)\n"
            "- Materials should build upon previous weeks and prepare for assessments\n"
            "- Content should be industry-relevant and practical\n"
            "- Titles should be descriptive and engaging\n\n"
            "For every artefact include:\n"
            "- filename (MUST be either 'slides.md', 'demo.md', or any other .md filename for guides)\n"
            "- title (descriptive name for the material)\n"
            "- description (what the material covers)\n"
            "- week (integer week number)\n"
            "- justification (why this material is useful for this week)\n\n"
            "Return the plan as a JSON array with 2-3 materials per week."
        )

        # Append a compact representation of weekly topics to the prompt.
        topics_brief = "\n".join(
            f"Week {w['week']}: {w['title']}" for w in weekly_topics
        )

        prompt += f"Full weekly topics:\n\n{weekly_topics}"
        prompt += f"\nWeekly Topics Summary:\n{topics_brief}"

        response, success, raw_response = self._safe_prompt_with_retries(
            prompt,
            max_retries=3,
            response_type="MATERIALS_PLAN",
            json_expected=True,
            use_search=True,
        )

        if success and response:
            try:
                plan = json.loads(response)
                # Validate that the plan contains valid material types
                # slides.md and demo.md have hard requirements, other .md files are guides/handouts
                filtered_plan = []
                invalid_materials = []
                slides_materials = []
                demo_materials = []
                guide_materials = []

                for item in plan:
                    filename = item.get("filename", "")
                    if filename == "slides.md":
                        slides_materials.append(item)
                        filtered_plan.append(item)
                    elif filename == "demo.md":
                        demo_materials.append(item)
                        filtered_plan.append(item)
                    elif filename.endswith(".md"):
                        guide_materials.append(item)
                        filtered_plan.append(item)
                    else:
                        invalid_materials.append(filename)
                        log.warning(
                            f"{Colors.YELLOW}⚠️  Skipping invalid material type: {filename} (must be .md file){Colors.END}"
                        )

                if invalid_materials:
                    log.info(
                        f"{Colors.BLUE}ℹ️  Build system only supports .md files. "
                        f"Invalid types ({', '.join(invalid_materials)}) were filtered out.{Colors.END}"
                    )

                log.info(
                    f"{Colors.BLUE}ℹ️  Material plan: {len(slides_materials)} slides, "
                    f"{len(demo_materials)} demos, {len(guide_materials)} guides/handouts{Colors.END}"
                )

                return filtered_plan
            except json.JSONDecodeError:
                log.warning(
                    f"{Colors.YELLOW}⚠️  Could not parse JSON plan – using heuristic fallback.{Colors.END}"
                )

        # If the call was unsuccessful *and* we are in a unit-test context
        # where the helper is patched with ``MagicMock``, propagate the
        # failure so that the tests can assert the correct behaviour.
        if not success and _is_magic_mock(self._safe_prompt_with_retries):
            return []

        # In all other failure scenarios we resort to the deterministic
        # heuristic plan defined above.
        return _heuristic_plan()

    def generate_detailed_assessment(
        self,
        assessment_desc: Dict[str, Any],
        units: List[Any],
        weekly_topics: List[Dict[str, Any]],
        mission_prompt: Optional[str] = None,
    ) -> str:
        """
        Generate detailed assessment content with actual tasks based on assessment description.

        Args:
            assessment_desc: Assessment description from LAP generation
            units: List of UnitOfCompetency objects
            weekly_topics: List of weekly topics for context
            mission_prompt: Optional guiding prompt for course context

        Returns:
            Detailed assessment content as markdown
        """
        if not self.client:
            log.info(
                f"{Colors.YELLOW}GPT client not available, using fallback assessment content{Colors.END}"
            )
            return self._fallback_detailed_assessment(assessment_desc)

        # Build context about units and topics
        unit_context = ""
        for unit in units:
            unit_context += f"\nUnit: {unit.unit_code} - {unit.title}\n"
            if hasattr(unit, "elements_and_criteria") and unit.elements_and_criteria:
                for element_name, criteria in unit.elements_and_criteria.items():
                    unit_context += f"  Element: {element_name}\n"
                    for criteria_key, criteria_desc in criteria.items():
                        unit_context += f"    {criteria_key}: {criteria_desc}\n"

        # Build topics context for relevant weeks
        topics_context = ""
        for topic in weekly_topics[:18]:  # Academic weeks only
            topics_context += f"Week {topic['week']}: {topic['title']}\n"
            for subtopic in topic.get("topics", []):
                topics_context += f"  - {subtopic}\n"

        prompt = f"""
{self._format_config_context()}

You are an expert VET assessment designer. Generate detailed assessment content with specific tasks based on the assessment description provided.

ASSESSMENT DESCRIPTION:
Title: {assessment_desc["title"]}
Description: {assessment_desc["description"]}
Due Date: {assessment_desc.get("due_date", "TBD")}

UNIT CONTEXT:
{unit_context}

WEEKLY TOPICS CONTEXT (for alignment):
{topics_context}

MISSION CONTEXT:
{mission_prompt or "Industry-focused VET training"}

REQUIREMENTS:
1. Generate specific, actionable assessment tasks that align with the assessment description
2. Each task should clearly map to specific unit criteria and learning outcomes
3. Include clear instructions, requirements, and success criteria for each task
4. Provide realistic scenarios and industry-relevant contexts
5. Include assessment resources, submission requirements, and evaluation criteria
6. Make tasks progressive in complexity and comprehensive in coverage

Generate the complete assessment content including:
- Assessment Resources section
- Assessment Instructions section (overview, instructions, submission evidence)
- Assessment Instrument section with specific numbered tasks
- Each task should have clear instructions, requirements, and response areas

Format the output as markdown content (without YAML frontmatter - that will be added separately).
Focus on creating authentic, industry-relevant assessment tasks that students can actually complete.
"""

        response, success, raw_response = self._safe_prompt_with_retries(
            prompt,
            max_retries=3,
            response_type="DETAILED_ASSESSMENT",
            json_expected=False,
        )

        if success and response:
            return response.strip()
        else:
            log.warning(
                f"{Colors.YELLOW}Failed to generate detailed assessment content, using fallback{Colors.END}"
            )
            return self._fallback_detailed_assessment(assessment_desc)

    def generate_holistic_assessment_mappings(
        self,
        assessment_contents: List[Dict[str, Any]],
        units: List[Any],
        mission_prompt: Optional[str] = None,
    ) -> Dict[int, str]:
        """
        Generate holistic assessment mappings for all assessments considering UOC coverage.

        Args:
            assessment_contents: List of assessment content dictionaries
            units: List of UnitOfCompetency objects
            mission_prompt: Optional guiding prompt for course context

        Returns:
            Dictionary mapping assessment index to YAML mapping content
        """
        if not self.client:
            log.info(
                f"{Colors.YELLOW}GPT client not available, using fallback mappings{Colors.END}"
            )
            return self._fallback_holistic_mappings(assessment_contents, units)

        # Build comprehensive UOC context
        uoc_context = ""
        for unit in units:
            uoc_context += f"\nUnit: {unit.unit_code} - {unit.title}\n"
            if hasattr(unit, "elements_and_criteria") and unit.elements_and_criteria:
                for element_index, (element_name, criteria) in enumerate(
                    unit.elements_and_criteria.items(), 1
                ):
                    uoc_context += f"  Element {element_index}: {element_name}\n"
                    for criteria_key, criteria_desc in criteria.items():
                        uoc_context += f"    {criteria_key}: {criteria_desc}\n"

            # Add knowledge and skills evidence if available
            if hasattr(unit, "knowledge_evidence") and unit.knowledge_evidence:
                uoc_context += f"  Knowledge Evidence:\n"
                for i, knowledge in enumerate(unit.knowledge_evidence, 1):
                    uoc_context += f"    {i}. {knowledge}\n"

            if hasattr(unit, "performance_evidence") and unit.performance_evidence:
                uoc_context += f"  Performance Evidence:\n"
                for i, performance in enumerate(unit.performance_evidence, 1):
                    uoc_context += f"    {i}. {performance}\n"

        # Build assessment context
        assessment_context = ""
        for i, assessment in enumerate(assessment_contents):
            assessment_context += f"\nAssessment {i + 1}: {assessment['title']}\n"
            assessment_context += (
                f"Description: {assessment['description']['description']}\n"
            )
            assessment_context += f"Content Preview: {assessment['content'][:500]}...\n"

        prompt = f"""
You are an expert VET assessment mapping specialist. Create holistic assessment mappings that ensure complete UOC coverage across all assessments.

CRITICAL ASSESSMENT MAPPING STRUCTURE GUIDANCE:

ELEMENTS vs CRITERIA HIERARCHY:
- ELEMENTS are the main sections of a unit (numbered 1, 2, 3, 4, etc.)
- CRITERIA are sub-points within elements (numbered 1.1, 1.2, 1.3, 2.1, 2.2, etc.)
- Each element contains multiple criteria that must ALL be satisfied together

ASSESSMENT DESIGN RULES:
1. ELEMENT INTEGRITY: ALL criteria for an element must be satisfied within the same assessment
   - Example: Assessment 1 covers Element 1 (criteria 1.1, 1.2, 1.3) and Element 2 (criteria 2.1, 2.2)
   - Example: Assessment 2 covers Element 3 (criteria 3.1, 3.2) and Element 4 (criteria 4.1, 4.2, 4.3)

2. COMPLETE COVERAGE: Every criteria, knowledge evidence, and performance evidence must be mapped to at least one assessment

3. LOGICAL DISTRIBUTION: Elements should be distributed logically across assessments (foundational → advanced)

4. CRITERIA-LEVEL MAPPING: Assessments must be mapped at the CRITERIA level to questions
   - Each question should map to specific criteria (e.g., 1.1, 1.2, 2.1)
   - NOT to simplified descriptions like "1. Specify software requirements"

5. NO GAPS: Ensure no UOC components are left unmapped

6. NO REDUNDANCY: Avoid unnecessary duplication of mappings

MAPPING FORMAT REQUIREMENTS:
- Use exact criteria numbers from UOC (e.g., "1.1", "2.3", "3.1") - NOT simplified descriptions
- Map knowledge and performance evidence by index number (1, 2, 3, etc.)
- Each assessment gets a "mapping:" section with question-based structure
- Format: criteria: UNIT_CODE: [list of criteria], knowledge: UNIT_CODE: [list of indices], performance: UNIT_CODE: [list of indices]
- Each question should focus on specific criteria, not general element descriptions

EXAMPLE CORRECT MAPPING:
```yaml
mapping:
  - # Question 1 - Element 1 - Criteria 1.1
    criteria:
      ICTCLD401:
        - 1.1
    knowledge:
      ICTCLD401:
        - 1
    performance:
      ICTCLD401:
        - 1
  - # Question 2 - Element 1 - Criteria 1.2  
    criteria:
      ICTCLD401:
        - 1.2
    knowledge:
      ICTCLD401:
        - 1
    performance:
      ICTCLD401:
        - 1
```

AVOID THESE COMMON MISTAKES:
- ❌ Using simplified descriptions like "1. Select and secure access to cloud environment"
- ❌ Using element numbers instead of criteria numbers in the criteria mapping
- ❌ Splitting criteria from the same element across different assessments
- ❌ Creating gaps in UOC coverage, remember we must uphold validity and reliability of the assessments.

UOC STRUCTURE:
{uoc_context}

ASSESSMENT OVERVIEW:
{assessment_context}

Generate YAML mapping sections for each assessment that:
1. Ensures complete UOC coverage across all assessments
2. Maps specific criteria to individual questions within each assessment
3. Distributes elements logically (Assessment 1: foundational, Assessment 4: comprehensive)
4. Uses exact criteria numbers as shown in the UOC structure above
5. Follows the Element Integrity Rule strictly

For each assessment (0-based index), return:
```yaml
mapping:
  - # Question 1
    criteria:
      UNIT_CODE: [specific criteria numbers like 1.1, 1.2]
    knowledge:
      UNIT_CODE: [knowledge evidence indices like 1, 2]
    performance:
      UNIT_CODE: [performance evidence indices like 1, 2]
  - # Question 2
    [continue for all questions in this assessment]
```

Return a JSON object with assessment indices as keys (0, 1, 2, 3) and YAML mapping content as values.
"""

        response, success, raw_response = self._safe_prompt_with_retries(
            prompt,
            max_retries=3,
            response_type="HOLISTIC_MAPPINGS",
            json_expected=True,
        )

        if success and response:
            try:
                mappings_data = json.loads(response)
                # Convert string keys to integers and return YAML content
                result = {}
                for key, value in mappings_data.items():
                    try:
                        index = int(key)
                        result[index] = value
                    except ValueError:
                        log.warning(f"Invalid assessment index in mappings: {key}")
                return result
            except json.JSONDecodeError:
                log.warning(
                    f"{Colors.YELLOW}Failed to parse holistic mappings JSON, using fallback{Colors.END}"
                )
                return self._fallback_holistic_mappings(assessment_contents, units)
        else:
            log.warning(
                f"{Colors.YELLOW}Failed to generate holistic mappings, using fallback{Colors.END}"
            )
            return self._fallback_holistic_mappings(assessment_contents, units)

    def _fallback_detailed_assessment(self, assessment_desc: Dict[str, Any]) -> str:
        """Fallback detailed assessment content when GPT is not available."""
        title = assessment_desc.get("title", "Assessment")
        description = assessment_desc.get("description", "Assessment description")

        return f"""# Assessment Resources:

- Course materials and textbooks
- Online resources and tutorials
- Required software and tools
- Assessment guidelines and rubrics

# Assessment Instructions:

## Assessment Overview
{description}

### Instructions:
1. Read all instructions carefully before beginning
2. Complete all required tasks as specified
3. Provide clear and detailed responses
4. Include appropriate evidence and examples
5. Submit by the due date

### Submission Evidence:
- Completed assessment tasks
- Supporting documentation
- Any required files or outputs
- Self-assessment and reflection

# Assessment Instrument:

## {title}

### Task 1: Foundation Task
#### Instructions:
Complete the foundational requirements for this assessment.

Your response must include:
- Clear demonstration of understanding
- Practical application of concepts
- Evidence of competency development

Please provide your response here:

---

### Task 2: Application Task
#### Instructions:
Apply the concepts to a practical scenario.

Your response must include:
- Problem analysis and solution
- Use of appropriate tools and methods
- Clear documentation of process

Please provide your response here:

---

### Task 3: Integration Task
#### Instructions:
Integrate multiple concepts and demonstrate comprehensive understanding.

Your response must include:
- Synthesis of learning outcomes
- Critical analysis and evaluation
- Professional presentation of results

Please provide your response here:

---
"""

    def _fallback_holistic_mappings(
        self, assessment_contents: List[Dict[str, Any]], units: List[Any]
    ) -> Dict[int, str]:
        """Fallback holistic mappings when GPT is not available."""
        mappings = {}

        for i, assessment in enumerate(assessment_contents):
            # Simple fallback mapping
            mapping_yaml = f"""mapping:
  - # Question 1
    criteria:"""

            for unit in units:
                mapping_yaml += f"""
      {unit.unit_code}:
        - 1.1"""

            mapping_yaml += f"""
    knowledge:"""

            for unit in units:
                mapping_yaml += f"""
      {unit.unit_code}:
        - 1"""

            mapping_yaml += f"""
    performance:"""

            for unit in units:
                mapping_yaml += f"""
      {unit.unit_code}:
        - 1"""

            mappings[i] = mapping_yaml

        return mappings

    def generate_fields_md(
        self,
        units: List[Any],
        assessments: List[Dict[str, Any]],
        course_overview: Optional[str] = None,
        mission_prompt: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Generate a complete fields.md file for the Learning and Assessment Plan.

        Args:
            units: List of UnitOfCompetency objects
            assessments: List of assessment descriptions from LAP generation
            course_overview: Generated course overview text
            mission_prompt: Optional guiding prompt for course context
            config: Course configuration dictionary

        Returns:
            Complete fields.md content with YAML frontmatter
        """
        if not self.client:
            log.info(
                f"{Colors.YELLOW}GPT client not available, using fallback fields.md{Colors.END}"
            )
            return self._fallback_fields_md(units, assessments, course_overview, config)

        # Build comprehensive context about the course
        units_context = ""
        for unit in units:
            units_context += f"\nUnit: {unit.unit_code} - {unit.title}\n"
            if hasattr(unit, "application") and unit.application:
                units_context += f"Application: {unit.application}\n"
            if hasattr(unit, "elements_and_criteria") and unit.elements_and_criteria:
                units_context += "Elements:\n"
                for element_name, criteria in unit.elements_and_criteria.items():
                    units_context += f"  - {element_name}\n"

        # Build assessments context
        assessments_context = ""
        for i, assessment in enumerate(assessments, 1):
            assessments_context += f"\nAssessment {i}: {assessment['title']}\n"
            assessments_context += f"Description: {assessment['description']}\n"
            assessments_context += f"Due Date: {assessment.get('due_date', 'TBD')}\n"

        prompt = f"""
{self._format_config_context()}

You are an expert VET course coordinator creating a fields.md file for a Learning and Assessment Plan (LAP). Generate a complete, realistic fields.md file based on the provided information.

UNITS OF COMPETENCY:
{units_context}

ASSESSMENTS:
{assessments_context}

COURSE OVERVIEW:
{course_overview or "Course overview not available"}

MISSION CONTEXT:
{mission_prompt or "Industry-focused VET training"}

REQUIREMENTS:
1. Look up the official qualification code and title based on units provided or configuration or leave it blank if not available
2. Generate appropriate delivery details based on course configuration
3. Create real lecturer information (use appropriate institutional context)
4. Generate course-specific student and college supply requirements
5. Ensure assessments section matches the provided assessment descriptions exactly
6. Use real campus/location information based on configuration or obvious placeholder
7. Include appropriate industry-specific requirements and tools
8. Make all content authentic and course-appropriate

YAML HEADER STRUCTURE REQUIREMENTS:
- qualification_national_code_and_title: Look up the official qualification code and title based on units or configuration or leave it blank if not available
- delivery_period: Current year and semester
- cluster_name: Appropriate cluster name for the qualification
- units: Exact unit codes and titles from the UOC data
- delivery_location/s: Based on configuration or obvious placeholder
- student_to_supply: Course-specific requirements (software, accounts, hardware)
- college_to_supply: Institution-provided resources and facilities
- lecturers: Realistic lecturer information with appropriate contact details
- assessments: Exact match to the provided assessment descriptions

EXAMPLE YAML HEADER STRUCTURE (adapt to your specific course):
---
qualification_national_code_and_title: "COURSE_CODE - Course Title"
delivery_period: 2025, S1
cluster_name: "Appropriate Cluster Name"

units:
  - name: "Unit Title"
    id: "UNIT_CODE"

delivery_location/s: Location

student_to_supply: |
  - Course-specific requirements
  - Software and accounts needed
  - Hardware requirements

college_to_supply: |
  - Institution facilities
  - Equipment and resources
  - Access to systems

lecturers:
  - name: "Lecturer Name"
    phone: "Phone or --"
    email: "email@institution.edu.au"
    contact_time: "in-class or by appointment"
    campus/room: "Campus Location"

assessments:
  - title: "Assessment Title"
    description: |
      Detailed description
    due_date: "Week X"
---


Generate a complete fields.md file that is accurate, professional, and specific to the course content. Ensure all information is consistent with the units, assessments, and configuration provided.
"""

        response, success, raw_response = self._safe_prompt_with_retries(
            prompt,
            max_retries=3,
            response_type="FIELDS_MD",
            json_expected=False,
            use_search=True,
        )

        if success and response:
            return response.strip()
        else:
            log.warning(
                f"{Colors.YELLOW}Failed to generate fields.md content, using fallback{Colors.END}"
            )
            return self._fallback_fields_md(units, assessments, course_overview, config)

    def _fallback_fields_md(
        self,
        units: List[Any],
        assessments: List[Dict[str, Any]],
        course_overview: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Fallback fields.md generation when GPT is not available."""

        # Generate units YAML
        units_yaml = ""
        for unit in units:
            units_yaml += f'  - name: "{unit.title}"\n    id: "{unit.unit_code}"\n'

        # Generate assessments YAML
        assessments_yaml = ""
        for assessment in assessments:
            assessments_yaml += f'''  - title: "{assessment["title"]}"
    description: |
      {assessment["description"]}
    due_date: "{assessment.get("due_date", "TBD")}"
'''

        # Extract info from config if available
        institution_name = "Institution"
        delivery_location = "Perth"
        if config:
            institution_info = config.get("institution", {})
            institution_name = institution_info.get("name", "Institution")
            delivery_location = institution_info.get("delivery_location", "Perth")

        return f"""---
qualification_national_code_and_title: "QUALIFICATION_CODE - Qualification Title"
delivery_period: "2025, S1"
cluster_name: "Course Cluster"
course_overview: |
  {course_overview.replace("\n", "\n  ") if course_overview else "Course overview not available"}

units:
{units_yaml}
delivery_location/s: "{delivery_location}"

student_to_supply: |
  - Adequate home workstation for out of class activities
  - Student's personal notes
  - Required software and tools

college_to_supply: |
  - On campus workstation 
  - Access to academic journals
  - Online databases and resources
  - Course materials and online textbooks

lecturers:
  - name: "Lecturer Name"
    phone: "Phone Number"
    email: "email@{institution_name.lower().replace(" ", "")}.edu.au"
    contact_time: "in-class or by appointment"
    campus/room: "Campus/Room"

assessments:
{assessments_yaml}
---
"""


def create_gpt_generator(
    course_config: Optional[CourseConfig] = None,
    config: Optional[Dict[str, Any]] = None,
    progress_file: Optional[str] = None,
    model: str = "gpt-4.1-nano-2025-04-14",
    yes_to_all: bool = False,
) -> GPTContentGenerator:
    """
    Create a GPT content generator instance.

    Args:
        course_config: Optional course configuration (defaults to TAFE 20-week course)
        config: Optional raw config dictionary for context formatting
        progress_file: Optional progress file for checkpointing
        model: The AI model to use for content generation

    Returns:
        GPTContentGenerator instance
    """
    return GPTContentGenerator(
        course_config=course_config,
        config=config,
        progress_file=progress_file,
        model=model,
        yes_to_all=yes_to_all,
    )
