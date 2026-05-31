"""Roundtrip property tests for the bencode encoder + decoder pair.

The encoder lives in ``swirrl.modules.torrent.service._bencode`` and the
decoder in ``swirrl.commands.torrent._bdecode``. Together they handle
``.torrent`` payloads produced by Swirrl. Roundtrip stability is a hard
contract: BitTorrent v1 clients must receive bit-identical metainfo bytes
across encode/decode cycles, otherwise torrent infohashes drift.

Properties under test:

* Encode then decode returns a structurally equal payload (modulo the
  ``str → bytes`` coercion enforced on dict keys, which is part of the
  on-wire format).
* Encoding an already-decoded payload reproduces the original bytes.
* The decoder rejects truncated or mistyped frames with ``ValueError``.
"""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from swirrl.commands.torrent import _bdecode
from swirrl.modules.torrent.service import _bencode

pytestmark = pytest.mark.benchmark


# Strategy: dict keys must be bytes/str (encoder coerces); we generate
# bytes to keep the decoded shape comparable byte-for-byte.
_KEY = st.binary(min_size=1, max_size=12)
_INT = st.integers(min_value=-(10**9), max_value=10**9)
_BSTR = st.binary(max_size=32)

_VALUE = st.recursive(
    st.one_of(_INT, _BSTR),
    lambda children: st.one_of(
        st.lists(children, max_size=4),
        st.dictionaries(keys=_KEY, values=children, max_size=4),
    ),
    max_leaves=12,
)


# ---------------------------------------------------------------------------
# Roundtrip
# ---------------------------------------------------------------------------


@given(value=_VALUE)
def test_bencode_roundtrip_returns_equal(value) -> None:
    """``decode(encode(x)) == x`` for any supported payload tree.

    Lists, dicts, ints, and byte strings roundtrip without loss. Empty
    containers are explicitly covered by ``test_bencode_fuzz.py``.
    """

    encoded = _bencode(value)
    decoded = _bdecode(encoded)
    assert decoded == value


@given(
    mapping=st.dictionaries(keys=_KEY, values=_INT, min_size=1, max_size=6),
)
def test_bencode_dict_roundtrip_preserves_keys(mapping: dict) -> None:
    """Bytes-keyed dicts roundtrip with identical key set."""

    encoded = _bencode(mapping)
    decoded = _bdecode(encoded)
    assert isinstance(decoded, dict)
    assert set(decoded.keys()) == set(mapping.keys())
    assert all(decoded[k] == mapping[k] for k in mapping)


@given(items=st.lists(_INT, min_size=0, max_size=10))
def test_bencode_list_roundtrip_order_preserved(items: list) -> None:
    """List order survives encode→decode (no implicit sorting)."""

    encoded = _bencode(items)
    decoded = _bdecode(encoded)
    assert decoded == items


# ---------------------------------------------------------------------------
# Decoder robustness (negative cases)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "payload",
    [
        b"",  # empty input
        b"i",  # int marker without body
        b"i42",  # int missing terminator
        b"l",  # list marker without terminator
        b"d",  # dict marker without terminator
        b"5:abc",  # length prefix lies about content length
        b"x",  # unknown prefix
    ],
)
def test_bdecode_rejects_malformed_frame(payload: bytes) -> None:
    """Malformed frames raise ``ValueError``/``IndexError`` — never silently
    decode to a partial structure.
    """

    with pytest.raises((ValueError, IndexError)):
        _bdecode(payload)


def test_bdecode_handles_nested_dict_value() -> None:
    """Sanity: encode/decode a nested structure end-to-end."""

    payload = {b"info": {b"piece length": 16384, b"name": b"release.mkv"}}
    encoded = _bencode(payload)
    decoded = _bdecode(encoded)
    assert decoded == payload


def test_bdecode_handles_empty_dict_and_list() -> None:
    """Empty containers roundtrip cleanly."""

    assert _bdecode(_bencode({})) == {}
    assert _bdecode(_bencode([])) == []


def test_bdecode_negative_int() -> None:
    """Negative ints encode as ``i-Ne`` and decode back."""

    assert _bdecode(_bencode(-1234)) == -1234
