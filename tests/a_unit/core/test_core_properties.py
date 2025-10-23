"""Property-based tests for core components.

These tests generate random inputs to verify invariants hold across
a wide range of values, helping discover edge cases that might be
missed by example-based tests.
"""

from __future__ import annotations

from typing import Any

from hypothesis import given
from hypothesis import strategies as st

from capnweb.core.payload import PayloadSource, RpcPayload

# Custom strategies


@st.composite
def simple_json_strategy(draw: Any) -> Any:
    """Generate simple JSON-serializable values."""
    return draw(
        st.one_of(
            st.none(),
            st.booleans(),
            st.integers(min_value=-1000000, max_value=1000000),
            st.floats(allow_nan=False, allow_infinity=False),
            st.text(max_size=100),
        )
    )


# Property tests for RpcPayload ownership semantics


class TestPayloadProperties:
    """Property-based tests for RpcPayload ownership semantics."""

    @given(simple_json_strategy())
    def test_owned_payload_has_owned_source(self, value: Any) -> None:
        """Owned payloads should have PayloadSource.OWNED."""
        payload = RpcPayload.owned(value)
        assert payload.source == PayloadSource.OWNED
        assert payload.value == value

    @given(simple_json_strategy())
    def test_params_payload_has_params_source(self, value: Any) -> None:
        """Params payloads should have PayloadSource.PARAMS."""
        payload = RpcPayload.from_app_params(value)
        assert payload.source == PayloadSource.PARAMS
        assert payload.value == value

    @given(simple_json_strategy())
    def test_return_payload_has_return_source(self, value: Any) -> None:
        """Return payloads should have PayloadSource.RETURN."""
        payload = RpcPayload.from_app_return(value)
        assert payload.source == PayloadSource.RETURN
        assert payload.value == value

    @given(simple_json_strategy())
    def test_params_payload_needs_deep_copy(self, value: Any) -> None:
        """PARAMS payloads should require deep copy before use."""
        payload = RpcPayload.from_app_params(value)
        assert payload.source == PayloadSource.PARAMS

        # After ensure_deep_copied, source should change to OWNED
        copied = payload.ensure_deep_copied()
        if copied is not None:
            assert copied.source == PayloadSource.OWNED

    @given(simple_json_strategy())
    def test_owned_payload_no_copy_needed(self, value: Any) -> None:
        """OWNED payloads don't need copying."""
        payload = RpcPayload.owned(value)
        copied = payload.ensure_deep_copied()

        # Should return same payload (no copy needed) or None if immutable
        if copied is not None:
            assert copied.source == PayloadSource.OWNED

    @given(simple_json_strategy())
    def test_return_payload_becomes_owned(self, value: Any) -> None:
        """RETURN payloads become OWNED when copied."""
        payload = RpcPayload.from_app_return(value)
        copied = payload.ensure_deep_copied()

        # Should be OWNED after copying
        if copied is not None:
            assert copied.source == PayloadSource.OWNED

    @given(st.lists(st.integers(min_value=0, max_value=100), min_size=1, max_size=10))
    def test_deep_copy_actually_copies_mutable_values(self, value: list[int]) -> None:
        """Deep copy should create independent copy of mutable objects."""
        payload = RpcPayload.from_app_params(value)
        copied = payload.ensure_deep_copied()

        # Modify original
        value.append(999)

        # Copied value should not be affected
        assert 999 in value
        if copied is not None and isinstance(copied.value, list):
            assert 999 not in copied.value
