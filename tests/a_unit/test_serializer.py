"""Tests for Serializer - Python object to wire format conversion."""

from capnweb.error import ErrorCode, RpcError
from capnweb.hooks import PayloadStubHook
from capnweb.payload import RpcPayload
from capnweb.serializer import Serializer
from capnweb.session import RpcSession
from capnweb.stubs import RpcPromise, RpcStub


class TestSerializerPrimitives:
    """Test serialization of primitive types."""

    def test_serialize_none(self):
        """Test serializing None."""
        session = RpcSession()
        serializer = Serializer(exporter=session)

        result = serializer.serialize(None)
        assert result is None

    def test_serialize_bool(self):
        """Test serializing booleans."""
        session = RpcSession()
        serializer = Serializer(exporter=session)

        assert serializer.serialize(True) is True
        assert serializer.serialize(False) is False

    def test_serialize_int(self):
        """Test serializing integers."""
        session = RpcSession()
        serializer = Serializer(exporter=session)

        assert serializer.serialize(42) == 42
        assert serializer.serialize(0) == 0
        assert serializer.serialize(-123) == -123

    def test_serialize_float(self):
        """Test serializing floats."""
        session = RpcSession()
        serializer = Serializer(exporter=session)

        assert serializer.serialize(3.14) == 3.14
        assert serializer.serialize(0.0) == 0.0
        assert serializer.serialize(-2.5) == -2.5

    def test_serialize_string(self):
        """Test serializing strings."""
        session = RpcSession()
        serializer = Serializer(exporter=session)

        assert serializer.serialize("hello") == "hello"
        assert serializer.serialize("") == ""
        assert serializer.serialize("unicode: 你好") == "unicode: 你好"


class TestSerializerCollections:
    """Test serialization of collections."""

    def test_serialize_list(self):
        """Test serializing lists."""
        session = RpcSession()
        serializer = Serializer(exporter=session)

        result = serializer.serialize([1, 2, 3])
        assert result == [1, 2, 3]

    def test_serialize_nested_list(self):
        """Test serializing nested lists."""
        session = RpcSession()
        serializer = Serializer(exporter=session)

        result = serializer.serialize([[1, 2], [3, 4], [5]])
        assert result == [[1, 2], [3, 4], [5]]

    def test_serialize_dict(self):
        """Test serializing dictionaries."""
        session = RpcSession()
        serializer = Serializer(exporter=session)

        result = serializer.serialize({"name": "Alice", "age": 30})
        assert result == {"name": "Alice", "age": 30}

    def test_serialize_nested_dict(self):
        """Test serializing nested dictionaries."""
        session = RpcSession()
        serializer = Serializer(exporter=session)

        data = {"user": {"id": 123, "profile": {"name": "Bob"}}}
        result = serializer.serialize(data)
        assert result == data

    def test_serialize_mixed_structures(self):
        """Test serializing mixed nested structures."""
        session = RpcSession()
        serializer = Serializer(exporter=session)

        data = {"users": [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]}
        result = serializer.serialize(data)
        assert result == data


class TestSerializeRpcStub:
    """Test serialization of RpcStub objects."""

    def test_serialize_stub(self):
        """Test serializing an RpcStub."""
        session = RpcSession()
        serializer = Serializer(exporter=session)

        payload = RpcPayload.owned({"test": "data"})
        hook = PayloadStubHook(payload)
        stub = RpcStub(hook)

        result = serializer.serialize(stub)

        # Should be ["export", id]
        assert isinstance(result, list)
        assert result[0] == "export"
        assert isinstance(result[1], int)
        assert result[1] in session._exports

    def test_serialize_stub_in_list(self):
        """Test serializing stub nested in a list."""
        session = RpcSession()
        serializer = Serializer(exporter=session)

        payload = RpcPayload.owned({"test": "data"})
        hook = PayloadStubHook(payload)
        stub = RpcStub(hook)

        result = serializer.serialize([stub, "other"])

        assert len(result) == 2
        assert isinstance(result[0], list)
        assert result[0][0] == "export"
        assert result[1] == "other"

    def test_serialize_stub_in_dict(self):
        """Test serializing stub nested in a dict."""
        session = RpcSession()
        serializer = Serializer(exporter=session)

        payload = RpcPayload.owned({"test": "data"})
        hook = PayloadStubHook(payload)
        stub = RpcStub(hook)

        result = serializer.serialize({"cap": stub, "id": 123})

        assert isinstance(result["cap"], list)
        assert result["cap"][0] == "export"
        assert result["id"] == 123


class TestSerializeRpcPromise:
    """Test serialization of RpcPromise objects."""

    def test_serialize_promise(self):
        """Test serializing an RpcPromise."""
        session = RpcSession()
        serializer = Serializer(exporter=session)

        # Create a promise
        hook = session.create_promise_hook(1)
        promise = RpcPromise(hook)

        result = serializer.serialize(promise)

        # Should be ["promise", id]
        assert isinstance(result, list)
        assert result[0] == "promise"
        assert isinstance(result[1], int)

    def test_serialize_promise_in_dict(self):
        """Test serializing promise nested in a dict."""
        session = RpcSession()
        serializer = Serializer(exporter=session)

        hook = session.create_promise_hook(1)
        promise = RpcPromise(hook)

        result = serializer.serialize({"result": promise, "status": "pending"})

        assert isinstance(result["result"], list)
        assert result["result"][0] == "promise"
        assert result["status"] == "pending"


class TestSerializeRpcError:
    """Test serialization of RpcError objects."""

    def test_serialize_error_basic(self):
        """Test serializing a basic error."""
        session = RpcSession()
        serializer = Serializer(exporter=session)

        error = RpcError.not_found("Resource not found")
        result = serializer.serialize(error)

        # Should be ["error", "not_found", "Resource not found", null, null]
        assert isinstance(result, list)
        assert result[0] == "error"
        assert result[1] == "not_found"
        assert result[2] == "Resource not found"

    def test_serialize_error_with_data(self):
        """Test serializing error with custom data."""
        session = RpcSession()
        serializer = Serializer(exporter=session)

        error = RpcError(
            ErrorCode.BAD_REQUEST,
            "Invalid input",
            data={"field": "email", "reason": "invalid"},
        )
        result = serializer.serialize(error)

        assert result[0] == "error"
        assert result[1] == "bad_request"
        assert result[2] == "Invalid input"
        # data should be in position 4
        assert result[4] == {"field": "email", "reason": "invalid"}

    def test_serialize_error_in_dict(self):
        """Test serializing error nested in a dict."""
        session = RpcSession()
        serializer = Serializer(exporter=session)

        error = RpcError.internal("Server error")
        result = serializer.serialize({"success": False, "error": error})

        assert result["success"] is False
        assert isinstance(result["error"], list)
        assert result["error"][0] == "error"
        assert result["error"][1] == "internal"


class TestSerializeRpcPayload:
    """Test serialization of RpcPayload objects."""

    def test_serialize_payload_owned(self):
        """Test serializing an owned payload."""
        session = RpcSession()
        serializer = Serializer(exporter=session)

        payload = RpcPayload.owned({"test": "data"})
        result = serializer.serialize(payload)

        assert result == {"test": "data"}

    def test_serialize_payload_params(self):
        """Test serializing a params payload (triggers deep copy)."""
        session = RpcSession()
        serializer = Serializer(exporter=session)

        original = {"test": "data"}
        payload = RpcPayload.from_app_params([original])
        result = serializer.serialize(payload)

        # Should be deep copied
        assert isinstance(result, list)
        assert result == [original]

    def test_serialize_payload_method(self):
        """Test the serialize_payload convenience method."""
        session = RpcSession()
        serializer = Serializer(exporter=session)

        payload = RpcPayload.owned({"test": "data"})
        result = serializer.serialize_payload(payload)

        assert result == {"test": "data"}


class TestSerializeEdgeCases:
    """Test edge cases and complex scenarios."""

    def test_serialize_empty_list(self):
        """Test serializing an empty list."""
        session = RpcSession()
        serializer = Serializer(exporter=session)

        result = serializer.serialize([])
        assert result == []

    def test_serialize_empty_dict(self):
        """Test serializing an empty dict."""
        session = RpcSession()
        serializer = Serializer(exporter=session)

        result = serializer.serialize({})
        assert result == {}

    def test_serialize_deeply_nested_structure(self):
        """Test serializing deeply nested structures."""
        session = RpcSession()
        serializer = Serializer(exporter=session)

        data = {"level1": {"level2": {"level3": {"level4": {"value": 42}}}}}
        result = serializer.serialize(data)
        assert result == data

    def test_serialize_mixed_stubs_and_data(self):
        """Test serializing mix of stubs, promises, and plain data."""
        session = RpcSession()
        serializer = Serializer(exporter=session)

        payload = RpcPayload.owned({"test": "data"})
        hook = PayloadStubHook(payload)
        stub = RpcStub(hook)

        promise_hook = session.create_promise_hook(1)
        promise = RpcPromise(promise_hook)

        data = {"stub": stub, "promise": promise, "number": 42, "list": [1, 2, 3]}
        result = serializer.serialize(data)

        assert isinstance(result["stub"], list)
        assert result["stub"][0] == "export"
        assert isinstance(result["promise"], list)
        assert result["promise"][0] == "promise"
        assert result["number"] == 42
        assert result["list"] == [1, 2, 3]

    def test_serialize_unknown_type_passthrough(self):
        """Test that unknown types are passed through as-is."""
        session = RpcSession()
        serializer = Serializer(exporter=session)

        # Custom object
        class CustomObject:
            def __init__(self, value):
                self.value = value

        obj = CustomObject(42)
        result = serializer.serialize(obj)

        # Should return the object as-is (will likely fail at JSON encoding)
        assert result is obj
