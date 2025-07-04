#!/usr/bin/env python3
"""
Simple test runner for CLI tests
"""

import sys
import unittest

# Import the test module
from tests.integration.test_cli_simple import TestCLISimple


def run_tests():
    """Run all CLI tests."""
    # Create test suite
    suite = unittest.TestLoader().loadTestsFromTestCase(TestCLISimple)

    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Return exit code
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(run_tests())
