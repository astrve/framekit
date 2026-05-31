"""Test markers documentation for Swirrl test suite.

This module documents all pytest markers used in the test suite.
Markers help categorize and filter tests for different purposes.

Usage:
    # Run only unit tests
    pytest -m unit

    # Run integration tests
    pytest -m integration

    # Run all tests except slow ones
    pytest -m "not slow"

    # Run network-dependent tests
    pytest -m network

    # Combine markers
    pytest -m "unit and not network"
"""

# Test Category Markers
# =====================

UNIT = """
@pytest.mark.unit
Fast, isolated unit tests that test individual functions or classes.
- No external dependencies
- No network access
- No filesystem operations (or minimal mocking)
- Execution time: < 1 second per test
- Should make up the majority of the test suite

Example:
    @pytest.mark.unit
    def test_parse_filename():
        result = parse_filename("Movie.2024.1080p.mkv")
        assert result["year"] == 2024
"""

INTEGRATION = """
@pytest.mark.integration
Integration tests that verify multiple components work together.
- May use real filesystem operations
- May use test databases or caches
- May involve multiple modules
- Execution time: 1-10 seconds per test
- Should verify component interactions

Example:
    @pytest.mark.integration
    def test_pipeline_workflow(tmp_path):
        pipeline = Pipeline(tmp_path)
        result = pipeline.run()
        assert result.success
"""

E2E = """
@pytest.mark.e2e
End-to-end tests that verify complete workflows.
- Test full user scenarios
- Use real external tools (mkvmerge, mediainfo)
- May require network access
- Execution time: 10+ seconds per test
- Should verify complete functionality

Example:
    @pytest.mark.e2e
    def test_full_release_workflow(sample_release):
        result = process_release(sample_release)
        assert result.nfo_created
        assert result.torrent_created
"""

# Performance Markers
# ===================

SLOW = """
@pytest.mark.slow
Tests that take significant time to execute.
- Execution time: > 10 seconds
- Often involves large files or complex operations
- Should be skipped in quick test runs
- Use sparingly

Example:
    @pytest.mark.slow
    def test_large_file_processing():
        process_file("large_movie.mkv")
"""

PERFORMANCE = """
@pytest.mark.performance
Performance and benchmark tests.
- Measure execution time
- Verify performance requirements
- Compare against baselines
- May use pytest-benchmark

Example:
    @pytest.mark.performance
    def test_cache_performance(benchmark):
        result = benchmark(cache.get, "key")
        assert result is not None
"""

# Resource Markers
# ================

NETWORK = """
@pytest.mark.network
Tests requiring network access.
- API calls to external services
- TMDb metadata fetching
- Tracker uploads
- Should be skippable for offline testing

Example:
    @pytest.mark.network
    def test_tmdb_api():
        metadata = fetch_tmdb_metadata("tt1234567")
        assert metadata["title"]
"""

FILESYSTEM = """
@pytest.mark.filesystem
Tests requiring filesystem operations.
- File creation/deletion
- Directory operations
- Should use tmp_path fixture
- Clean up after execution

Example:
    @pytest.mark.filesystem
    def test_file_creation(tmp_path):
        file_path = tmp_path / "test.txt"
        create_file(file_path)
        assert file_path.exists()
"""

# Module Markers
# ==============

CORE = """
@pytest.mark.core
Tests for core framework functionality.
- Configuration management
- Cache system
- Security/encryption
- CLI helpers

Example:
    @pytest.mark.core
    def test_config_loading():
        config = load_config()
        assert config.version
"""

MODULES = """
@pytest.mark.modules
Tests for feature modules.
- CleanMKV
- Renamer
- Metadata
- NFO
- Prez
- Torrent
- Encoder
- Upload
- Watch

Example:
    @pytest.mark.modules
    def test_cleanmkv_remux():
        result = cleanmkv.remux("input.mkv")
        assert result.success
"""

SETTINGS = """
@pytest.mark.settings
Tests for settings and configuration.
- Settings management
- Validation
- Defaults
- Migration

Example:
    @pytest.mark.settings
    def test_settings_validation():
        settings = Settings(invalid_value=True)
        with pytest.raises(ValidationError):
            settings.validate()
"""

HTTP = """
@pytest.mark.http
Tests for HTTP client functionality.
- HTTP/2 support
- Async operations
- Retry logic
- Error handling

Example:
    @pytest.mark.http
    async def test_http_request():
        response = await http_client.get("https://api.example.com")
        assert response.status_code == 200
"""

DIAGNOSTICS = """
@pytest.mark.diagnostics
Tests for diagnostics and health checks.
- System checks
- Tool detection
- Performance benchmarks
- Error reporting

Example:
    @pytest.mark.diagnostics
    def test_tool_detection():
        result = check_tools()
        assert result.mkvmerge_found
"""

SECURITY = """
@pytest.mark.security
Security-related tests.
- Encryption/decryption
- Credential storage
- Input validation
- Vulnerability checks

Example:
    @pytest.mark.security
    def test_credential_encryption():
        encrypted = encrypt_credential("secret")
        assert encrypted != "secret"
        assert decrypt_credential(encrypted) == "secret"
"""

# Marker Combinations
# ===================

"""
Common marker combinations:

# Fast unit tests only
pytest -m "unit and not slow"

# All tests except network-dependent
pytest -m "not network"

# Integration and E2E tests
pytest -m "integration or e2e"

# Core functionality only
pytest -m "core"

# Module tests excluding slow ones
pytest -m "modules and not slow"

# Security and performance tests
pytest -m "security or performance"
"""

# Best Practices
# ==============

"""
1. Always mark tests appropriately
   - Every test should have at least one category marker (unit/integration/e2e)
   - Add resource markers if applicable (network/filesystem)
   - Add module markers for organization

2. Keep unit tests fast
   - Unit tests should complete in < 1 second
   - Mock external dependencies
   - Use fixtures for setup

3. Use parametrize for variations
   - Test multiple inputs with @pytest.mark.parametrize
   - Reduces code duplication
   - Makes test intent clearer

4. Document complex tests
   - Add docstrings explaining what is tested
   - Include expected behavior
   - Note any special requirements

5. Clean up resources
   - Use fixtures with cleanup
   - Use tmp_path for file operations
   - Close connections properly

Example of well-marked test:
    @pytest.mark.unit
    @pytest.mark.core
    def test_cache_key_generation():
        '''Test that cache keys are generated correctly.
        
        Cache keys should be deterministic and include all
        relevant parameters to avoid collisions.
        '''
        key1 = generate_cache_key("movie", year=2024)
        key2 = generate_cache_key("movie", year=2024)
        key3 = generate_cache_key("movie", year=2023)
        
        assert key1 == key2
        assert key1 != key3
"""
