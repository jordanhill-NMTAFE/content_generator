# Marking Guide Generator

The marking guide generator creates Word documents from markdown files using the `Instructions to Assessors and Marking Guide (F122A13).docx` template.

## File Structure

The generator looks for `marking_guide.md` files in the following directory structure:
```
course_content/
└── 2 KAD/
    └── 6 Marking Guide/
        └── [Assessment Name]/
            └── marking_guide.md
```

## Markdown Format

### YAML Frontmatter (Optional)
```yaml
---
name: "Assessment Name"
qualification_national_code_and_title: "ICT40120 Certificate IV in Information Technology"
units:
  - id: ICTSS00120
    name: "Work in a team environment"
  - id: ICTAII401
    name: "Confirm and implement opportunities for AI technologies"
assessment_type: 1  # Optional: for assessment type highlighting
---
```

### Content Structure
The markdown content should follow this structure:

```markdown
### Marking Guide: [Assessment Title]

---

#### Task 1: [Task Title]
##### Instructions: 
[Detailed instructions for the task]

Your response must include the following:
1. [Requirement 1]
2. [Requirement 2]
3. [Requirement 3]

```
Example Response:
[Example student response]
```
---
*[Marking notes for assessors]*

---

#### Task 2: [Second Task Title]
##### Instructions:
[Instructions for second task]

[Continue with additional tasks...]

---

### Observation Checklist

#### Checkpoint:
- [Checkpoint 1]
- [Checkpoint 2]
- [Checkpoint 3]

---

#### Marking Criteria:
Each task should be evaluated based on the following scales:
- **Satisfactory (S)**: [Description]
- **Not Yet Satisfactory (NYS)**: [Description]

---

### Additional Feedback
[Guidelines for providing feedback to students]

---
```

## Usage

### CLI Usage
```bash
# Generate all marking guides for a course
python -m src.main push

# Or run the marking guide generator directly
uv run python3 -c "
from src.content_generator.marking_guide import marking_guide_generator
from pathlib import Path
marking_guide_generator(Path('path/to/course'), Path('path/to/output'))
"
```

### Programmatic Usage
```python
from src.content_generator.marking_guide import marking_guide_generator
from pathlib import Path

course_directory = Path("path/to/course/content")
output_directory = Path("path/to/output")

marking_guide_generator(course_directory, output_directory)
```

## Output

The generator creates Word documents at:
```
output_location/
└── 2 KAD/
    └── 6 Marking Guide/
        └── [Assessment Name]/
            └── Instructions to Assessors and Marking Guide (F122A13).docx
```

## Template Population

The generator populates the Word template as follows:

1. **Header Table**: Qualification and unit information from YAML frontmatter
2. **Assessment Task Table**: Assessment name and details
3. **Unit Details Table**: Detailed unit codes and names
4. **Assessment Details Table**: Logistics and instructions summary
5. **Marking Criteria Table**: Comprehensive marking content including:
   - Task instructions and examples
   - Observation checklist
   - Marking criteria and benchmarks
   - Additional feedback guidelines

## Features

- **YAML Frontmatter Support**: Populates template fields from frontmatter
- **Graceful Fallback**: Works with markdown files without frontmatter
- **Rich Content Support**: Converts markdown to formatted Word content
- **Template Consistency**: Uses the official F122A13 template
- **Error Handling**: Robust error handling with descriptive logging

## Requirements

- Python 3.8+
- python-docx
- PyYAML (for frontmatter parsing)
- pathlib
- Environment variables: `ROOT_DIR`, `COURSE_CONTENT`, `OUTPUT_LOCATION` 