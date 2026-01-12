# Pull Request Summary

## Title
Fix critical argument parsing bugs in explain and export_data tools

## Type
Bug Fix

## Description

### Problem
The `explain` and `export_data` tools were experiencing runtime errors when called with array-format arguments. The issue occurred because:

1. **Expected format**: The code was trying to parse method/exportTarget as objects with `.get("name")` and `.get("arguments")`
2. **Actual format**: Tools were being called with simple arrays like `["find", {"filter": {}, "limit": 10}]`
3. **Result**: Runtime error: `'str' object has no attribute 'get'`

This made both tools completely non-functional despite having valid input according to their type signatures.

### Solution
Updated the argument parsing logic to correctly handle the array format:
- Parse first element as method/target name (string)
- Parse second element as arguments dictionary (dict)
- Add defensive checks for type validation
- Provide clear error messages for invalid inputs

### Changes Made

#### 1. Core Fixes (1 commit)
- Fixed `explain()` to parse `method` as `[method_name, args_dict]`
- Fixed `export_data()` to parse `exportTarget` as `[target_name, args_dict]`
- Added type checking for array elements

#### 2. Input Validation (included in commit 1)
- Validate `verbosity` parameter in `explain` (queryPlanner, executionStats, allPlansExecution)
- Validate `jsonExportFormat` in `export_data` (relaxed, canonical)
- Clear error messages for invalid parameters

#### 3. Tests (1 commit)
- Unit tests for `explain` argument parsing (4 test cases)
- Unit tests for `export_data` argument parsing (3 test cases)
- Validation tests for all parameters
- Error case handling tests

#### 4. Documentation (3 commits)
- Updated docstrings with explicit format specifications
- Added concrete usage examples in README
- Created CHANGELOG with upgrade notes

### Testing
All unit tests pass:
```bash
$ python tests/test_tool_fixes.py
✓ All explain argument parsing tests passed
✓ All export_data argument parsing tests passed
✓ All validation tests passed
✓ All error case tests passed
All tests passed!
```

### Impact
- **Before**: Both tools were completely broken, throwing errors on any call
- **After**: Both tools work correctly with proper error handling and validation
- **Breaking Changes**: None - the fix aligns with the existing type signatures
- **Backward Compatibility**: Maintained - the array format was always the intended format

### Files Changed
- `src/server.py` - Core bug fixes and validations
- `tests/test_tool_fixes.py` - New unit tests (177 lines)
- `README.md` - Usage examples and documentation
- `CHANGELOG.md` - Release notes and upgrade guide

### Commits
1. `34590c0` - fix: correct argument parsing for explain and export_data tools
2. `24722c5` - test: add unit tests for tool argument parsing fixes
3. `02ad96e` - docs: improve documentation for explain and export_data tools
4. `05832f6` - docs: add usage examples for explain and export_data tools
5. `c6bf28a` - docs: add CHANGELOG documenting bug fixes and improvements

## Related Issues
This addresses the runtime errors discovered during comprehensive tool testing where `explain` and `export_data` were found to be non-functional.

## Checklist
- [x] Code follows project style guidelines
- [x] Tests added for bug fixes
- [x] All tests pass
- [x] Documentation updated
- [x] CHANGELOG updated
- [x] No breaking changes introduced
