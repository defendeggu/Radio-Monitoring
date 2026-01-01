#!/usr/bin/env python3
"""
Quick test for path validation security fix
"""
import os
import sys

# Standalone copy of validate_file_path for testing
def validate_file_path(file_path: str, base_dir: str = './recordings') -> str:
    """
    Validate file path to prevent path traversal attacks

    Args:
        file_path: User-provided file path
        base_dir: Base directory to restrict access to

    Returns:
        Validated absolute file path

    Raises:
        ValueError: If path attempts to escape base directory
    """
    # Convert to absolute paths
    base_dir_abs = os.path.abspath(base_dir)

    # Handle both absolute and relative paths from user
    if os.path.isabs(file_path):
        # If user provides absolute path, check if it's within base_dir
        file_path_abs = os.path.abspath(file_path)
    else:
        # If relative, join with base_dir
        file_path_abs = os.path.abspath(os.path.join(base_dir_abs, file_path))

    # Ensure the resolved path is within base_dir
    try:
        common_path = os.path.commonpath([base_dir_abs, file_path_abs])
    except ValueError:
        # Paths on different drives on Windows
        raise ValueError(f"Invalid file path: path traversal detected")

    if common_path != base_dir_abs:
        raise ValueError(f"Invalid file path: access denied outside {base_dir}")

    return file_path_abs

def test_path_validation():
    """Test path validation against various attacks"""

    test_cases = [
        # (input, should_succeed, description)
        ("test.wav", True, "Simple filename"),
        ("subdir/test.wav", True, "Subdirectory"),
        ("../etc/passwd", False, "Path traversal with ../"),
        ("../../etc/passwd", False, "Double path traversal"),
        ("/etc/passwd", False, "Absolute path outside base"),
        ("./recordings/../../../etc/passwd", False, "Complex traversal"),
        ("recordings/test.wav", True, "Explicit recordings dir"),
    ]

    print("Testing path validation...")
    print("=" * 60)

    passed = 0
    failed = 0

    for test_input, should_succeed, description in test_cases:
        try:
            result = validate_file_path(test_input)
            if should_succeed:
                print(f"✅ PASS: {description}")
                print(f"   Input: {test_input}")
                print(f"   Result: {result}")
                passed += 1
            else:
                print(f"❌ FAIL: {description}")
                print(f"   Input: {test_input}")
                print(f"   Expected: ValueError, Got: {result}")
                failed += 1
        except ValueError as e:
            if not should_succeed:
                print(f"✅ PASS: {description}")
                print(f"   Input: {test_input}")
                print(f"   Blocked: {e}")
                passed += 1
            else:
                print(f"❌ FAIL: {description}")
                print(f"   Input: {test_input}")
                print(f"   Expected: Success, Got: {e}")
                failed += 1
        print()

    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed")

    return failed == 0

if __name__ == '__main__':
    success = test_path_validation()
    sys.exit(0 if success else 1)
