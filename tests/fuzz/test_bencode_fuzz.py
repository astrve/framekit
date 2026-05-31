"""Property tests for :func:`swirrl.modules.torrent.service._bencode`.

Bencode is the BitTorrent v1 payload format. Swirrl emits it when
generating ``.torrent`` files. The encoder must:

* Round-trip any int/bytes/str/list/dict that contains only the supported
  primitive types.
* Sort dict keys in byte order (BTv1 requirement) — verified by encoding
  the same dict with shuffled key order and comparing outputs.
* Raise :class:`TypeError` (not silently corrupt the payload) when fed an
  unsupported type.
"""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from swirrl.modules.torrent.service import _bencode

pytestmark = pytest.mark.benchmark


# Recursive strategy for valid bencode-able trees.
_bencode_leaf = st.one_of(
    st.integers(min_value=-(10**12), max_value=10**12),
    st.binary(max_size=64),
    st.text(
        alphabet=st.characters(
            min_codepoint=0x20,
            max_codepoint=0x7E,
            blacklist_categories=("Cs",),
        ),
        max_size=64,
    ),
)

_bencode_tree = st.recursive(
    _bencode_leaf,
    lambda children: st.one_of(
        st.lists(children, max_size=5),
        st.dictionaries(
            keys=st.text(
                alphabet=st.characters(
                    min_codepoint=0x20,
                    max_codepoint=0x7E,
                    blacklist_categories=("Cs",),
                ),
                min_size=1,
                max_size=16,
            ),
            values=children,
            max_size=5,
        ),
    ),
    max_leaves=20,
)


@given(value=_bencode_tree)
def test_bencode_returns_bytes_for_valid_input(value) -> None:
    """Whatever the tree, ``_bencode`` returns ``bytes``."""

    out = _bencode(value)
    assert isinstance(out, bytes)


@given(value=_bencode_tree)
def test_bencode_starts_with_protocol_byte(value) -> None:
    """First byte identifies type: 'i' (int), digit (str/bytes), 'l' (list), 'd' (dict)."""

    out = _bencode(value)
    assert out[:1] in (b"i", b"l", b"d") or out[:1].isdigit()


@given(items=st.lists(_bencode_leaf, min_size=0, max_size=8))
def test_bencode_list_roundtrip_first_byte(items: list) -> None:
    """A bencoded list always starts with ``b'l'`` and ends with ``b'e'``."""

    out = _bencode(items)
    assert out[:1] == b"l"
    assert out[-1:] == b"e"


@given(
    mapping=st.dictionaries(
        keys=st.text(
            alphabet=st.characters(
                min_codepoint=ord("a"),
                max_codepoint=ord("z"),
            ),
            min_size=1,
            max_size=8,
        ),
        values=_bencode_leaf,
        min_size=1,
        max_size=6,
    )
)
def test_bencode_dict_keys_sorted_byteorder(mapping: dict) -> None:
    """BTv1 mandates byte-sorted keys. Encoding with shuffled order yields the same bytes."""

    shuffled = dict(reversed(list(mapping.items())))
    assert _bencode(mapping) == _bencode(shuffled)


@given(
    bad=st.one_of(
        st.floats(),
        st.complex_numbers(),
    )
)
def test_bencode_rejects_unsupported_types(bad) -> None:
    """Non-supported types must raise ``TypeError`` (not silently encode)."""

    with pytest.raises(TypeError):
        _bencode(bad)


def test_bencode_empty_list() -> None:
    assert _bencode([]) == b"le"


def test_bencode_empty_dict() -> None:
    assert _bencode({}) == b"de"


def test_bencode_zero_int() -> None:
    assert _bencode(0) == b"i0e"


def test_bencode_negative_int() -> None:
    assert _bencode(-42) == b"i-42e"
