# Content Generator Examples

This directory contains comprehensive examples of all document types processed by the content generation system. These examples serve as:

- **Documentation**: Clear examples of expected input formats
- **Testing**: Reference files for automated testing
- **Templates**: Starting points for new course development
- **Validation**: Standards for quality assurance

## Directory Structure

```
examples/
├── README.md                           # This file
├── course_samples/
│   ├── course_config/                  # Course configuration examples
│   │   └── basic_course.yaml          # Basic TAFE course configuration
│   ├── full_course_structure/          # Complete course example
│   │   ├── 1 Learning Materials/       # Learning content examples
│   │   └── 2 KAD/                      # Knowledge and Assessment Development
│   │       ├── 1 LAP/                  # Learning and Assessment Plan
│   │       │   └── fields.md           # LAP configuration fields
│   │       ├── 5 Assess Tool/          # Assessment instruments
│   │       │   └── AT1 Example Assessment/
│   │       │       └── assessment.md  # Complete assessment example
│   │       ├── 6 Marking Guide/        # Assessment marking guides
│   │       │   └── AT1 Example Assessment/
│   │       │       └── marking_guide.md # Complete marking guide
│   │       └── 7 Assess Mapping Matrix/ # Assessment mapping
│   ├── mapping_matrix/                 # Assessment mapping examples
│   │   └── example_matrix.yaml        # Complete mapping example
│   ├── lap/                           # LAP-specific examples
│   ├── assessments/                   # Assessment-specific examples
│   └── marking_guides/                # Marking guide examples
└── flexible_course_generation.py      # Dynamic course generation example
```

## Document Types and Generators

### 1. Course Configuration (`course_config/`)
**Generator**: `src/content_generator/init.py`
**Purpose**: Configure course parameters, units, and institutional context
**Key Features**:
- Institution details and delivery context
- Unit specifications and learning outcomes
- Assessment strategy and industry alignment
- Resource requirements and infrastructure

### 2. Learning and Assessment Plan (LAP) (`lap/`)
**Generator**: `src/content_generator/lap.py`
**Purpose**: Generate comprehensive learning and assessment plans
**Key Features**:
- Weekly topic progression and learning activities
- Assessment mapping and scheduling
- Resource allocation and infrastructure planning
- Industry context and stakeholder engagement

### 3. Assessment Tools (`assessments/`)
**Generator**: `src/content_generator/assessment_tools.py`
**Purpose**: Create assessment instruments and task specifications
**Key Features**:
- YAML frontmatter with competency mapping
- Structured task instructions and requirements
- Observation and marking checklists
- Evidence requirements and submission guidelines

### 4. Marking Guides (`marking_guides/`)
**Generator**: `src/content_generator/marking_guide.py`
**Purpose**: Generate comprehensive marking guides for assessors
**Key Features**:
- Task-by-task marking criteria and examples
- Observation checklists and evidence requirements
- Professional feedback guidelines
- Competency-based assessment standards

### 5. Mapping Matrix (`mapping_matrix/`)
**Generator**: `src/content_generator/oo_mapping_matrix.py`
**Purpose**: Create assessment mapping matrices showing competency coverage
**Key Features**:
- Unit competency mapping to assessment questions
- Element integrity validation (all criteria together)
- Progressive complexity building across assessments
- Comprehensive competency coverage verification

## File Format Standards

### YAML Frontmatter Structure
All assessment documents use YAML frontmatter for metadata:

```yaml
---
name: "Assessment Name"
qualification_national_code_and_title: "CODE - Qualification Title"
units:
  - id: UNIT_CODE
    name: "Unit Name"
assessment_type: 1  # Optional: for template highlighting
mapping:
  - # Question/Task mapping
    criteria:
      UNIT_CODE: [1.1, 1.2]  # Element criteria (decimal numbers)
    knowledge:
      UNIT_CODE: [1, 2]      # Knowledge evidence (integers)
    skills:
      UNIT_CODE: [1]         # Performance evidence (integers)
    foundation_skills:
      UNIT_CODE: [1]         # Foundation skills (integers)
---
```

### Markdown Content Structure
Content follows standardized markdown patterns:

**Assessment Tools**:
```markdown
# Assessment Resources
## Assessment Instructions
# Assessment Instrument
### Task 1: [Title]
#### Instructions:
[Content]
---
```

**Marking Guides**:
```markdown
### Marking Guide: [Assessment Title]
#### Task 1: [Title]
##### Instructions:
[Requirements and criteria]
```
Example Response:
[Sample answer]
```
---
*[Assessor guidance]*
---
```

## Testing Integration

### Example-Based Testing
Examples are integrated with the test suite for validation:

```python
# Example test structure
def test_assessment_generation_with_examples():
    example_path = Path("examples/course_samples/full_course_structure")
    output_path = Path("test_output")
    
    # Test all generators with examples
    generate_assessments(example_path, output_path)
    generate_marking_guides(example_path, output_path)
    generate_mapping_matrix(example_path, output_path)
    
    # Validate outputs
    assert_valid_word_documents(output_path)
    assert_competency_mapping_integrity(example_path)
```

### Validation Standards
Examples maintain quality standards:
- **Competency Coverage**: All unit competencies addressed
- **Element Integrity**: Complete elements in single assessments
- **Progressive Complexity**: Logical skill building sequence
- **Industry Relevance**: Realistic workplace scenarios
- **Professional Standards**: TAFE/VET quality expectations

## Usage in Development

### Creating New Examples
1. **Choose appropriate directory** based on document type
2. **Follow naming conventions** (assessment names, file structures)
3. **Include comprehensive YAML frontmatter** with all required fields
4. **Provide realistic content** with industry-relevant scenarios
5. **Test with generators** to ensure compatibility

### Updating Examples
1. **Maintain backward compatibility** with existing tests
2. **Update related examples** to maintain consistency
3. **Validate with all generators** after changes
4. **Document changes** in commit messages and PR descriptions

### Testing with Examples
```bash
# Test specific generator with examples
export COURSE_CONTENT="examples/course_samples/full_course_structure"
export OUTPUT_LOCATION="test_output"
uv run python -m src.main push

# Run comprehensive test suite
uv run python -m pytest tests/ -v
```

## Quality Assurance

### Content Standards
- **Accuracy**: Technically correct and industry-relevant
- **Completeness**: All required elements present
- **Consistency**: Uniform formatting and structure
- **Clarity**: Clear instructions and expectations

### Technical Standards
- **Valid YAML**: Proper frontmatter structure
- **Generator Compatibility**: Works with all relevant generators
- **Test Coverage**: Integrated with automated testing
- **Documentation**: Clear usage examples and explanations

## Contributing

When adding new examples:
1. **Follow existing patterns** for structure and format
2. **Include comprehensive metadata** in YAML frontmatter
3. **Provide realistic scenarios** based on actual industry needs
4. **Test thoroughly** with relevant generators
5. **Document usage** and special considerations

### Example Checklist
- [ ] Proper directory structure
- [ ] Complete YAML frontmatter
- [ ] Realistic content scenarios
- [ ] Generator compatibility tested
- [ ] Documentation updated
- [ ] Test integration verified 