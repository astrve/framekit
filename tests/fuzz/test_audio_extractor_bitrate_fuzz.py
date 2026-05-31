"""Property tests for :meth:`swirrl.modules.extract.audio_extractor.AudioExtractor.validate_bitrate`.

Parser contract:

* Accept only ``<digits>k`` in range ``32k..640k``.
* Return original string for valid values.
* Raise :class:`ValueError` for malformed/out-of-range values.
"""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from swirrl.modules.extract.audio_extractor import AudioExtractor

pytestmark = pytest.mark.benchmark


class _FakeRegistry:
    def resolve_tool_path(self, _name: str) -> str:
        return "ffmpeg"


_extractor = AudioExtractor(_FakeRegistry())


@given(value=st.integers(min_value=32, max_value=640))
def test_validate_bitrate_accepts_range(value: int) -> None:
    bitrate = f"{value}k"
    assert _extractor.validate_bitrate(bitrate) == bitrate


@given(value=st.one_of(st.integers(max_value=31), st.integers(min_value=641, max_value=10000)))
def test_validate_bitrate_rejects_out_of_range(value: int) -> None:
    with pytest.raises(ValueError):
        _extractor.validate_bitrate(f"{value}k")


@given(
    raw=st.one_of(
        st.just(""),
        st.just(" "),
        st.text(
            alphabet=st.characters(
                min_codepoint=ord("a"),
                max_codepoint=ord("z"),
            ),
            min_size=1,
            max_size=12,
        ),
        st.integers(min_value=0, max_value=9999).map(lambda n: f"{n}"),
        st.integers(min_value=0, max_value=9999).map(lambda n: f"{n}K"),
        st.integers(min_value=0, max_value=9999).map(lambda n: f"{n}kk"),
        st.integers(min_value=0, max_value=9999).map(lambda n: f"{n}.5k"),
    )
)
def test_validate_bitrate_rejects_malformed(raw: str) -> None:
    with pytest.raises(ValueError):
        _extractor.validate_bitrate(raw)
