"""Property-based tests for common/shared components.

These tests generate random inputs to verify invariants hold across
a wide range of values, helping discover edge cases that might be
missed by example-based tests.
"""

from __future__ import annotations

from typing import Any

from hypothesis import given
from hypothesis import strategies as st

from capnweb.error import ErrorCode, RpcError

# Property tests for RpcError


class TestRpcErrorProperties:
    """Property-based tests for RpcError factory methods."""

    @given(st.text(min_size=1, max_size=200))
    def test_not_found_error_has_correct_code(self, message: str) -> None:
        """not_found() factory should create NOT_FOUND errors."""
        error = RpcError.not_found(message)
        assert error.code == ErrorCode.NOT_FOUND
        assert error.message == message

    @given(st.text(min_size=1, max_size=200))
    def test_bad_request_error_has_correct_code(self, message: str) -> None:
        """bad_request() factory should create BAD_REQUEST errors."""
        error = RpcError.bad_request(message)
        assert error.code == ErrorCode.BAD_REQUEST
        assert error.message == message

    @given(st.text(min_size=1, max_size=200))
    def test_internal_error_has_correct_code(self, message: str) -> None:
        """internal() factory should create INTERNAL errors."""
        error = RpcError.internal(message)
        assert error.code == ErrorCode.INTERNAL
        assert error.message == message

    @given(
        st.sampled_from(list(ErrorCode)),
        st.text(min_size=1, max_size=200),
    )
    def test_error_code_is_preserved(self, code: ErrorCode, message: str) -> None:
        """Error codes should be preserved in RpcError."""
        error = RpcError(code, message)
        assert error.code == code
        assert error.message == message

    @given(
        st.text(min_size=1, max_size=200),
        st.dictionaries(
            st.text(min_size=1, max_size=20),
            st.one_of(st.integers(), st.text(max_size=50), st.booleans()),  # type: ignore[arg-type]
            min_size=0,
            max_size=5,
        ),
    )
    def test_error_data_is_preserved(self, message: str, data: dict[str, Any]) -> None:
        """Custom error data should be preserved."""
        error = RpcError(ErrorCode.INTERNAL, message, data=data)
        assert error.data == data

    @given(
        st.sampled_from(list(ErrorCode)),
        st.text(min_size=1, max_size=200),
    )
    def test_error_is_exception(self, code: ErrorCode, message: str) -> None:
        """RpcError should be a proper exception."""
        error = RpcError(code, message)
        assert isinstance(error, Exception)
        assert str(error) == f"{code}: {message}"
