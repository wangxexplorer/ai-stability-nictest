"""Test runner for executing test cases."""
import logging
from typing import List, Dict, Any
from testcase.base import BaseTestCase

logger = logging.getLogger(__name__)


class TestRunner:
    """Runner for executing test cases."""
    
    def __init__(self):
        self.results: List[Dict[str, Any]] = []
    
    def run_test(self, test_case: BaseTestCase) -> Dict[str, Any]:
        """Run a single test case."""
        logger.info(f"Running test: {test_case.test_name}")
        result = test_case.execute()
        self.results.append(result)
        return result
    
    def run_tests(self, test_cases: List[BaseTestCase]) -> List[Dict[str, Any]]:
        """Run multiple test cases."""
        for test_case in test_cases:
            self.run_test(test_case)
        return self.results
    
    def get_summary(self) -> Dict[str, Any]:
        """Get test execution summary."""
        total = len(self.results)
        passed = sum(1 for r in self.results if r.get('passed', False))
        failed = total - passed
        
        return {
            'total': total,
            'passed': passed,
            'failed': failed,
            'pass_rate': passed / total if total > 0 else 0.0
        }
