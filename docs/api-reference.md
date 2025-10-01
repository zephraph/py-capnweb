# API Reference

Complete reference for all public APIs in Cap'n Web Python.

## Table of Contents

- [Client](#client)
- [Server](#server)
- [RPC Targets](#rpc-targets)
- [Capabilities](#capabilities)
- [Errors](#errors)
- [Pipelining](#pipelining)
- [Transports](#transports)

## Client

### ClientConfig

Configuration for the RPC client.

```python
@dataclass(frozen=True)
class ClientConfig:
    url: str                     # Server URL (http:// or ws://)
    timeout: float = 30.0        # Request timeout in seconds
    max_retries: int = 3         # Max retry attempts
    retry_delay: float = 1.0     # Delay between retries
```

**Example:**
```python
config = ClientConfig(
    url="http://localhost:8080/rpc/batch",
    timeout=10.0,
    max_retries=5
)
```

### Client

Main client class for making RPC calls.

```python
class Client(RpcSession):
    def __init__(self, config: ClientConfig)
```

#### Methods

##### `async call(capability_id: int, method: str, args: list) -> Any`

Make a single RPC call.

**Parameters:**
- `capability_id`: ID of the capability to call (usually 0 for root)
- `method`: Name of the method to call
- `args`: List of arguments to pass

**Returns:** The method's return value

**Raises:** `RpcError` on failure

**Example:**
```python
async with Client(config) as client:
    result = await client.call(0, "add", [5, 3])
    print(result)  # 8
```

##### `async close() -> None`

Close the client and clean up resources.

**Example:**
```python
client = Client(config)
try:
    result = await client.call(0, "method", [])
finally:
    await client.close()
```

##### Context Manager Support

```python
async with Client(config) as client:
    # Client automatically closed on exit
    result = await client.call(0, "method", [])
```

## Server

### ServerConfig

Configuration for the RPC server.

```python
@dataclass(frozen=True)
class ServerConfig:
    host: str = "127.0.0.1"              # Listen address
    port: int = 8080                     # Listen port
    max_batch_size: int = 100            # Max messages per batch
    include_stack_traces: bool = False   # Include stack traces (dev only!)
    resume_token_ttl: float = 3600.0     # Token TTL in seconds
```

**Security Note:** Never set `include_stack_traces=True` in production!

**Example:**
```python
config = ServerConfig(
    host="0.0.0.0",  # Listen on all interfaces
    port=8080,
    max_batch_size=200
)
```

### Server

Main server class for hosting RPC services.

```python
class Server(RpcSession):
    def __init__(self, config: ServerConfig)
```

#### Methods

##### `register_capability(export_id: int, target: RpcTarget) -> None`

Register a local object as a capability.

**Parameters:**
- `export_id`: ID to assign (usually 0 for root capability)
- `target`: Object implementing `RpcTarget` protocol

**Example:**
```python
server = Server(config)
server.register_capability(0, MyService())
```

##### `async start() -> None`

Start the server.

**Example:**
```python
server = Server(config)
server.register_capability(0, service)
await server.start()
```

##### `async stop() -> None`

Stop the server gracefully.

##### Context Manager Support

```python
async with Server(config) as server:
    server.register_capability(0, service)
    # Server automatically started and stopped
    await asyncio.Event().wait()
```

## RPC Targets

### RpcTarget Protocol

Protocol for objects that can be exposed as RPC capabilities.

```python
class RpcTarget(Protocol):
    async def call(self, method: str, args: list) -> Any:
        """Handle method calls."""

    async def get_property(self, property: str) -> Any:
        """Handle property access."""
```

#### Implementation Example

```python
class Calculator(RpcTarget):
    async def call(self, method: str, args: list) -> int:
        match method:
            case "add":
                return args[0] + args[1]
            case "multiply":
                return args[0] * args[1]
            case _:
                raise RpcError.not_found(f"Method {method} not found")

    async def get_property(self, property: str):
        match property:
            case "name":
                return "Calculator"
            case _:
                raise RpcError.not_found(f"Property {property} not found")
```

### Optional: dispose()

If your target needs cleanup, implement a `dispose()` method:

```python
class DatabaseService(RpcTarget):
    def __init__(self, connection):
        self.conn = connection

    async def call(self, method: str, args: list):
        # ... implementation

    async def get_property(self, property: str):
        # ... implementation

    def dispose(self):
        """Called when capability is released."""
        self.conn.close()
```

## Capabilities

### RpcStub

Represents a remote capability (returned from RPC calls).

```python
class RpcStub:
    def __getattr__(self, name: str) -> RpcStub:
        """Access properties."""

    def __call__(self, *args) -> RpcPromise:
        """Call as a function."""
```

**Example:**
```python
user = await client.call(0, "getUser", ["alice"])
name = await user.name           # Property access
greeting = await user.greet()    # Method call
```

#### Methods

##### `dispose() -> None`

Release the capability and clean up resources.

**Example:**
```python
stub = await client.call(0, "getResource", [])
try:
    result = await stub.process()
finally:
    stub.dispose()
```

### RpcPromise

Represents a future value from an RPC call.

```python
class RpcPromise:
    def __await__(self):
        """Make the promise awaitable."""

    def __getattr__(self, name: str) -> RpcPromise:
        """Access properties on the future value."""
```

**Example:**
```python
# Create promise (doesn't block)
promise = stub.getUser("alice")

# Chain operations (still doesn't block)
name_promise = promise.name

# Await to get final value (blocks)
name = await name_promise
```

## Errors

### ErrorCode

Standard error codes.

```python
class ErrorCode(Enum):
    BAD_REQUEST = "bad_request"           # Invalid request
    NOT_FOUND = "not_found"               # Resource not found
    CAP_REVOKED = "cap_revoked"           # Capability revoked
    PERMISSION_DENIED = "permission_denied"  # Access denied
    CANCELED = "canceled"                 # Operation canceled
    INTERNAL = "internal"                 # Internal server error
```

### RpcError

Structured RPC error with error code and optional data.

```python
class RpcError(Exception):
    code: ErrorCode
    message: str
    data: Any | None
```

#### Factory Methods

```python
# Create errors using factory methods
raise RpcError.bad_request("Invalid input")
raise RpcError.not_found("User not found")
raise RpcError.permission_denied("Access denied")
raise RpcError.internal("Database connection failed")

# With custom data
raise RpcError.bad_request(
    "Validation failed",
    data={"field": "email", "reason": "invalid format"}
)
```

#### Handling Errors

```python
try:
    result = await client.call(0, "method", [args])
except RpcError as e:
    match e.code:
        case ErrorCode.NOT_FOUND:
            print(f"Not found: {e.message}")
        case ErrorCode.PERMISSION_DENIED:
            print(f"Access denied: {e.message}")
        case _:
            print(f"Error {e.code}: {e.message}")

    if e.data:
        print(f"Additional data: {e.data}")
```

## Pipelining

### PipelineBatch

Batch multiple RPC calls into a single network round-trip.

```python
class PipelineBatch:
    def __init__(self, client: Client, capability_id: int)
```

#### Methods

##### `call(method: str, args: list) -> PipelinePromise`

Queue a method call (doesn't execute yet).

**Parameters:**
- `method`: Method name to call
- `args`: Arguments to pass

**Returns:** A `PipelinePromise` that can be awaited later

**Example:**
```python
batch = PipelineBatch(client, capability_id=0)
call1 = batch.call("method1", [arg1])
call2 = batch.call("method2", [arg2])
```

##### `async execute() -> None`

Execute all queued calls in a single network request.

**Example:**
```python
batch = PipelineBatch(client, capability_id=0)

# Queue calls
promise1 = batch.call("add", [10, 20])
promise2 = batch.call("multiply", [5, 6])

# Execute batch (single network request)
await batch.execute()

# Get results
result1 = await promise1  # 30
result2 = await promise2  # 30
```

### PipelinePromise

Promise returned by `PipelineBatch.call()`.

```python
class PipelinePromise:
    def __await__(self):
        """Await to get the final result."""

    def __getattr__(self, name: str) -> PipelinePromise:
        """Chain property access."""
```

**Example:**
```python
batch = PipelineBatch(client, 0)

# Queue call and chain property access
user_promise = batch.call("getUser", ["alice"])
name_promise = user_promise.name  # Chained access

# Execute
await batch.execute()

# Get result
name = await name_promise  # "alice"
```

## Transports

### HttpBatchTransport

HTTP-based batch transport (default).

**Features:**
- Simple request/response
- Automatic batching
- Works with any HTTP server

**URL format:** `http://host:port/path` or `https://host:port/path`

**Example:**
```python
config = ClientConfig(url="http://localhost:8080/rpc/batch")
```

### WebSocketTransport

WebSocket-based transport for persistent connections.

**Features:**
- Persistent connection
- Lower latency for multiple calls
- Server can push updates

**URL format:** `ws://host:port/path` or `wss://host:port/path`

**Example:**
```python
config = ClientConfig(url="ws://localhost:8080/rpc/ws")
```

## Utility Classes

### RpcPayload

Wraps data with ownership semantics (internal use).

```python
class RpcPayload:
    @classmethod
    def from_app_params(cls, value: Any) -> RpcPayload:
        """Create from application parameters (will be copied)."""

    @classmethod
    def from_app_return(cls, value: Any) -> RpcPayload:
        """Create from application return value (ownership transferred)."""

    @classmethod
    def owned(cls, value: Any) -> RpcPayload:
        """Create from already-owned data (already copied)."""
```

**Note:** Usually you don't need to work with `RpcPayload` directly - the framework handles it.

## Type Hints

All public APIs are fully type-hinted. For best results, use a type checker:

```bash
# With pyrefly (recommended)
pyrefly check

# With mypy
mypy src/
```

**Example with type hints:**
```python
from capnweb.client import Client, ClientConfig
from capnweb.error import RpcError

async def get_user(client: Client, user_id: str) -> dict[str, Any]:
    """Fetch user data from the server."""
    try:
        user: dict[str, Any] = await client.call(0, "getUser", [user_id])
        return user
    except RpcError as e:
        print(f"Error fetching user: {e}")
        raise
```

## Next Steps

- **[Quickstart Guide](quickstart.md)** - Get started quickly
- **[Architecture Guide](architecture.md)** - Understand the internals
- **[Advanced Topics](advanced.md)** - Resume tokens, bidirectional RPC
