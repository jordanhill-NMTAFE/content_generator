#!/usr/bin/env python3
"""
Script to run push validation tests and generate comprehensive reports.
Validates the push function against the AISS-ICTSS00120 config and example course.
"""

import os
import sys
import json
import shutil
import tempfile
from pathlib import Path
from datetime import datetime
import subprocess
import yaml
from typing import Dict, List, Any

# Imports are now handled by conftest.py

from src.main import init_course, push
from src.gptgen.content_generator import create_gpt_generator


class PushValidationRunner:
    """Runner for push validation tests with comprehensive reporting."""

    def __init__(self, output_dir: str = "test_outputs/aiss_validation"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.report_data = {
            "timestamp": datetime.now().isoformat(),
            "tests_run": [],
            "summary": {},
            "issues": [],
            "recommendations": [],
        }

    def load_config(self) -> Dict[str, Any]:
        """Load the AISS-ICTSS00120 configuration."""
        config_path = Path("aiss_ictss00120_config.yaml")
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")

        with open(config_path, "r") as f:
            return yaml.safe_load(f)

    def run_init_validation(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Run init function validation."""
        print("Running init validation...")

        test_dir = self.output_dir / "generated_course"
        if test_dir.exists():
            shutil.rmtree(test_dir)

        test_dir.mkdir(parents=True)

        try:
            # Mock GPT client to avoid API calls
            with self.mock_gpt_client():
                init_course(
                    course_name=config["course_name"],
                    target_path=test_dir,
                    course_type=config["course_type"],
                    num_weeks=config["weeks"],
                    delivery_mode=config["delivery_mode"],
                    institution_name=config["institution"],
                    student_cohort=config["student_cohort"],
                    mission_prompt=config["mission"],
                    uoc_codes=[u["id"] for u in config["units"]],
                )

            # Validate structure
            course_dir = test_dir / config["course_name"]
            validation_result = self.validate_course_structure(course_dir, config)

            return {
                "status": "passed" if validation_result["passed"] else "failed",
                "course_dir": str(course_dir),
                "validation": validation_result,
            }

        except Exception as e:
            return {"status": "error", "error": str(e), "course_dir": str(test_dir)}

    def run_push_validation(self, course_dir: str) -> Dict[str, Any]:
        """Run push function validation."""
        print("Running push validation...")

        documents_dir = self.output_dir / "documents"
        if documents_dir.exists():
            shutil.rmtree(documents_dir)
        documents_dir.mkdir(parents=True)

        try:
            # Mock GPT client to avoid API calls
            with self.mock_gpt_client():
                # Create args object for generate function
                class Args:
                    def __init__(self, target):
                        self.target = target

                args = Args(course_dir)
                push(args)

            # Validate documents
            validation_result = self.validate_documents(Path(course_dir))

            return {
                "status": "passed" if validation_result["passed"] else "failed",
                "documents_dir": str(documents_dir),
                "validation": validation_result,
            }

        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "documents_dir": str(documents_dir),
            }

    def validate_course_structure(
        self, course_dir: Path, config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate the course directory structure."""
        issues = []
        passed = True

        # Check required directories
        required_dirs = ["1 Learning Materials", "2 KAD", "docs"]
        for dir_name in required_dirs:
            dir_path = course_dir / dir_name
            if not dir_path.exists():
                issues.append(f"Missing required directory: {dir_name}")
                passed = False

        # Check KAD subdirectories
        if (course_dir / "2 KAD").exists():
            kad_subdirs = [
                "1 LAP",
                "2 Preassess Validation",
                "3 Postassess Validation",
                "4 Assess Sub and FB Form",
                "5 Assess Tool",
                "6 Marking Guide",
                "7 Assess Mapping Matrix",
            ]
            for subdir in kad_subdirs:
                subdir_path = course_dir / "2 KAD" / subdir
                if not subdir_path.exists():
                    issues.append(f"Missing KAD subdirectory: {subdir}")
                    passed = False

        # Check assessment tools
        assess_tool_dir = course_dir / "2 KAD" / "5 Assess Tool"
        if assess_tool_dir.exists():
            expected_assessments = [
                "AT1 Identify Opportunities for AI Task Automation",
                "AT2 Knowledge Based Assessment",
                "AT3 Knowledge Based Assessment",
                "AT4 Apply Machine Learning to Task Automation",
            ]
            for assessment in expected_assessments:
                assessment_path = assess_tool_dir / assessment
                if not assessment_path.exists():
                    issues.append(f"Missing assessment directory: {assessment}")
                    passed = False
                else:
                    # Check for assessment.md
                    assessment_file = assessment_path / "assessment.md"
                    if not assessment_file.exists():
                        issues.append(f"Missing assessment.md in {assessment}")
                        passed = False

        # Check learning materials
        learning_materials_dir = course_dir / "1 Learning Materials"
        if learning_materials_dir.exists():
            for week_num in range(1, config["weeks"] + 1):
                week_dir = learning_materials_dir / f"Week {week_num}"
                if not week_dir.exists():
                    issues.append(f"Missing Week {week_num} directory")
                    passed = False
                else:
                    # Check required files
                    required_files = ["slides.md", "footer.png"]
                    for file_name in required_files:
                        file_path = week_dir / file_name
                        if not file_path.exists():
                            issues.append(f"Missing {file_name} in Week {week_num}")
                            passed = False

        return {"passed": passed, "issues": issues, "total_issues": len(issues)}

    def validate_documents(self, course_dir: Path) -> Dict[str, Any]:
        """Validate that required documents are generated."""
        issues = []
        passed = True

        required_documents = [
            "2 KAD/1 LAP/Learning and Assessment Plan (F122A14).docx",
            "2 KAD/5 Assess Tool/AT1 Identify Opportunities for AI Task Automation/Assessment Task Tool (F122A12).docx",
            "2 KAD/5 Assess Tool/AT2 Knowledge Based Assessment/Assessment Task Tool (F122A12).docx",
            "2 KAD/5 Assess Tool/AT3 Knowledge Based Assessment/Assessment Task Tool (F122A12).docx",
            "2 KAD/5 Assess Tool/AT4 Apply Machine Learning to Task Automation/Assessment Task Tool (F122A12).docx",
            "2 KAD/7 Assess Mapping Matrix/ICTAII401 Assessment Mapping Matrix (F122A8).docx",
            "2 KAD/7 Assess Mapping Matrix/ICTAII501 Assessment Mapping Matrix (F122A8).docx",
            "2 KAD/7 Assess Mapping Matrix/ICTAII502 Assessment Mapping Matrix (F122A8).docx",
        ]

        for doc_path in required_documents:
            full_path = course_dir / doc_path
            if not full_path.exists():
                issues.append(f"Missing required document: {doc_path}")
                passed = False

        return {
            "passed": passed,
            "issues": issues,
            "total_issues": len(issues),
            "documents_checked": len(required_documents),
        }

    def compare_with_example(self, generated_course_dir: str) -> Dict[str, Any]:
        """Compare generated course with example course structure."""
        print("Comparing with example course...")

        example_course_path = Path("example/AISS-ICTSS00120")
        if not example_course_path.exists():
            return {"status": "skipped", "reason": "Example course not found"}

        comparison_dir = self.output_dir / "comparison"
        comparison_dir.mkdir(parents=True, exist_ok=True)

        issues = []
        passed = True

        # Compare assessment tool structure
        example_assess_tool_dir = example_course_path / "2 KAD" / "5 Assess Tool"
        generated_assess_tool_dir = (
            Path(generated_course_dir) / "2 KAD" / "5 Assess Tool"
        )

        if example_assess_tool_dir.exists() and generated_assess_tool_dir.exists():
            example_assessments = [
                d.name for d in example_assess_tool_dir.iterdir() if d.is_dir()
            ]
            generated_assessments = [
                d.name for d in generated_assess_tool_dir.iterdir() if d.is_dir()
            ]

            if set(example_assessments) != set(generated_assessments):
                issues.append(
                    f"Assessment directories don't match. Expected: {example_assessments}, Got: {generated_assessments}"
                )
                passed = False

        return {
            "status": "passed" if passed else "failed",
            "passed": passed,
            "issues": issues,
            "total_issues": len(issues),
        }

    def mock_gpt_client(self):
        """Context manager to mock GPT client."""
        from unittest.mock import patch, MagicMock

        return patch(
            "gpt.models.openai_.Chat",
            return_value=MagicMock(),
        )

    def generate_report(self) -> str:
        """Generate a comprehensive validation report."""
        report_path = self.output_dir / "validation_report.json"

        with open(report_path, "w") as f:
            json.dump(self.report_data, f, indent=2)

        # Generate markdown report
        md_report_path = self.output_dir / "validation_report.md"
        self.generate_markdown_report(md_report_path)

        return str(report_path)

    def generate_markdown_report(self, report_path: Path):
        """Generate a markdown version of the validation report."""
        with open(report_path, "w") as f:
            f.write("# Push Validation Report\n\n")
            f.write(f"**Generated:** {self.report_data['timestamp']}\n\n")

            # Summary
            f.write("## Summary\n\n")
            total_tests = len(self.report_data["tests_run"])
            passed_tests = sum(
                1
                for test in self.report_data["tests_run"]
                if test.get("status") == "passed"
            )
            failed_tests = total_tests - passed_tests

            f.write(f"- **Total Tests:** {total_tests}\n")
            f.write(f"- **Passed:** {passed_tests}\n")
            f.write(f"- **Failed:** {failed_tests}\n\n")

            # Test Results
            f.write("## Test Results\n\n")
            for test in self.report_data["tests_run"]:
                status_emoji = "✅" if test.get("status") == "passed" else "❌"
                f.write(f"### {status_emoji} {test['name']}\n")
                f.write(f"- **Status:** {test.get('status', 'unknown')}\n")

                if "validation" in test:
                    validation = test["validation"]
                    f.write(f"- **Issues:** {validation.get('total_issues', 0)}\n")
                    if validation.get("issues"):
                        f.write("- **Details:**\n")
                        for issue in validation["issues"]:
                            f.write(f"  - {issue}\n")

                if "error" in test:
                    f.write(f"- **Error:** {test['error']}\n")

                f.write("\n")

            # Issues and Recommendations
            if self.report_data["issues"]:
                f.write("## Issues Found\n\n")
                for issue in self.report_data["issues"]:
                    f.write(f"- {issue}\n")
                f.write("\n")

            if self.report_data["recommendations"]:
                f.write("## Recommendations\n\n")
                for rec in self.report_data["recommendations"]:
                    f.write(f"- {rec}\n")
                f.write("\n")

    def run_full_validation(self):
        """Run the complete validation suite."""
        print("Starting push validation suite...")

        try:
            # Load config
            config = self.load_config()

            # Run init validation
            init_result = self.run_init_validation(config)
            self.report_data["tests_run"].append(
                {"name": "Init Course Structure Validation", **init_result}
            )

            # Run push validation if init passed
            if init_result["status"] == "passed":
                push_result = self.run_push_validation(init_result["course_dir"])
                self.report_data["tests_run"].append(
                    {"name": "Push Document Generation Validation", **push_result}
                )

                # Compare with example
                comparison_result = self.compare_with_example(init_result["course_dir"])
                self.report_data["tests_run"].append(
                    {"name": "Example Course Comparison", **comparison_result}
                )

            # Generate summary
            total_tests = len(self.report_data["tests_run"])
            passed_tests = sum(
                1
                for test in self.report_data["tests_run"]
                if test.get("status") == "passed"
            )

            self.report_data["summary"] = {
                "total_tests": total_tests,
                "passed_tests": passed_tests,
                "failed_tests": total_tests - passed_tests,
                "success_rate": (passed_tests / total_tests * 100)
                if total_tests > 0
                else 0,
            }

            # Generate report
            report_path = self.generate_report()
            print(f"Validation complete. Report saved to: {report_path}")

            return self.report_data["summary"]["success_rate"] == 100

        except Exception as e:
            print(f"Validation failed with error: {e}")
            self.report_data["tests_run"].append(
                {"name": "Validation Suite", "status": "error", "error": str(e)}
            )
            return False


def main():
    """Main entry point for the validation runner."""
    runner = PushValidationRunner()
    success = runner.run_full_validation()

    if success:
        print("✅ All validation tests passed!")
        sys.exit(0)
    else:
        print("❌ Some validation tests failed. Check the report for details.")
        sys.exit(1)


if __name__ == "__main__":
    main()
