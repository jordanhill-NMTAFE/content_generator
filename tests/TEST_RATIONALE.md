# Test Suite Rationale and Goals

This document provides a clear rationale for each test in the `tests/` folder, explaining why we have written each test and what the overall goals are. This documentation is designed to be high-level enough to survive refactoring or implementation changes while providing clear guidance for maintaining and extending the test suite.

## Test Suite Overview

Our test suite is organized into two main categories:

1. **Unit Tests** (`tests/unit/`) - Test individual functions and methods in isolation
2. **Integration Tests** (`tests/integration/`) - Test how components work together and end-to-end workflows

## Unit Tests Rationale

### `test_gpt_helper.py` - Core GPT Functionality

**Overall Goal**: Ensure the GPT content generation system works correctly at the function level, with proper error handling and fallback mechanisms.

#### ResponseBox Tests
- **`test_wrap_content`**: Ensures content can be properly wrapped in response boxes for structured communication with GPT
- **`test_extract_content`**: Verifies that content can be reliably extracted from response boxes
- **`test_extract_from_mixed_content`**: Tests extraction when response boxes are embedded in larger text
- **`test_extract_missing_box`**: Ensures graceful handling when expected response boxes are not found

#### CourseConfig Tests
- **`test_tafe_default_config`**: Validates that TAFE courses have the correct default configuration (20 weeks, 18 academic + 2 reassessment)
- **`test_commercial_config`**: Ensures commercial courses have appropriate settings (no reassessment weeks, not accredited)
- **`test_custom_config`**: Verifies that custom configurations can be properly set and validated
- **`test_get_week_ranges`**: Tests that week ranges are calculated correctly for different course types
- **`test_get_learning_phases`**: Ensures learning phases are properly distributed across the course timeline

#### GPTContentGenerator Unit Tests
- **`test_initialization`**: Verifies that the generator initializes with correct default settings
- **`test_initialization_with_custom_config`**: Tests that custom configurations are properly applied
- **`test_fallback_course_overview`**: Ensures fallback content is generated when GPT is unavailable
- **`test_fallback_weekly_topics`**: Tests that weekly topics can be generated without GPT
- **`test_fallback_assessment_descriptions`**: Verifies assessment descriptions are created in fallback mode
- **`test_build_course_context`**: Tests that course context is properly constructed for GPT prompts
- **`test_build_course_structure_context`**: Ensures course structure information is correctly formatted
- **`test_build_learning_phases_context`**: Tests learning phases context generation
- **`test_build_industry_context_*`**: Verifies industry context handling for different input types
- **`test_build_unit_context`**: Tests unit of competency context building
- **`test_sanitize_activity_text`**: Ensures activity text is properly cleaned for GPT consumption
- **`test_format_chain_of_thought_header`**: Tests chain-of-thought prompt formatting
- **`test_format_thought_answer_structure`**: Verifies answer structure formatting
- **`test_format_formatting_requirements`**: Tests formatting requirements generation
- **`test_safe_prompt_with_retries_*`**: Ensures robust error handling and retry logic for GPT calls

#### CourseContextBuilder Tests
- **`test_build_full_context`**: Tests complete context building for GPT prompts
- **`test_build_full_context_with_mission`**: Verifies mission integration in context building

#### CreateGPTGenerator Tests
- **`test_create_default_generator`**: Ensures default generator creation works correctly
- **`test_create_generator_with_custom_config`**: Tests custom configuration application
- **`test_create_generator_with_progress_file`**: Verifies progress tracking integration

### `test_cli_parser.py` - Command Line Interface

**Overall Goal**: Ensure the CLI interface is robust, user-friendly, and handles all input scenarios correctly.

#### Parser Help Tests
- **`test_parser_help`**: Ensures main help is displayed correctly
- **`test_init_command_help`**: Tests init command help documentation
- **`test_push_command_help`**: Verifies push command help
- **`test_config_command_help`**: Tests config command help
- **`test_convert_command_help`**: Tests convert command help

#### Argument Parsing Tests
- **`test_init_command_required_args`**: Ensures required arguments are properly parsed
- **`test_init_command_with_uoc_codes`**: Tests unit of competency code parsing
- **`test_init_command_with_mission`**: Verifies mission prompt handling
- **`test_init_command_with_no_llm`**: Tests no-LLM flag functionality
- **`test_init_command_course_type_options`**: Validates all course type options
- **`test_init_command_weeks_options`**: Tests week configuration options
- **`test_init_command_delivery_options`**: Verifies delivery-related options
- **`test_init_command_config_file`**: Tests config file option
- **`test_push_command_with_target`**: Tests push command with target directory
- **`test_push_command_without_target`**: Tests push command without target
- **`test_config_command_create`**: Tests config creation functionality
- **`test_config_command_template_options`**: Validates template options
- **`test_config_command_output_dir`**: Tests output directory specification
- **`test_convert_command_args`**: Tests convert command argument parsing
- **`test_convert_command_pattern`**: Tests file pattern specification for conversion
- **`test_convert_command_reverse`**: Tests reverse conversion flag

#### Validation Tests
- **`test_init_command_missing_required_args`**: Ensures proper error handling for missing arguments
- **`test_init_command_invalid_course_type`**: Tests invalid course type rejection
- **`test_init_command_invalid_delivery_mode`**: Verifies invalid delivery mode handling
- **`test_config_command_invalid_template`**: Tests invalid template rejection
- **`test_parser_no_command`**: Ensures proper handling when no command is provided
- **`test_parser_unknown_command`**: Tests unknown command handling

#### Short Options Tests
- **`test_init_command_short_options`**: Verifies short option aliases work correctly
- **`test_config_command_short_options`**: Tests config command short options

#### Default Values Tests
- **`test_init_defaults`**: Ensures default values are applied correctly
- **`test_init_boolean_flags`**: Tests boolean flag handling
- **`test_init_multiple_uoc_codes`**: Verifies multiple UOC code handling
- **`test_init_single_uoc_code`**: Tests single UOC code handling

#### Input Validation Tests
- **`test_numeric_arguments_validation`**: Ensures numeric arguments are properly validated
- **`test_delivery_mode_choices`**: Tests delivery mode choice validation
- **`test_course_type_choices`**: Verifies course type choice validation
- **`test_template_choices`**: Tests template choice validation

### `test_progress_manager.py` - Progress Tracking

**Overall Goal**: Ensure progress tracking is reliable, thread-safe, and handles edge cases properly.

#### Basic Functionality Tests
- **`test_initialization_empty_file`**: Tests initialization with empty progress file
- **`test_initialization_existing_file`**: Verifies loading from existing progress file
- **`test_initialization_corrupted_file`**: Tests recovery from corrupted progress files
- **`test_get_set_operations`**: Ensures basic get/set operations work correctly
- **`test_mark_done_and_status_checks`**: Tests progress marking and status checking
- **`test_save_and_load_persistence`**: Verifies data persistence across sessions

#### Concurrency Tests
- **`test_atomic_write_operations`**: Ensures atomic file operations
- **`test_thread_safety`**: Tests thread safety for concurrent access
- **`test_concurrent_file_access`**: Verifies proper handling of concurrent file access
- **`test_concurrent_access_with_mocks`**: Tests concurrency with mocked file system

#### Edge Cases Tests
- **`test_reset_functionality`**: Tests progress reset capability
- **`test_invalid_progress_file_path`**: Ensures graceful handling of invalid paths
- **`test_large_data_handling`**: Tests handling of large progress data
- **`test_concurrent_file_modification`**: Verifies behavior when files are modified externally
- **`test_memory_efficiency`**: Tests memory usage with large datasets
- **`test_progress_file_corruption_recovery`**: Tests recovery from file corruption
- **`test_empty_progress_file`**: Verifies handling of empty progress files

### `test_course_config.py` - Course Configuration

**Overall Goal**: Ensure course configuration is flexible, validated, and supports all required course types.

#### Configuration Tests
- **`test_tafe_default_config`**: Validates TAFE course defaults
- **`test_commercial_config`**: Tests commercial course configuration
- **`test_custom_config`**: Verifies custom configuration support
- **`test_get_week_ranges`**: Tests week range calculations
- **`test_get_learning_phases`**: Verifies learning phase distribution

### `test_response_box.py` - Response Box Utilities

**Overall Goal**: Ensure response box utilities work reliably for structured communication.

#### Response Box Tests
- **`test_wrap_content`**: Tests content wrapping functionality
- **`test_extract_content`**: Verifies content extraction
- **`test_extract_from_mixed_content`**: Tests extraction from complex content
- **`test_extract_missing_box`**: Ensures graceful handling of missing boxes

### `test_context_awareness.py` - Context Building

**Overall Goal**: Ensure context building creates comprehensive, well-structured prompts for GPT.

#### Context Building Tests
- **`test_build_course_context`**: Tests course context construction
- **`test_build_course_structure_context`**: Verifies course structure context
- **`test_build_learning_phases_context`**: Tests learning phases context
- **`test_build_industry_context_*`**: Verifies industry context handling
- **`test_build_unit_context`**: Tests unit context building

### `test_learning_materials.py` - Learning Materials Generation

**Overall Goal**: Ensure learning materials generation produces high-quality, structured content.

#### Learning Materials Tests
- **`test_generate_learning_materials`**: Tests complete learning materials generation
- **`test_generate_learning_materials_fallback`**: Verifies fallback content generation

## Integration Tests Rationale

### `test_cli_integration.py` - CLI Integration

**Overall Goal**: Ensure the CLI works correctly as a complete system, handling real-world usage scenarios.

#### CLI Function Tests
- **`test_parser_help`**: Tests complete help system
- **`test_init_function_call`**: Verifies init function integration
- **`test_generate_function_calls`**: Tests generation function integration
- **`test_create_config_function`**: Verifies config creation integration
- **`test_convert_function_call`**: Tests convert function integration

#### CLI Workflow Tests
- **`test_full_init_workflow`**: Tests complete init workflow
- **`test_full_config_workflow`**: Verifies complete config workflow
- **`test_init_command_multiline_mission`**: Tests multiline mission input
- **`test_init_command_short_options`**: Verifies short option workflows
- **`test_config_command_short_options`**: Tests config short option workflows

### `test_learning_materials_generation.py` - Learning Materials Integration

**Overall Goal**: Ensure the two-stage learning materials generation system works correctly end-to-end.

#### Materials Planning Tests
- **`test_plan_learning_materials_structure`**: Tests materials planning structure
- **`test_plan_learning_materials_failure`**: Verifies failure handling in planning

#### Materials Generation Tests
- **`test_generate_individual_materials_structure`**: Tests individual material generation
- **`test_generate_individual_materials_with_failures`**: Verifies failure handling in generation
- **`test_generate_single_material_slides`**: Tests slides content generation
- **`test_generate_single_material_unknown_type`**: Verifies unknown material type handling

#### Content Generation Tests
- **`test_generate_slides_content`**: Tests slides content creation
- **`test_generate_slides_content_failure`**: Verifies slides generation failure handling
- **`test_generate_demo_content`**: Tests demo content creation
- **`test_generate_demo_content_failure`**: Verifies demo generation failure handling

#### Full Flow Tests
- **`test_generate_learning_materials_full_flow`**: Tests complete materials generation workflow
- **`test_generate_learning_materials_planning_failure`**: Verifies planning failure handling
- **`test_generate_learning_materials_generation_failure`**: Tests generation failure handling

#### Context Integration Tests
- **`test_build_course_structure_context`**: Tests course structure context integration
- **`test_build_learning_phases_context`**: Verifies learning phases context integration
- **`test_build_course_context_with_learning_phases`**: Tests combined context building

#### Progress Integration Tests
- **`test_progress_tracking_integration`**: Tests progress tracking integration
- **`test_no_gpt_client_fallback`**: Verifies fallback behavior without GPT

### `test_checkpointing_system.py` - Checkpointing Integration

**Overall Goal**: Ensure the checkpointing system provides reliable progress tracking and recovery across complex workflows.

#### Progress Manager Integration Tests
- **`test_generator_with_progress_manager`**: Tests generator with progress tracking
- **`test_generator_without_progress_manager`**: Verifies generator without progress tracking
- **`test_checkpointing_integration_with_mock`**: Tests checkpointing with mocked GPT
- **`test_resume_from_checkpoint_with_mock`**: Verifies checkpoint resumption
- **`test_partial_progress_resume`**: Tests partial progress recovery

#### Generation Method Tests
- **`test_all_generation_methods_with_checkpointing`**: Tests all generation methods with checkpointing
- **`test_checkpointing_with_different_course_types`**: Verifies checkpointing across course types

#### Edge Case Tests
- **`test_progress_file_cleanup`**: Tests progress file cleanup
- **`test_checkpointing_with_api_failures`**: Verifies API failure handling

### `test_checkpointing_fast.py` - Fast Checkpointing Tests

**Overall Goal**: Provide quick validation of checkpointing functionality for development.

#### Fast Tests
- **`test_basic_checkpointing`**: Quick test of basic checkpointing
- **`test_resume_functionality`**: Fast test of resume functionality
- **`test_concurrent_access`**: Quick concurrency test

### `test_cli_simple.py` - Simple CLI Tests

**Overall Goal**: Provide quick validation of CLI functionality for development.

#### Simple CLI Tests
- **`test_basic_cli_functionality`**: Quick test of basic CLI
- **`test_cli_error_handling`**: Fast test of error handling
- **`test_cli_help_system`**: Quick test of help system

### `test_cli_workflows.py` - CLI Workflow Tests

**Overall Goal**: Ensure CLI workflows handle real-world usage patterns correctly.

#### Workflow Tests
- **`test_init_workflow`**: Tests complete init workflow
- **`test_push_workflow`**: Tests complete push workflow
- **`test_config_workflow`**: Tests complete config workflow
- **`test_convert_workflow`**: Tests complete convert workflow
- **`test_error_workflows`**: Tests error handling workflows

### `test_concurrent_access.py` - Concurrency Tests

**Overall Goal**: Ensure the system handles concurrent access reliably.

#### Concurrency Tests
- **`test_concurrent_file_access`**: Tests concurrent file access
- **`test_concurrent_generation`**: Tests concurrent content generation
- **`test_race_conditions`**: Tests race condition handling

### `test_document_generation.py` - Document Generation

**Overall Goal**: Ensure document generation produces correct output formats.

#### Document Tests
- **`test_document_creation`**: Tests document creation
- **`test_document_formatting`**: Tests document formatting
- **`test_document_validation`**: Tests document validation

### `test_document_generation_pytest.py` - Pytest Document Tests

**Overall Goal**: Provide pytest-based document generation tests.

#### Pytest Document Tests
- **`test_document_generation_pytest`**: Pytest-based document generation test

### `test_gpt_helper_integration.py` - GPT Helper Integration

**Overall Goal**: Ensure GPT helper functions work correctly in integrated scenarios.

#### Integration Tests
- **`test_gpt_helper_integration`**: Tests GPT helper integration
- **`test_error_handling_integration`**: Tests error handling integration
- **`test_fallback_integration`**: Tests fallback mechanism integration

### `test_push_validation.py` - Push Validation

**Overall Goal**: Ensure push operations validate content correctly before deployment.

#### Validation Tests
- **`test_push_validation`**: Tests push validation
- **`test_content_validation`**: Tests content validation
- **`test_structure_validation`**: Tests structure validation

## Test Runners

### `tests/integration/runners/`

**Overall Goal**: Provide specialized test runners for different scenarios.

#### Runner Files
- **`run_cli_tests.py`**: Runs CLI-specific tests
- **`run_comprehensive_cli_tests.py`**: Runs comprehensive CLI test suite
- **`run_push_validation.py`**: Runs push validation tests

## Test Configuration

### `conftest.py` - Shared Test Configuration

**Overall Goal**: Provide shared test fixtures and configuration for the entire test suite.

#### Configuration
- **Shared fixtures**: Common test fixtures used across multiple test files
- **Test environment setup**: Environment configuration for tests
- **Mock configurations**: Shared mock configurations

## Current Implementation Alignment

### Key Features Implemented

#### GPTContentGenerator Core Functionality
- **Chain-of-thought reasoning**: All generation methods use structured chain-of-thought prompts
- **Two-stage learning materials generation**: Planning followed by individual material generation
- **Progress tracking**: Checkpointing system for resuming interrupted operations
- **Fallback mechanisms**: Template content when GPT is unavailable
- **Context awareness**: Comprehensive context building for all prompts
- **Industry contextualization**: Support for industry-specific content generation

#### CLI Commands
- **`init`**: Course initialization with comprehensive configuration options
- **`push`**: Document generation and archival
- **`config`**: Configuration file management
- **`convert`**: Markdown to Jupyter notebook conversion using jupytext

#### Course Configuration
- **Multiple course types**: TAFE, COMMERCIAL, ACCELERATED, CUSTOM
- **Flexible week configuration**: Academic and reassessment weeks
- **Industry context**: Support for industry-specific settings
- **Delivery options**: Location, mode, institution, and cohort settings

#### Learning Materials Generation
- **Slides and demo content**: Two types of materials per week
- **Automatic notebook conversion**: Demo.md files converted to .ipynb
- **Structured content**: Markdown-based materials with proper formatting
- **Week-specific content**: Tailored materials for each week

### Test Coverage Alignment

#### Unit Tests Focus
- **Core functionality**: GPT helper methods, CLI parsing, progress management
- **Configuration handling**: Course config validation and defaults
- **Utility functions**: Response boxes, context building, text sanitization
- **Error handling**: Fallback mechanisms and error recovery

#### Integration Tests Focus
- **End-to-end workflows**: Complete CLI command execution
- **File system operations**: Course creation, document generation
- **Progress tracking**: Checkpointing and resume functionality
- **Content generation**: Learning materials and assessment creation

## Test Maintenance Guidelines

### When Adding New Tests

1. **Unit Tests**: Add to `tests/unit/` when testing individual functions or methods
2. **Integration Tests**: Add to `tests/integration/` when testing component interactions
3. **Documentation**: Update this file to explain the rationale for new tests
4. **Naming**: Use descriptive test names that explain what is being tested

### When Modifying Tests

1. **Preserve Intent**: Maintain the original test intent even if implementation changes
2. **Update Documentation**: Update this file if test goals or rationale change
3. **Maintain Coverage**: Ensure modifications don't reduce test coverage

### When Removing Tests

1. **Verify Obsolescence**: Ensure the test is truly no longer needed
2. **Update Documentation**: Remove corresponding entries from this file
3. **Consider Replacement**: Add new tests if functionality is still important

## Test Quality Standards

### Unit Tests Should
- Test one specific behavior or function
- Use descriptive names that explain the test purpose
- Include both positive and negative test cases
- Mock external dependencies appropriately
- Be fast and reliable

### Integration Tests Should
- Test how components work together
- Use realistic data and scenarios
- Test end-to-end workflows
- Handle error conditions gracefully
- Be comprehensive but not exhaustive

### All Tests Should
- Have clear, documented rationale
- Be maintainable and readable
- Provide value in catching regressions
- Run reliably in CI/CD environments
- Follow consistent naming and structure conventions

This documentation serves as a living reference that should be updated whenever tests are added, modified, or removed to maintain clear understanding of the test suite's purpose and goals. 