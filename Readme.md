# Content Generator Tool (Alpha)

No guarantees are given regarding support or stability of this code as it is under active (semi-active) development!

## Installation

### Development Installation

For development and testing:

```bash
# Clone the repository
git clone <repository-url>
cd content_generator

# Install with UV (recommended)
uv sync

# Or install with pip
pip install -e .
```

### Production Installation

For production use:

```bash
# Install with UV
uv add content-generator

# Or install with pip
pip install content-generator
```

### Man Page Installation

Install the man page for command-line help:

```bash
# Using the provided script
python install_manpage.py

# Or manually
sudo cp docs/manpage/gen.1 /usr/local/share/man/man1/
sudo mandb
```

## Command Line Interface

The Content Generator Tool provides a comprehensive CLI for course content generation and management.

### Quick Start

1. **List available AI models:**
   ```bash
   python -m src.main list-models
   ```

2. **Create a course configuration:**
   ```bash
   python -m src.main config --create course_config.yaml --template basic
   ```

3. **Initialize a new course:**
   ```bash
   python -m src.main init --course-name "AI Course" --model "gpt-4.1-nano-2025-04-14" --uoc-codes ICTAII401 ICTAII501
   ```

4. **Generate Key Academic Documents:**
   ```bash
   python -m src.main push --target /path/to/course
   ```

### Available Commands

#### `init` - Initialize a New Course

Creates a complete course structure with all necessary files and directories.

```bash
python -m src.main init --course-name "Course Name" [options]
```

**Required Options:**
- `--course-name, -c`: Name of the course (creates folder with this name)

**Course Configuration:**
- `--course-type, -ct`: Type of course (TAFE, COMMERCIAL, ACCELERATED, CUSTOM) [default: TAFE]
- `--num-weeks, -w`: Total number of weeks for the course
- `--academic-weeks, -aw`: Number of academic weeks
- `--reassessment-weeks, -rw`: Number of reassessment weeks

**AI Model Selection:**
- `--model, -i`: AI model for content generation [default: gpt-4.1-nano-2025-04-14]
  - Examples: `gpt-4.1-nano-2025-04-14`, `gpt-4o-mini`, `gpt-4o`, `claude-3-5-sonnet`

**Content Sources:**
- `--uoc-codes, -u`: Unit of Competency codes (e.g., ICTAII401 ICTAII501)
- `--mission, -m`: Guiding prompt for course context and goals
- `--config-file, -cf`: Path to JSON/YAML configuration file
- `--no-llm`: Disable AI content generation (use templates only)

**Institutional Settings:**
- `--delivery-location, -l`: Primary delivery location (campus, city, etc.)
- `--delivery-mode, -dm`: Delivery mode (face-to-face, online, hybrid) [default: face-to-face]
- `--institution-name, -in`: Institution name for course materials
- `--student-cohort, -sc`: Target student cohort description

**Output Options:**
- `--target, -t`: Path to create the course folder (default: current directory)
- `--theme, -th`: CSS theme file for presentations [default: northmetro.css]

**Examples:**
```bash
# Basic course initialization
python -m src.main init --course-name "Introduction to AI"

# Course with specific model and UOC codes
python -m src.main init --course-name "AI Course" --model "gpt-4o" --uoc-codes ICTAII401 ICTAII501

# Course with configuration file
python -m src.main init --course-name "Custom Course" --config-file course_config.yaml

# Template-only course (no AI generation)
python -m src.main init --course-name "Template Course" --no-llm

# Course with mission prompt
python -m src.main init --course-name "Mission Course" --mission "Focus on practical AI applications"
```

#### `push` - Generate Academic Documents

Generates all Key Academic Documents from the course content.

```bash
python -m src.main push [--target /path/to/course]
```

**Options:**
- `--target, -t`: Path to the course content folder (default: current directory)

**Examples:**
```bash
# Generate documents from current directory
python -m src.main push

# Generate documents from specific course
python -m src.main push --target /path/to/course
```

#### `config` - Manage Course Configuration

Create and manage course configuration files.

```bash
python -m src.main config [options]
```

**Options:**
- `--create, -c`: Create a new configuration file [default: course_config.yaml]
- `--template, -t`: Template type (basic, tafe, commercial, accelerated, custom) [default: basic]
- `--output-dir, -o`: Output directory for configuration file [default: current directory]

**Examples:**
```bash
# Create basic configuration
python -m src.main config --create course_config.yaml

# Create TAFE-specific configuration
python -m src.main config --create tafe_config.yaml --template tafe

# Create configuration in specific directory
python -m src.main config --create config.yaml --output-dir /path/to/configs
```

#### `convert` - Convert Markdown to Notebooks

Convert markdown files to Jupyter notebooks or vice versa using jupytext.

```bash
python -m src.main convert <course_directory> [options]
```

**Options:**
- `--pattern`: File pattern to convert [default: demo.md]
- `--reverse`: Convert notebooks to markdown instead

**Examples:**
```bash
# Convert demo.md files to notebooks
python -m src.main convert /path/to/course

# Convert specific pattern
python -m src.main convert /path/to/course --pattern "*.md"

# Convert notebooks back to markdown
python -m src.main convert /path/to/course --reverse
```

#### `list-models` - List Available AI Models

Display all available AI models for content generation.

```bash
python -m src.main list-models
```

**Output:**
- Lists all available models from OpenAI, Anthropic, and HuggingFace
- Shows model count and provider information
- Caches results for 24 hours to avoid repeated API calls

### AI Model Selection

The tool supports multiple AI providers and models for content generation:

#### **Default Model**
- **`gpt-4.1-nano-2025-04-14`**: Cheapest option, good for basic content generation

#### **Popular Models**
- **OpenAI**: `gpt-4o-mini`, `gpt-4o`, `gpt-4-turbo`
- **Anthropic**: `claude-3-5-sonnet`, `claude-3-opus`, `claude-3-haiku`
- **HuggingFace**: `meta-llama/Llama-3.2-*`, `deepseek-ai/DeepSeek-V3`

#### **Model Selection Examples**
```bash
# Use cheapest model (default)
python -m src.main init --course-name "Course" 

# Use specific OpenAI model
python -m src.main init --course-name "Course" --model "gpt-4o"

# Use Claude model
python -m src.main init --course-name "Course" --model "claude-3-5-sonnet"

# List all available models
python -m src.main list-models
```

### Configuration Templates

The tool provides several configuration templates for different course types:

#### **Basic Template**
- Standard course configuration
- Suitable for most educational contexts

#### **TAFE Template**
- TAFE-specific settings and requirements
- Competency-based assessment structure
- Industry-focused learning outcomes

#### **Commercial Template**
- Commercial training settings
- Flexible assessment options
- Business-oriented content

#### **Accelerated Template**
- Fast-paced learning format
- Condensed timeline
- Intensive assessment structure

#### **Custom Template**
- Fully customizable configuration
- All options available
- Maximum flexibility

### Environment Variables

The tool uses several environment variables for configuration:

```bash
# Required for production
export COURSE_CONTENT="/path/to/course/content"
export OUTPUT_LOCATION="/path/to/output"

# API Keys (optional, for AI content generation)
export OPENAI_API_KEY="your-openai-api-key"
export ANTHROPIC_API_KEY="your-anthropic-api-key"
```

### Help and Documentation

```bash
# General help
python -m src.main --help

# Command-specific help
python -m src.main init --help
python -m src.main push --help
python -m src.main config --help
python -m src.main convert --help

# Man page (if installed)
man gen
```

---

# What does this tool do?

These utilities generate Key Academic Documents from strictly named and formatted markdown files.

This allows us to maintain our academic content separately from the Quality and Development template/formatting requirements.

[An example of the required format of markdown content can be found here](https://github.com/jordanhill-NMTAFE/AISS-ICTSS00120/)

A major selling point is in mapping as this method of maintaining your assessment tools allows you to map your assessments in yaml question-by-question. This means if you need to change the order or remove a question you don't have to rename all your question mapping! Just re-generate the mapping matrix.

Currently supported KADs:

- LAP
- Assess Tool
- Mapping Matrix

# Adding new (or updating) new templates

WARNING: The current implementation relies on the 'template' document's internal template containing the following defined styles:
 - "Heading 1"
 - "Heading 2"
 - "Heading 3"
 - "Heading 4"
 - "Heading 5"
 - "Heading 6"
 - "List Bullet"
 - "List Bullet 2"
 - "List Bullet 3"
 - "code"

To ensure these styles are defined you must: 
 1. open styles pane  
 2. for 'list' at the bottom > select 'All styles' 
 3. Locate relevant style > open dropdown menu > click 'Modify style...' to open the style dialog 
 4. In this dialog check 'add to template' > click 'OK'
 5. Repeat for each required style

 Note: this only applies if you wish to add your own template or style definitions.

The Content Generator Tool is a utility that allows users to create course content by parsing Markdown files and populating a Word document template. There are two primary ways of controlling the output document:


## 1) Template Manipulation

The simplest way to control the output of the generated document is by manipulating the `template` Word document. Users can design the template with the desired layout, styles, and placeholder text/formatting that will be retained in the final document. The Content Generator Tool uses this template as a starting point and fills in relevant content from the Markdown files.

Adjusting the template does not require any programming knowledge. You can open the `.docx` file in Microsoft Word and make changes as if you were editing a normal document. This includes modifying styles, moving or adding headings, paragraphs, images, tables, etc.

When the tool runs, it reads the template and dynamically injects the content from specified Markdown files while preserving the formatting and styles you set up.

## 2) Programmatic Settings via python-docx-oss

For users with Python knowledge, the Content Generator Tool is built on top of `python-docx-oss`, which enables more granular control over the document generation process. Users can write scripts to programmatically define the document's structure, styles, and content.

This method is more involved and is particularly useful for automating complex document creation tasks, such as generating a large number of documents with specific variations, or when needing to perform operations that are not easily done via the template alone.

Users can take advantage of the extensive capabilities of `python-docx-oss` by writing Python code that interacts with the library's objects, methods, and properties to manipulate the Word document before saving the final version.


Fair warning the code for laps and matrix is procedural spaghetti. An effort may be made to refactor & abstract some of the logic into an OOP or functional approach but for now I'm sticking with loops and procedural edits. Any suggestions are welcome!


## Controlling Text Content via Markdown (.md) Files

The Content Generator Tool enables users to define their content in Markdown files, which are then converted to styled Word content. This allows for writing content in a simple, plain text format while still achieving a rich, formatted output.

To add content via Markdown files, write your content following standard Markdown conventions. The tool's parser can recognize headers, lists, emphasis, bolding, italics, and other common formatting elements to convert them into the corresponding Word styles.

### Example with `lap.py`

In the `lap.py` script, Markdown files are read and parsed to extract headings, bullet points, and other elements defined in a structured format. The information gathered is then used to populate specific sections of the Word document template.

For instance, headings in Markdown become headings in the Word document, with the level of the heading (e.g., H1, H2) preserved. Bullet points are transformed into lists, and bold or italic text is styled accordingly.

The script demonstrates how one can use placeholders and structured data within Markdown files to generate a coherent Word document where content and formatting are controlled through simple text editing.

---

In summary, the Content Generator Tool is a powerful utility for creating documents with content defined in Markdown, offering flexibility to adapt the output through both template editing and programmatic customization via `python-docx-oss`. Choose the method that suits your skill level and requirements to achieve the desired result in your course content generation.