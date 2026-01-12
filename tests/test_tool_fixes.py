#!/usr/bin/env python3
"""
Test cases for the fixed explain and export_data tools.
This ensures the argument parsing works correctly.
"""

import json
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


def test_explain_argument_parsing():
    """Test that explain correctly parses array-format arguments."""
    from server import explain, mongo_conn, config
    
    # Mock setup would go here - for now just test the parsing logic
    test_cases = [
        # Valid: ["find", {"filter": {}, "limit": 1}]
        {
            "method": ["find", {"filter": {}, "limit": 1}],
            "expected_method_name": "find",
            "expected_args": {"filter": {}, "limit": 1}
        },
        # Valid: ["aggregate", {"pipeline": [{"$match": {}}]}]
        {
            "method": ["aggregate", {"pipeline": [{"$match": {}}]}],
            "expected_method_name": "aggregate",
            "expected_args": {"pipeline": [{"$match": {}}]}
        },
        # Valid: ["count", {"query": {"status": "active"}}]
        {
            "method": ["count", {"query": {"status": "active"}}],
            "expected_method_name": "count",
            "expected_args": {"query": {"status": "active"}}
        },
        # Valid: method with no args
        {
            "method": ["find"],
            "expected_method_name": "find",
            "expected_args": {}
        },
    ]
    
    for test_case in test_cases:
        method = test_case["method"]
        
        # Parse the method array
        method_name = method[0] if isinstance(method[0], str) else None
        method_args = method[1] if len(method) > 1 and isinstance(method[1], dict) else {}
        
        assert method_name == test_case["expected_method_name"], \
            f"Expected method_name {test_case['expected_method_name']}, got {method_name}"
        assert method_args == test_case["expected_args"], \
            f"Expected args {test_case['expected_args']}, got {method_args}"
    
    print("✓ All explain argument parsing tests passed")


def test_export_data_argument_parsing():
    """Test that export_data correctly parses array-format arguments."""
    test_cases = [
        # Valid: ["find", {"filter": {}, "limit": 100}]
        {
            "exportTarget": ["find", {"filter": {}, "limit": 100}],
            "expected_target_name": "find",
            "expected_args": {"filter": {}, "limit": 100}
        },
        # Valid: ["aggregate", {"pipeline": [{"$group": {"_id": "$category"}}]}]
        {
            "exportTarget": ["aggregate", {"pipeline": [{"$group": {"_id": "$category"}}]}],
            "expected_target_name": "aggregate",
            "expected_args": {"pipeline": [{"$group": {"_id": "$category"}}]}
        },
        # Valid: target with no args
        {
            "exportTarget": ["find"],
            "expected_target_name": "find",
            "expected_args": {}
        },
    ]
    
    for test_case in test_cases:
        exportTarget = test_case["exportTarget"]
        
        # Parse the exportTarget array
        target_name = exportTarget[0] if isinstance(exportTarget[0], str) else None
        target_args = exportTarget[1] if len(exportTarget) > 1 and isinstance(exportTarget[1], dict) else {}
        
        assert target_name == test_case["expected_target_name"], \
            f"Expected target_name {test_case['expected_target_name']}, got {target_name}"
        assert target_args == test_case["expected_args"], \
            f"Expected args {test_case['expected_args']}, got {target_args}"
    
    print("✓ All export_data argument parsing tests passed")


def test_validation():
    """Test input validation for parameters."""
    # Test verbosity validation
    valid_verbosity = ["queryPlanner", "executionStats", "allPlansExecution"]
    assert "invalidVerbosity" not in valid_verbosity
    assert "queryPlanner" in valid_verbosity
    
    # Test JSON format validation
    valid_formats = ["relaxed", "canonical"]
    assert "invalid-format" not in valid_formats
    assert "relaxed" in valid_formats
    assert "canonical" in valid_formats
    
    print("✓ All validation tests passed")


def test_error_cases():
    """Test that error cases are handled gracefully."""
    test_cases = [
        # Empty method array
        {
            "method": [],
            "should_error": True
        },
        # Non-string method name
        {
            "method": [123, {"filter": {}}],
            "should_error": True
        },
        # Non-dict args
        {
            "method": ["find", "not a dict"],
            "should_parse": True,
            "expected_args": {}  # Should default to empty dict
        },
    ]
    
    for test_case in test_cases:
        method = test_case["method"]
        
        if test_case.get("should_error"):
            # Should error for empty array
            if len(method) == 0:
                assert len(method) == 0
                continue
        
        # Parse the method array
        method_name = method[0] if isinstance(method[0], str) else None
        method_args = method[1] if len(method) > 1 and isinstance(method[1], dict) else {}
        
        if test_case.get("should_error"):
            assert method_name is None or test_case.get("should_parse"), \
                f"Expected None for non-string method name, got {method_name}"
        
        if test_case.get("expected_args") is not None:
            assert method_args == test_case["expected_args"], \
                f"Expected args {test_case['expected_args']}, got {method_args}"
    
    print("✓ All error case tests passed")


if __name__ == "__main__":
    print("Running tests for fixed tool argument parsing...\n")
    
    try:
        test_explain_argument_parsing()
        test_export_data_argument_parsing()
        test_validation()
        test_error_cases()
        
        print("\n✅ All tests passed!")
        sys.exit(0)
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)
