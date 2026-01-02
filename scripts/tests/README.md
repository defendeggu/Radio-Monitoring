# Test Scripts

Manual test scripts for specific features and edge cases.

## Scripts

### API Security Tests
- **`test_path_validation.py`** - Tests path validation and security
  - Validates file path sanitization
  - Tests for directory traversal vulnerabilities
  - Ensures safe file operations

### Session Management Tests
- **`test_session_cleanup.py`** - Tests session cleanup logic
  - Verifies orphaned session cleanup
  - Tests Redis session expiration
  - Validates session state transitions

### Concurrency Tests
- **`test_thread_management.py`** - Tests thread management
  - Validates concurrent streaming sessions
  - Tests thread safety and locks
  - Checks for race conditions

## Running Tests

These are standalone test scripts. Run them individually:

```bash
python scripts/tests/test_path_validation.py
python scripts/tests/test_session_cleanup.py
python scripts/tests/test_thread_management.py
```

## Automated Tests

For the full test suite using pytest:

```bash
./scripts/run_tests.sh      # Run all unit tests
./scripts/run_coverage.sh   # Run with coverage report
./scripts/run_mypy.sh        # Type checking
```

---

Last updated: 2026-01-02
