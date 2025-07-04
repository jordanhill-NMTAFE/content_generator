# CLI Testing Documentation

This document describes the CLI testing approach for the `gen` tool.

## Overview

The CLI tests are designed to verify that the command-line interface works correctly, including:
- Argument parsing
- Help text generation
- Input validation
- Default values
- Short and long option handling

## Test Structure

### Test Files

- **`tests/test_cli_simple.py`** - Simple CLI test suite (basic argument parsing)
- **`tests/test_cli.py`** - Comprehensive CLI test suite (includes integration testing)
- **`tests/run_cli_tests.py`** - Simple test runner script
- **`tests/run_comprehensive_cli_tests.py`** - Comprehensive test runner script

### Test Categories

#### Simple Tests (`test_cli_simple.py`)
The simple tests focus on basic argument parsing and validation:

#### Comprehensive Tests (`test_cli.py`)
The comprehensive tests include integration testing and more thorough validation:

#### 1. Help System Tests
- `test_main_help` - Main help text
- `test_init_help` - Init command help
- `test_push_help` - Push command help
- `test_config_help` - Config command help

#### 2. Init Command Tests
- Basic argument parsing
- Required arguments validation
- Optional arguments handling
- Course type options (TAFE, COMMERCIAL, ACCELERATED, CUSTOM)
- Weeks configuration
- Delivery options
- UOC codes handling
- Mission prompts
- No-LLM flag
- Config file support
- Short option names

#### 3. Push Command Tests
- Target path handling
- Optional target argument

#### 4. Config Command Tests
- Template creation
- Template type validation
- Output directory handling
- Default values
- Short option names

#### 5. Error Handling Tests
- Missing required arguments
- Invalid course types
- Invalid delivery modes
- Invalid templates
- Unknown commands

## Running the Tests

### Simple Tests (Recommended for Development)

```bash
cd tests
python run_cli_tests.py
```

### Comprehensive Tests (Recommended for CI/CD)

```bash
cd tests
python run_comprehensive_cli_tests.py
```

### Running Individual Tests

```bash
cd tests
python -c "
import sys; sys.path.append('..')
import test_cli_simple
test = test_cli_simple.TestCLISimple()
test.setUp()
test.test_init_basic_args()
print('Test passed!')
"
```

### Using pytest (Alternative)

```bash
cd tests
python -m pytest test_cli_simple.py -v
```

**Note:** pytest may conflict with the CLI parser due to argument parsing conflicts.

## Test Coverage

The CLI tests cover:

### ✅ **Argument Parsing**
- All command-line arguments are correctly parsed
- Short and long option names work
- Required arguments are enforced
- Optional arguments have correct defaults

### ✅ **Validation**
- Invalid choices are rejected
- Missing required arguments trigger errors
- Unknown commands are rejected

### ✅ **Help System**
- Help text is generated correctly
- All commands and options are documented
- Usage information is clear

### ✅ **Default Values**
- Course type defaults to 'TAFE'
- Delivery mode defaults to 'face-to-face'
- Template defaults to 'basic'
- Output directory defaults to '.'

### ✅ **Edge Cases**
- Empty command lists
- Invalid option combinations
- Boundary conditions

## Test Environment

### Setup
- Creates temporary directories for testing
- Sets required environment variables
- Cleans up after tests

### Isolation
- Each test runs in isolation
- No side effects between tests
- Temporary files are cleaned up

## Adding New Tests

To add new CLI tests:

1. **Add test method** to `TestCLISimple` class:
   ```python
   def test_new_feature(self):
       """Test description."""
       args = parser.parse_args(['command', '--option', 'value'])
       self.assertEqual(args.option, 'value')
   ```

2. **Test error cases**:
   ```python
   def test_new_feature_error(self):
       """Test error handling."""
       with self.assertRaises(SystemExit):
           parser.parse_args(['command', '--invalid-option'])
   ```

3. **Run tests** to verify:
   ```bash
   cd tests
   python run_cli_tests.py
   ```

## Best Practices

### Test Design
- **One assertion per test** when possible
- **Clear test names** that describe what's being tested
- **Comprehensive coverage** of all CLI options
- **Error case testing** for validation

### Test Maintenance
- **Update tests** when CLI changes
- **Keep tests simple** and focused
- **Use descriptive docstrings**
- **Test both success and failure cases**

### Test Execution
- **Run tests frequently** during development
- **Use the test runner** to avoid conflicts
- **Check test output** for any issues
- **Maintain test isolation**

## Integration with CI/CD

The CLI tests can be integrated into continuous integration:

```yaml
# Example GitHub Actions step
- name: Run CLI Tests
  run: |
    cd tests
    python run_cli_tests.py
```

## Troubleshooting

### Common Issues

1. **Import errors**: Ensure `src/` is in Python path
2. **Parser conflicts**: Use `run_cli_tests.py` instead of `python -m unittest`
3. **Environment variables**: Tests set required env vars automatically
4. **Temporary files**: Tests clean up automatically

### Debugging

To debug a failing test:

```python
# Add debug output
print(f"Args: {args}")
print(f"Command: {args.command}")
print(f"Course name: {args.course_name}")
```

## Future Enhancements

Potential improvements to the CLI testing:

1. **Integration tests** with actual file operations
2. **Performance tests** for large argument lists
3. **Cross-platform tests** for different OS compatibility
4. **Accessibility tests** for screen readers
5. **Internationalization tests** for different locales

## Conclusion

The CLI testing suite provides comprehensive coverage of the command-line interface, ensuring that:

- All arguments are parsed correctly
- Validation works as expected
- Help text is accurate and complete
- Error handling is robust
- Default values are appropriate

This testing approach helps maintain CLI reliability and provides confidence when making changes to the interface. 