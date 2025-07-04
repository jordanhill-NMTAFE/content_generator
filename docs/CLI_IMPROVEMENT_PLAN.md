# CLI Entrypoint and GPT Helper Improvement Plan

## Overview

This plan addresses the limitations in the current CLI entrypoint and GPT helper information flow. The goal is to create a more flexible, configurable system that leverages the full capabilities of the GPT helper.

## Step 1: Add Core CLI Configuration Arguments

### 1.1 Modify `src/main.py` - Add Course Configuration Arguments

```python
# Add these arguments to the init_parser in src/main.py
init_parser.add_argument(
    "--course-type",
    "-ct",
    type=str,
    choices=["TAFE", "COMMERCIAL", "ACCELERATED", "CUSTOM"],
    default="TAFE",
    help="Type of course to generate"
)

init_parser.add_argument(
    "--num-weeks",
    "-w",
    type=int,
    help="Total number of weeks for the course"
)

init_parser.add_argument(
    "--academic-weeks",
    "-aw",
    type=int,
    help="Number of academic weeks (defaults based on course type)"
)

init_parser.add_argument(
    "--reassessment-weeks",
    "-rw",
    type=int,
    help="Number of reassessment weeks (defaults based on course type)"
)
```

### 1.2 Add Institutional Context Arguments

```python
init_parser.add_argument(
    "--delivery-location",
    "-dl",
    type=str,
    help="Primary delivery location (campus, city, etc.)"
)

init_parser.add_argument(
    "--delivery-mode",
    "-dm",
    type=str,
    choices=["face-to-face", "online", "hybrid"],
    default="face-to-face",
    help="Primary delivery mode"
)

init_parser.add_argument(
    "--institution-name",
    "-in",
    type=str,
    help="Institution name for course materials"
)

init_parser.add_argument(
    "--student-cohort",
    "-sc",
    type=str,
    help="Target student cohort description"
)
```

### 1.3 Add Configuration File Support

```python
init_parser.add_argument(
    "--config-file",
    "-cf",
    type=str,
    help="Path to JSON/YAML configuration file"
)
```

## Step 2: Update CourseInitializer to Handle New Arguments

### 2.1 Modify `src/content_generator/init.py` - Update Constructor

```python
def __init__(self, course_name: str, target_path: Optional[Path] = None, 
             uoc_codes: Optional[List[str]] = None, mission_prompt: Optional[str] = None, 
             no_llm: bool = False, course_type: str = "TAFE", num_weeks: Optional[int] = None,
             academic_weeks: Optional[int] = None, reassessment_weeks: Optional[int] = None,
             delivery_location: Optional[str] = None, delivery_mode: str = "face-to-face",
             institution_name: Optional[str] = None, student_cohort: Optional[str] = None,
             config_file: Optional[str] = None):
    
    self.course_name = course_name
    self.target_path = target_path or Path.cwd()
    self.course_path = self.target_path / course_name
    self.uoc_codes = uoc_codes or []
    self.mission_prompt = mission_prompt
    self.no_llm = no_llm
    
    # Load configuration from file if provided
    if config_file:
        self.config = self._load_config_file(config_file)
    else:
        self.config = self._build_config_from_args(
            course_type, num_weeks, academic_weeks, reassessment_weeks,
            delivery_location, delivery_mode, institution_name, student_cohort
        )
    
    self.units = []
    self.gpt_generator = None if no_llm else create_gpt_generator(self.config.course_config)
```

### 2.2 Add Configuration Loading Methods

```python
def _load_config_file(self, config_file: str) -> Dict:
    """Load configuration from JSON/YAML file"""
    import yaml
    import json
    
    with open(config_file, 'r') as f:
        if config_file.endswith('.yaml') or config_file.endswith('.yml'):
            return yaml.safe_load(f)
        else:
            return json.load(f)

def _build_config_from_args(self, course_type: str, num_weeks: Optional[int],
                           academic_weeks: Optional[int], reassessment_weeks: Optional[int],
                           delivery_location: Optional[str], delivery_mode: str,
                           institution_name: Optional[str], student_cohort: Optional[str]) -> Dict:
    """Build configuration from CLI arguments"""
    return {
        'course': {
            'type': course_type,
            'num_weeks': num_weeks,
            'academic_weeks': academic_weeks,
            'reassessment_weeks': reassessment_weeks
        },
        'institution': {
            'name': institution_name,
            'delivery_location': delivery_location,
            'delivery_mode': delivery_mode
        },
        'students': {
            'cohort': student_cohort
        }
    }
```

## Step 3: Enhance UOC Data Utilization

### 3.1 Update UOC Data Structure in `src/content_generator/init.py`

```python
def fetch_uoc_data(self) -> None:
    """Fetch Unit of Competency data with enhanced information"""
    if not self.uoc_codes:
        log.info("No UOC codes provided, using template data")
        return
    
    log.info(f"Fetching UOC data for codes: {', '.join(self.uoc_codes)}")
    
    for uoc_code in self.uoc_codes:
        try:
            uoc = UnitOfCompetency(uoc_code)
            self.units.append({
                'id': uoc_code,
                'name': uoc.data.application.split('.')[0] if uoc.data.application else f"Unit {uoc_code}",
                'data': uoc.data,
                'elements': uoc.data.elements if hasattr(uoc.data, 'elements') else [],
                'performance_criteria': uoc.data.performance_criteria if hasattr(uoc.data, 'performance_criteria') else [],
                'foundation_skills': uoc.data.foundation_skills if hasattr(uoc.data, 'foundation_skills') else [],
                'assessment_requirements': uoc.data.assessment_requirements if hasattr(uoc.data, 'assessment_requirements') else [],
                'prerequisites': uoc.data.prerequisites if hasattr(uoc.data, 'prerequisites') else []
            })
            log.info(f"Successfully fetched UOC data for {uoc_code}")
        except UnitOfCompetencyNotFoundError as e:
            log.error(f"UOC not found: {e}")
        except Exception as e:
            log.error(f"Failed to fetch UOC data for {uoc_code}: {e}")
```

## Step 4: Update GPT Helper to Use Enhanced Context

### 4.1 Modify `src/utils/gpt_helper.py` - Add Context Builder

```python
class CourseContextBuilder:
    """Builds comprehensive context for GPT generation"""
    
    def __init__(self, config: Dict, units: List[Dict], mission_prompt: Optional[str] = None):
        self.config = config
        self.units = units
        self.mission_prompt = mission_prompt
    
    def build_full_context(self) -> str:
        """Build complete context string for GPT prompts"""
        context_parts = []
        
        # Course configuration context
        course_config = self.config.get('course', {})
        context_parts.append(f"Course Type: {course_config.get('type', 'TAFE')}")
        context_parts.append(f"Total Weeks: {course_config.get('num_weeks', 20)}")
        context_parts.append(f"Academic Weeks: {course_config.get('academic_weeks', 18)}")
        context_parts.append(f"Reassessment Weeks: {course_config.get('reassessment_weeks', 2)}")
        
        # Institutional context
        institution = self.config.get('institution', {})
        if institution.get('name'):
            context_parts.append(f"Institution: {institution['name']}")
        if institution.get('delivery_location'):
            context_parts.append(f"Delivery Location: {institution['delivery_location']}")
        if institution.get('delivery_mode'):
            context_parts.append(f"Delivery Mode: {institution['delivery_mode']}")
        
        # Student context
        students = self.config.get('students', {})
        if students.get('cohort'):
            context_parts.append(f"Student Cohort: {students['cohort']}")
        
        # Unit information
        if self.units:
            unit_info = "\n".join([
                f"- {unit['id']}: {unit['name']}" for unit in self.units
            ])
            context_parts.append(f"Units of Competency:\n{unit_info}")
        
        # Mission prompt
        if self.mission_prompt:
            context_parts.append(f"Mission Context:\n{self.mission_prompt}")
        
        return "\n\n".join(context_parts)
```

### 4.2 Update GPT Generation Methods

```python
def generate_course_overview(self, units: List[Dict[str, Any]], 
                           mission_prompt: Optional[str] = None,
                           context_builder: Optional[CourseContextBuilder] = None) -> str:
    """Generate course overview with enhanced context"""
    
    # Build comprehensive context
    if context_builder:
        full_context = context_builder.build_full_context()
    else:
        full_context = self._build_basic_context(units, mission_prompt)
    
    # Enhanced prompt with full context
    prompt = f"""Generate a comprehensive course overview based on the following context:

{full_context}

Consider the following aspects:
1. Course structure and progression
2. Learning outcomes and competencies
3. Delivery mode considerations
4. Student cohort characteristics
5. Institutional requirements

{ResponseBox.wrap("", "COURSE_OVERVIEW")}"""
    
    # Rest of the method remains the same...
```

## Step 5: Add Configuration File Templates

### 5.1 Create `templates/course_config.yaml`

```yaml
# Template for course configuration
course:
  type: "TAFE"  # TAFE, COMMERCIAL, ACCELERATED, CUSTOM
  num_weeks: 20
  academic_weeks: 18
  reassessment_weeks: 2

institution:
  name: "North Metropolitan TAFE"
  delivery_location: "Perth"
  delivery_mode: "face-to-face"  # face-to-face, online, hybrid

students:
  cohort: "mature-age students with industry experience"
  typical_background: "IT professionals seeking upskilling"

assessments:
  structure:
    - title: "Practical Project"
      type: "project"
      weight: 30
      due_week: 8
    - title: "Knowledge Assessment"
      type: "test"
      weight: 25
      due_week: 12
    - title: "Research Presentation"
      type: "presentation"
      weight: 25
      due_week: 15
    - title: "Final Assessment"
      type: "comprehensive"
      weight: 20
      due_week: 18

learning_phases:
  foundation: [1, 4]
  development: [5, 8]
  application: [9, 12]
  advanced: [13, 16]
  synthesis: [17, 18]
```

## Step 6: Update Main CLI Function

### 6.1 Modify `src/main.py` - Update init() Function

```python
def init():
    """Initialize a new course content folder"""
    print(f"Initializing new course: {args.course_name}")

    target_path = None
    if args.target:
        target_path = Path(args.target)
        if not target_path.exists():
            print(f"Target path {target_path} does not exist. Creating...")
            target_path.mkdir(parents=True, exist_ok=True)

    # Handle mission prompt input
    mission_prompt = args.mission
    if mission_prompt and mission_prompt.startswith("<<"):
        print("Enter your mission prompt (end with '<<' on a new line):")
        lines = []
        while True:
            try:
                line = input()
                if line.strip() == "<<":
                    break
                lines.append(line)
            except EOFError:
                break
        mission_prompt = "\n".join(lines)

    try:
        course_path = init_course(
            args.course_name, 
            target_path, 
            args.uoc_codes, 
            mission_prompt, 
            args.no_llm,
            course_type=args.course_type,
            num_weeks=args.num_weeks,
            academic_weeks=args.academic_weeks,
            reassessment_weeks=args.reassessment_weeks,
            delivery_location=args.delivery_location,
            delivery_mode=args.delivery_mode,
            institution_name=args.institution_name,
            student_cohort=args.student_cohort,
            config_file=args.config_file
        )
        
        print(f"Course '{args.course_name}' initialized successfully!")
        print(f"Course location: {course_path}")
        
        # Enhanced feedback
        if args.config_file:
            print(f"✓ Configuration loaded from: {args.config_file}")
        if args.course_type != "TAFE":
            print(f"✓ Course type: {args.course_type}")
        if args.num_weeks and args.num_weeks != 20:
            print(f"✓ Course duration: {args.num_weeks} weeks")
        if args.delivery_mode != "face-to-face":
            print(f"✓ Delivery mode: {args.delivery_mode}")
        
        # Rest of the feedback remains the same...
        
    except Exception as e:
        print(f"Failed to initialize course: {e}")
        return 1

    return 0
```

## Step 7: Add Validation

### 7.1 Create `src/utils/validation.py`

```python
class ConfigurationValidator:
    """Validates course configuration"""
    
    @staticmethod
    def validate_course_config(config: Dict) -> List[str]:
        """Validate course configuration and return list of errors"""
        errors = []
        
        course = config.get('course', {})
        
        # Validate course type
        valid_types = ["TAFE", "COMMERCIAL", "ACCELERATED", "CUSTOM"]
        if course.get('type') not in valid_types:
            errors.append(f"Invalid course type. Must be one of: {', '.join(valid_types)}")
        
        # Validate weeks
        num_weeks = course.get('num_weeks')
        if num_weeks and (num_weeks < 1 or num_weeks > 52):
            errors.append("Number of weeks must be between 1 and 52")
        
        academic_weeks = course.get('academic_weeks')
        reassessment_weeks = course.get('reassessment_weeks')
        
        if academic_weeks and reassessment_weeks:
            if academic_weeks + reassessment_weeks != num_weeks:
                errors.append("Academic weeks + reassessment weeks must equal total weeks")
        
        return errors
    
    @staticmethod
    def validate_uoc_codes(codes: List[str]) -> List[str]:
        """Validate UOC codes exist"""
        errors = []
        for code in codes:
            try:
                from src.utils.uoc_api import UnitOfCompetency
                UnitOfCompetency(code)
            except Exception:
                errors.append(f"Invalid or inaccessible UOC code: {code}")
        return errors
```

## Step 8: Update init_course Function Signature

### 8.1 Modify `src/content_generator/init.py` - Update Function Signature

```python
def init_course(course_name: str, target_path: Optional[Path] = None, 
                uoc_codes: Optional[List[str]] = None, mission_prompt: Optional[str] = None, 
                no_llm: bool = False, course_type: str = "TAFE", 
                num_weeks: Optional[int] = None, academic_weeks: Optional[int] = None,
                reassessment_weeks: Optional[int] = None, delivery_location: Optional[str] = None,
                delivery_mode: str = "face-to-face", institution_name: Optional[str] = None,
                student_cohort: Optional[str] = None, config_file: Optional[str] = None) -> Path:
    """
    Initialize a new course with enhanced configuration options.
    """
    initializer = CourseInitializer(
        course_name, target_path, uoc_codes, mission_prompt, no_llm,
        course_type, num_weeks, academic_weeks, reassessment_weeks,
        delivery_location, delivery_mode, institution_name, student_cohort, config_file
    )
    return initializer.initialize_course()
```

## Testing the Implementation

### Test Commands

```bash
# Basic usage with new arguments
python -m src.main init "AI Course" --course-type COMMERCIAL --num-weeks 12 --delivery-mode online

# Using configuration file
python -m src.main init "AI Course" --config-file templates/course_config.yaml

# Full custom configuration
python -m src.main init "AI Course" \
  --course-type CUSTOM \
  --num-weeks 16 \
  --academic-weeks 14 \
  --reassessment-weeks 2 \
  --delivery-location "Perth Campus" \
  --delivery-mode hybrid \
  --institution-name "North Metropolitan TAFE" \
  --student-cohort "mature-age IT professionals" \
  --uoc-codes ICTAII401 ICTAII501 \
  --mission "Advanced AI course for industry professionals"
```

## Summary

This step-by-step plan provides:

1. **Enhanced CLI Arguments** - Full control over course configuration
2. **Configuration File Support** - Complex setups via YAML/JSON
3. **Better UOC Data Utilization** - Leverage all available competency information
4. **Context-Aware Generation** - GPT prompts with comprehensive context
5. **Validation** - Ensure configuration correctness
6. **Backward Compatibility** - Existing functionality preserved

The implementation transforms the rigid system into a flexible, powerful tool that fully leverages the GPT helper's capabilities. 