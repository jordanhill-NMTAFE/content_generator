# Examples Integration Guide

## Quick Start

The repository now includes comprehensive in-repo examples that demonstrate all document generators and provide testing standards.

### 🚀 Try It Out

```bash
# Run all generators with examples
python examples/run_example_generators.py

# Run the test suite
uv run python -m pytest tests/integration/test_examples_integration.py -v

# See individual generator usage examples
python examples/run_example_generators.py --examples
```

### 📁 Examples Structure

```
examples/course_samples/
├── course_config/basic_course.yaml          # Course configuration
├── full_course_structure/                   # Complete course example
│   └── 2 KAD/
│       ├── 1 LAP/fields.md                 # LAP configuration
│       ├── 5 Assess Tool/                  # Assessment examples
│       └── 6 Marking Guide/                # Marking guide examples
└── mapping_matrix/example_matrix.yaml      # Assessment mapping
```

## 📋 What You Get

### ✅ **Complete Examples**
- **Assessment Tools**: Full assessment with YAML frontmatter and competency mapping
- **Marking Guides**: Comprehensive marking criteria with example responses
- **LAP Generation**: Complete field configuration with industry context
- **Mapping Matrix**: Complex competency mapping with validation rules
- **Course Configuration**: Institution setup and unit specifications

### ✅ **Comprehensive Testing**
- **Generator Validation**: All generators tested with examples
- **Format Validation**: YAML and markdown structure verification
- **Quality Assurance**: Content standards and consistency checking
- **Output Validation**: Generated document quality verification

### ✅ **Developer Resources**
- **Interactive Demo**: `examples/run_example_generators.py`
- **Usage Patterns**: Clear examples for each generator
- **Test Integration**: Automated testing with example validation
- **Documentation**: Complete usage guides and standards

## 🎯 Benefits

### **For Development**
- **Self-Contained**: No external course content dependencies
- **Quality Standards**: Validation tests ensure example quality
- **Testing**: Stable reference targets for regression testing
- **Documentation**: Clear examples of expected input formats

### **For Usage**
- **Learning**: Complete examples showing best practices
- **Templates**: Starting points for new course development
- **Validation**: Quality benchmarks for content creation
- **Testing**: Easy way to test and understand generators

## 📖 Usage Examples

### Generate Documents with Examples
```python
from src.content_generator.assessment_tools import assess_tool
from pathlib import Path

course_path = Path("examples/course_samples/full_course_structure")
output_path = Path("output")

assess_tool(course_path, output_path)
```

### Test All Generators
```bash
# Interactive demonstration
python examples/run_example_generators.py

# Automated testing
uv run python -m pytest tests/integration/test_examples_integration.py -v
```

### Create New Content
1. Copy example structure: `cp -r examples/course_samples/full_course_structure my_course`
2. Modify YAML frontmatter and content
3. Test with generators: `python -m src.main push`
4. Validate with test suite

## 🔧 Integration

The examples integrate seamlessly with existing workflows:

- **CLI Commands**: All examples work with `python -m src.main push`
- **Environment Variables**: Standard `COURSE_CONTENT` and `OUTPUT_LOCATION` usage  
- **Output Structure**: Consistent with existing output patterns
- **Quality Standards**: TAFE/VET professional standards maintained

## 📚 Documentation

- **Complete Guide**: `examples/README.md` - Comprehensive documentation
- **Implementation Summary**: `EXAMPLES_IMPLEMENTATION_SUMMARY.md` - Technical details
- **This Guide**: Quick start and usage patterns

## ✨ Next Steps

1. **Explore Examples**: Browse `examples/course_samples/` to understand structures
2. **Run Demo**: Try `python examples/run_example_generators.py`  
3. **Run Tests**: Execute `uv run python -m pytest tests/integration/test_examples_integration.py -v`
4. **Create Content**: Use examples as templates for new course development
5. **Contribute**: Add new examples following established patterns

The examples structure provides a solid foundation for development, testing, and quality assurance of the content generation system. 