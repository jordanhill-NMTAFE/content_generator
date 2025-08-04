# Word Document Analyzer Utility

A comprehensive utility for analyzing Word document templates to understand their structure, tables, and paragraph context relationships.

## Installation

The utility is installed as part of the content generator toolchain:

```bash
gen analyze <document-path> [options]
```

## Usage Examples

### Basic Analysis
```bash
# Full analysis with all details
gen analyze templates/my-template.docx

# Context-only (paragraphs + table headers)
gen analyze templates/my-template.docx --context-only

# Tables-only (detailed table structures)
gen analyze templates/my-template.docx --tables-only
```

### Export Analysis
```bash
# Export to JSON for programmatic use
gen analyze templates/my-template.docx --export analysis.json

# Export to text file for documentation
gen analyze templates/my-template.docx --export analysis.txt
```

## Command Options

| Option | Short | Description |
|--------|-------|-------------|
| `--context-only` | `-c` | Show only paragraph context and table headers |
| `--tables-only` | `-t` | Show only detailed table structures |
| `--export FILE` | `-e` | Export analysis to file (JSON or text) |
| `--help` | `-h` | Show help message |

## Output Format

### Document Structure Analysis
- 📝 **Paragraphs**: Shows paragraph index and content
- 📊 **Tables**: Shows table dimensions and follows relationships
- 📋 **Headers**: Shows table header content for context
- 📐 **Dimensions**: Shows rows × columns for each table

### Key Information Provided
1. **Context Relationships**: Which paragraphs precede which tables
2. **Table Purpose**: Inferred from preceding paragraph content
3. **Table Structure**: Exact dimensions and cell content
4. **Document Flow**: Complete element-by-element structure

## Example Output

```
=== WORD DOCUMENT ANALYSIS ===
Document: templates/Instructions to Assessors and Marking Guide (F122A13).docx
Paragraphs: 21
Tables: 5
Document elements: 27

📋 DOCUMENT STRUCTURE (with context):
----------------------------------------

📊 TABLE 0 (follows P2)
    📐 Dimensions: 2 rows × 2 columns
    📋 Headers: Qualification national code and title

📝 P7: "Pre-requisite Units"

📊 TABLE 2 (follows P8)
    📐 Dimensions: 4 rows × 2 columns
    📋 Headers: National Code | Name of unit
```

## Use Cases

### 1. Understanding Template Structure
Use `--context-only` to quickly understand what each table is for:
```bash
gen analyze templates/marking-guide.docx --context-only
```

### 2. Mapping Tables for Code
Use full analysis to understand exact table structure for populating from code:
```bash
gen analyze templates/marking-guide.docx --export structure.json
```

### 3. Documentation
Export analysis for sharing with team or documentation:
```bash
gen analyze templates/marking-guide.docx --export template-structure.txt
```

## Tips for Future Use

1. **Always run analysis first** when working with new Word templates
2. **Check paragraph context** to understand table purposes
3. **Export to JSON** for programmatic reference in code
4. **Use context-only mode** for quick structure overview
5. **Remember the relationships** between paragraphs and following tables

## Integration with Code

The analysis helps you understand:
- Which table indexes to use in python-docx code
- What YAML fields to create for template population
- How tables relate to document sections
- Available cells and their purposes

Example: From analysis, we learned that Table 2 follows "Pre-requisite Units" paragraph, so we know it's for prerequisites, not assessed units.

## Future Enhancements

This utility can be extended to:
- Analyze other Office document types (.pptx, .xlsx)
- Generate code templates for document population
- Validate document structures against expected patterns
- Compare template versions for changes 