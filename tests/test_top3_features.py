"""Tests for top 3 features: prez refactor, upload rate limiting, unified selector."""

from __future__ import annotations

import threading
import time
from unittest.mock import patch


class TestPrezSubtitleDedup:
    """Tests for prez subtitle deduplication and variant column."""

    def test_subtitle_table_has_variant_column(self):
        """Test that BBCode subtitle table includes Variant column."""
        from framekit.modules.prez.models import PrezTrack
        from framekit.modules.prez.service import _render_subtitle_tracks_bbcode

        tracks = [
            PrezTrack(
                language="French",
                language_code="fr",
                flag_url="https://flagcdn.com/20x15/fr.png",
                codec="SRT",
                channels="-",
                bitrate="-",
                variant="Full",
                format_name="SRT",
                is_default="No",
                is_forced="No",
            ),
            PrezTrack(
                language="English (E09)",
                language_code="en",
                flag_url="https://flagcdn.com/20x15/gb.png",
                codec="SRT",
                channels="-",
                bitrate="-",
                variant="SDH",
                format_name="SRT",
                is_default="No",
                is_forced="No",
            ),
        ]

        result = _render_subtitle_tracks_bbcode(tracks)

        assert "Variant" in result or "variant" in result.lower()
        assert "French[/td][td]Full" in result
        assert "English (E09)[/td][td]SDH" in result
        assert result.count("French[/td][td]Full") == 1

    def test_empty_subtitle_table_renders(self):
        """Test empty subtitle table has correct column count."""
        from framekit.modules.prez.service import _render_subtitle_tracks_bbcode

        result = _render_subtitle_tracks_bbcode([])
        # 6 columns: Track, Language, Variant, Format, Default, Forced
        assert result.count("[td]-[/td]") == 6


class TestUploadRateLimiter:
    """Tests for per-tracker upload rate limiting."""

    def test_tracker_config_has_rate_limit_fields(self):
        """Test TrackerConfig includes rate limit configuration."""
        from framekit.modules.upload.models import TrackerConfig

        config = TrackerConfig(
            name="test",
            type="unit3d",
            url="https://example.com",
            api_key="key",
            rate_limit_requests=5,
            rate_limit_period=30,
        )

        assert config.rate_limit_requests == 5
        assert config.rate_limit_period == 30

    def test_tracker_config_default_rate_limits(self):
        """Test TrackerConfig has sensible default rate limits."""
        from framekit.modules.upload.models import TrackerConfig

        config = TrackerConfig(
            name="test",
            type="unit3d",
            url="https://example.com",
            api_key="key",
        )

        assert config.rate_limit_requests == 10
        assert config.rate_limit_period == 60

    def test_token_bucket_acquire(self):
        """Test token bucket basic acquire/exhaust behavior."""
        from framekit.modules.upload.rate_limiter import _TokenBucket

        bucket = _TokenBucket(capacity=3, period=60.0)

        # Should acquire 3 tokens immediately
        assert bucket.try_acquire()
        assert bucket.try_acquire()
        assert bucket.try_acquire()
        # 4th should fail (exhausted)
        assert not bucket.try_acquire()

    def test_token_bucket_refill(self):
        """Test token bucket refills over time."""
        from framekit.modules.upload.rate_limiter import _TokenBucket

        bucket = _TokenBucket(capacity=1, period=0.1)

        assert bucket.try_acquire()
        assert not bucket.try_acquire()

        # Wait for refill
        time.sleep(0.15)
        assert bucket.try_acquire()

    def test_registry_creates_per_tracker_limiter(self):
        """Test registry creates separate limiters per tracker."""
        from framekit.modules.upload.models import TrackerConfig
        from framekit.modules.upload.rate_limiter import TrackerRateLimiterRegistry

        registry = TrackerRateLimiterRegistry()

        config_a = TrackerConfig(
            name="tracker_a",
            type="unit3d",
            url="https://a.com",
            api_key="k",
            rate_limit_requests=5,
            rate_limit_period=60,
        )
        config_b = TrackerConfig(
            name="tracker_b",
            type="unit3d",
            url="https://b.com",
            api_key="k",
            rate_limit_requests=10,
            rate_limit_period=60,
        )

        limiter_a = registry.get_limiter(config_a)
        limiter_b = registry.get_limiter(config_b)

        assert limiter_a is not limiter_b
        # Same tracker returns same limiter
        assert registry.get_limiter(config_a) is limiter_a

    def test_registry_thread_safety(self):
        """Test registry is thread-safe under concurrent access."""
        from framekit.modules.upload.models import TrackerConfig
        from framekit.modules.upload.rate_limiter import TrackerRateLimiterRegistry

        registry = TrackerRateLimiterRegistry()
        config = TrackerConfig(
            name="concurrent",
            type="unit3d",
            url="https://c.com",
            api_key="k",
            rate_limit_requests=100,
            rate_limit_period=60,
        )

        acquired = []

        def worker():
            result = registry.acquire(config, timeout=5.0)
            acquired.append(result)

        threads = [threading.Thread(target=worker) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert all(acquired)
        assert len(acquired) == 20


class TestUnifiedSelector:
    """Tests for unified selector interface."""

    def test_selection_item_creation(self):
        """Test SelectionItem dataclass."""
        from framekit.ui.unified_selector import SelectionItem

        item = SelectionItem(
            value="tmdb",
            label="TMDb",
            description="The Movie Database",
            group="Providers",
        )

        assert item.value == "tmdb"
        assert item.label == "TMDb"
        assert item.group == "Providers"

    def test_selection_result_properties(self):
        """Test SelectionResult helper properties."""
        from framekit.ui.unified_selector import SelectionResult

        empty = SelectionResult()
        assert empty.is_empty
        assert empty.value is None
        assert not empty.cancelled

        cancelled = SelectionResult(cancelled=True)
        assert cancelled.cancelled
        assert not cancelled.is_empty

        with_value = SelectionResult(items=["a", "b"])
        assert with_value.value == "a"
        assert not with_value.is_empty

    def test_headless_fallback_preselected(self):
        """Test headless mode returns preselected item."""
        from framekit.ui.unified_selector import SelectionItem, UnifiedSelector

        selector = UnifiedSelector(
            title="Pick one",
            items=[
                SelectionItem(value="a", label="A"),
                SelectionItem(value="b", label="B", preselected=True),
                SelectionItem(value="c", label="C"),
            ],
        )

        with patch("sys.stdin") as mock_stdin:
            mock_stdin.isatty.return_value = False
            result = selector.select()

        assert not result.cancelled
        assert result.value == "b"

    def test_headless_fallback_default(self):
        """Test headless mode returns explicit default."""
        from framekit.ui.unified_selector import SelectionItem, UnifiedSelector

        selector = UnifiedSelector(
            title="Pick one",
            items=[
                SelectionItem(value="a", label="A"),
                SelectionItem(value="b", label="B"),
            ],
            headless_default="b",
        )

        with patch("sys.stdin") as mock_stdin:
            mock_stdin.isatty.return_value = False
            result = selector.select()

        assert result.value == "b"

    def test_headless_fallback_first_enabled(self):
        """Test headless mode skips disabled items."""
        from framekit.ui.unified_selector import SelectionItem, UnifiedSelector

        selector = UnifiedSelector(
            title="Pick one",
            items=[
                SelectionItem(value="a", label="A", disabled=True),
                SelectionItem(value="b", label="B"),
            ],
        )

        with patch("sys.stdin") as mock_stdin:
            mock_stdin.isatty.return_value = False
            result = selector.select()

        assert result.value == "b"

    def test_build_entries_with_groups(self):
        """Test group dividers are inserted correctly."""
        from framekit.ui.unified_selector import SelectionItem, SelectorDivider, UnifiedSelector

        selector = UnifiedSelector(
            title="test",
            items=[
                SelectionItem(value=1, label="One", group="Numbers"),
                SelectionItem(value=2, label="Two", group="Numbers"),
                SelectionItem(value="a", label="Alpha", group="Letters"),
            ],
        )

        entries = selector._build_entries()

        # Should have 2 dividers + 3 options = 5 entries
        assert len(entries) == 5
        assert isinstance(entries[0], SelectorDivider)
        assert entries[0].label == "Numbers"
        assert isinstance(entries[3], SelectorDivider)
        assert entries[3].label == "Letters"

    def test_select_or_default(self):
        """Test select_or_default returns default on headless."""
        from framekit.ui.unified_selector import SelectionItem, UnifiedSelector

        selector = UnifiedSelector(
            title="test",
            items=[SelectionItem(value="x", label="X")],
        )

        with patch("sys.stdin") as mock_stdin:
            mock_stdin.isatty.return_value = False
            result = selector.select_or_default("fallback")

        assert result == "x"

    def test_empty_items_returns_cancelled(self):
        """Test empty item list returns cancelled."""
        from framekit.ui.unified_selector import UnifiedSelector

        selector = UnifiedSelector(title="test", items=[])

        with patch("sys.stdin") as mock_stdin:
            mock_stdin.isatty.return_value = True
            result = selector.select()

        assert result.cancelled
