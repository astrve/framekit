# Ouro Test Suite

This directory contains the comprehensive test suite for Ouro, organized by test type and module.

## 📁 Directory Structure

```
tests/
├── conftest.py              # Base pytest configuration and shared fixtures
├── fixtures/                # Reusable test fixtures
│   ├── conftest.py         # Fixture imports and organization
│   ├── mock_settings.py    # Settings-related fixtures
│   ├── mock_http.py        # HTTP client fixtures
│   ├── mock_batch.py       # Batch module fixtures
│   ├── mock_encoder.py     # Encoder module fixtures
│   ├── mock_upload.py      # Upload module fixtures
│   ├── mock_watch.py       # Watch module fixtures
│   ├── sample_media.py     # Sample media file fixtures
│   └── temp_files.py       # Temporary file management fixtures
├── unit/                    # Unit tests (fast, isolated)
│   ├── core/               # Core module tests
│   │   ├── test_settings.py
│   │   ├── test_http.py
│   │   └── test_diagnostics.py
│   └── modules/            # Feature module tests
│       ├── test_batch.py
│       ├── test_encoder.py
│       ├── test_upload.py
│       └── test_watch.py
├── integration/             # Integration tests (multiple components)
└── e2e/                     # End-to-end tests (full workflows)
```

## 🚀 Running Tests

### Run All Tests
```bash
pytest
```

### Run by Test Type
```bash
# Unit tests only (fast)
pytest -m unit

# Integration tests
pytest -m integration

# End-to-end tests
pytest -m e2e
```

### Run by Module
```bash
# Core modules
pytest tests/unit/core/

# Specific module
pytest tests/unit/core/test_settings.py

# Feature modules
pytest tests/unit/modules/
pytest tests/unit/modules/test_batch.py
```

### Run with Coverage
```bash
# Generate coverage report
pytest --cov=src/ouro --cov-report=html

# View coverage in browser
# Open htmlcov/index.html
```

### Run Specific Tests
```bash
# By test name pattern
pytest -k "test_settings"

# By marker
pytest -m "settings and unit"

# Verbose output
pytest -v

# Stop on first failure
pytest -x
```

## 🏷️ Test Markers

Tests are categorized using pytest markers:

- `@pytest.mark.unit` - Unit tests (fast, isolated, no external dependencies)
- `@pytest.mark.integration` - Integration tests (multiple components)
- `@pytest.mark.e2e` - End-to-end tests (full workflows)
- `@pytest.mark.slow` - Tests that take significant time
- `@pytest.mark.network` - Tests requiring network access
- `@pytest.mark.filesystem` - Tests requiring filesystem operations
- `@pytest.mark.settings` - Settings module tests
- `@pytest.mark.http` - HTTP client tests
- `@pytest.mark.diagnostics` - Diagnostics module tests
- `@pytest.mark.core` - Core module tests
- `@pytest.mark.modules` - Feature module tests

### Using Markers
```python
@pytest.mark.unit
@pytest.mark.settings
def test_settings_load():
    """Test settings loading."""
    pass
```

## 🔧 Fixtures

### Base Fixtures (conftest.py)

#### Environment & Isolation
- `isolated_env` - Clean environment with isolated temp directories
- `tmp_path` - Pytest built-in temporary directory
- `tmp_path_factory_session` - Session-scoped temp directory

#### Settings
- `mock_settings_data` - Minimal valid settings dictionary
- `mock_settings` - Mock Settings object (from fixtures/mock_settings.py)

#### HTTP
- `mock_http_response` - Mock HTTP response object
- `mock_http_client` - Mock HTTP client (from fixtures/mock_http.py)

#### Media Files
- `sample_video_path` - Sample video file path
- `mock_mediainfo` - Mock MediaInfo object

#### Utilities
- `mock_sleep` - Mock time.sleep for faster tests
- `capture_logs` - Capture diagnostic logs to file
- `reset_diagnostics_state` - Auto-reset diagnostics between tests

### Module-Specific Fixtures

Located in `tests/fixtures/`:
- **mock_batch.py** - Batch processing fixtures
- **mock_encoder.py** - Encoder module fixtures
- **mock_upload.py** - Upload module fixtures
- **mock_watch.py** - Watch mode fixtures

## 📊 Coverage Targets

### Current Coverage Goals

| Module | Target | Priority |
|--------|--------|----------|
| core.settings | 90%+ | High |
| core.http | 85%+ | High |
| core.diagnostics | 85%+ | High |
| modules.batch | 80%+ | Medium |
| modules.encoder | 80%+ | Medium |
| modules.upload | 75%+ | Medium |
| modules.watch | 75%+ | Medium |

### Viewing Coverage
```bash
# Generate HTML report
pytest --cov=src/ouro --cov-report=html

# Terminal report with missing lines
pytest --cov=src/ouro --cov-report=term-missing

# JSON report for CI/CD
pytest --cov=src/ouro --cov-report=json
```

## ✍️ Writing New Tests

### Test File Naming
- Unit tests: `test_<module_name>.py`
- Integration tests: `test_<feature>_integration.py`
- E2E tests: `test_<workflow>_e2e.py`

### Test Function Naming
```python
def test_<what_is_being_tested>_<expected_behavior>():
    """Clear description of what the test validates."""
    pass
```

### Test Structure (AAA Pattern)
```python
@pytest.mark.unit
@pytest.mark.settings
def test_settings_load_valid_file(tmp_path, mock_settings_data):
    """Test that settings load correctly from a valid YAML file."""
    # Arrange - Set up test data and conditions
    settings_file = tmp_path / "ouro.yaml"
    settings_file.write_text(yaml.dump(mock_settings_data))
    
    # Act - Execute the code being tested
    store = SettingsStore(settings_file)
    settings = store.load()
    
    # Assert - Verify the expected outcome
    assert settings["schema_version"] == 1
    assert settings["general"]["ui_locale"] == "en"
```

### Using Fixtures
```python
@pytest.mark.unit
def test_with_fixtures(isolated_env, mock_settings, tmp_path):
    """Test using multiple fixtures."""
    # Fixtures are automatically provided by pytest
    assert "OURO_CACHE_DIR" in isolated_env
    assert mock_settings.get("general.ui_locale") == "en"
    assert tmp_path.exists()
```

### Parametrized Tests
```python
@pytest.mark.unit
@pytest.mark.parametrize("input_value,expected", [
    ("en", "en"),
    ("en-US", "en"),
    ("fr", "fr"),
    ("invalid", "en"),  # Falls back to default
])
def test_locale_normalization(input_value, expected):
    """Test locale normalization with various inputs."""
    result = normalize_ui_locale(input_value)
    assert result == expected
```

### Mocking External Dependencies
```python
from unittest.mock import Mock, patch

@pytest.mark.unit
def test_with_mocking(monkeypatch):
    """Test with mocked external calls."""
    # Mock a function
    mock_func = Mock(return_value="mocked_result")
    monkeypatch.setattr("module.function", mock_func)
    
    # Test code that calls the mocked function
    result = some_function_that_calls_external()
    
    # Verify mock was called correctly
    mock_func.assert_called_once()
    assert result == "mocked_result"
```

## 🎯 Common Testing Patterns

### Testing Exceptions
```python
@pytest.mark.unit
def test_invalid_input_raises_error():
    """Test that invalid input raises appropriate error."""
    with pytest.raises(ValueError, match="Invalid input"):
        function_that_should_raise("invalid")
```

### Testing File Operations
```python
@pytest.mark.unit
@pytest.mark.filesystem
def test_file_creation(tmp_path):
    """Test file creation and content."""
    output_file = tmp_path / "output.txt"
    
    write_file(output_file, "test content")
    
    assert output_file.exists()
    assert output_file.read_text() == "test content"
```

### Testing Async Code
```python
@pytest.mark.unit
@pytest.mark.asyncio
async def test_async_function():
    """Test asynchronous function."""
    result = await async_function()
    assert result == expected_value
```

### Testing with Temporary Environment Variables
```python
@pytest.mark.unit
def test_with_env_var(monkeypatch):
    """Test behavior with specific environment variable."""
    monkeypatch.setenv("OURO_DEBUG", "true")
    
    result = function_that_checks_env()
    
    assert result is True
```

## 🔍 Debugging Tests

### Run with Verbose Output
```bash
pytest -vv
```

### Show Print Statements
```bash
pytest -s
```

### Drop into Debugger on Failure
```bash
pytest --pdb
```

### Run Last Failed Tests
```bash
pytest --lf
```

### Show Slowest Tests
```bash
pytest --durations=10
```

## 📝 Best Practices

1. **Keep tests isolated** - Each test should be independent
2. **Use descriptive names** - Test names should explain what they test
3. **Follow AAA pattern** - Arrange, Act, Assert
4. **One assertion per test** - Or closely related assertions
5. **Use fixtures** - Reuse common setup code
6. **Mark tests appropriately** - Use markers for categorization
7. **Mock external dependencies** - Keep tests fast and reliable
8. **Test edge cases** - Not just happy paths
9. **Keep tests fast** - Unit tests should run in milliseconds
10. **Document complex tests** - Add docstrings explaining why

## 🚨 Continuous Integration

Tests run automatically on:
- Pull requests
- Commits to main branch
- Scheduled nightly builds

CI configuration is in `.github/workflows/`.

## 📚 Additional Resources

- [pytest Documentation](https://docs.pytest.org/)
- [pytest Fixtures](https://docs.pytest.org/en/stable/fixture.html)
- [pytest Markers](https://docs.pytest.org/en/stable/mark.html)
- [Coverage.py](https://coverage.readthedocs.io/)

## 🤝 Contributing

When adding new features:
1. Write tests first (TDD approach recommended)
2. Ensure all tests pass: `pytest`
3. Check coverage: `pytest --cov`
4. Add appropriate markers
5. Update this README if adding new patterns

---
