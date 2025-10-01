# Cap'n Web Python Implementation

Python implementation of the [Cap'n Web protocol](https://github.com/cloudflare/capnweb), delivering both server and client with support for HTTP batch and WebSocket transports.

## Status: v0.3.1-dev

✅ **Production-ready with comprehensive test coverage**
- 329 tests passing, 85% coverage
- Fully interoperable with TypeScript reference implementation
- Hook-based architecture (legacy code removed)
- ~98% protocol compliance

## Documentation

- **[Quickstart Guide](docs/quickstart.md)** - Get started in 5 minutes
- **[API Reference](docs/api-reference.md)** - Complete API documentation
- **[Architecture Guide](docs/architecture.md)** - Understand the internals
- **[Examples](examples/)** - Working code examples

### What's New in v0.3.1

- **🏗️ Architecture Complete**: Removed all legacy code (evaluator.py, tables.py)
- **📈 Test Coverage**: 67% → 85% coverage (+172 tests, 329 total)
- **✨ 8 Modules at 100% Coverage**: payload, serializer, stubs, error, ids, types, __init__
- **📚 Comprehensive Documentation**: Quickstart guide, architecture guide, API reference
- **🔧 Code Quality**: All linting and type checks passing

### What's New in v0.3.0

- **🎉 Full TypeScript Interoperability**: 100% compatibility with TypeScript reference
- **🔄 Promise Pipelining**: Batch multiple dependent calls into one round-trip
- **📊 Interop Test Suite**: Automated testing across all implementation combinations

## Features

- **Capability-based security**: Unforgeable object references with explicit disposal
- **Promise pipelining**: Batch multiple dependent RPC calls into single round trips
- **Expression evaluation**: Full support for wire expressions including remap (`.map()` operations)
- **Multiple transports**: HTTP batch and WebSocket with pluggable transport abstraction
- **Type-safe**: Full type hints with pyright/mypy compatibility
- **Async/await**: Built on Python's asyncio
- **Error handling**: Structured error model with security-conscious stack trace redaction
- **Reference counting**: Automatic resource management with proper refcounting
- **Resume tokens**: Session restoration for stateful connections
- **Bidirectional RPC**: Peer-to-peer capability passing
- **100% Interoperable**: Fully compatible with [TypeScript reference implementation](https://github.com/cloudflare/capnweb)

## Installation

```bash
pip install capnweb
# or
uv add capnweb
```

or, from this repository:

```bash
uv sync
```

## Quick Start

### Server

```python
import asyncio
from typing import Any
from capnweb.server import Server, ServerConfig
from capnweb.types import RpcTarget
from capnweb.error import RpcError

class Calculator(RpcTarget):
    async def call(self, method: str, args: list[Any]) -> Any:
        match method:
            case "add":
                return args[0] + args[1]
            case "subtract":
                return args[0] - args[1]
            case _:
                raise RpcError.not_found(f"Method {method} not found")

    async def get_property(self, property: str) -> Any:
        raise RpcError.not_found("Property access not implemented")

async def main() -> None:
    config = ServerConfig(host="127.0.0.1", port=8080)
    server = Server(config)

    # Register the main capability
    server.register_capability(0, Calculator())

    await server.start()
    print("Calculator server listening on http://127.0.0.1:8080/rpc/batch")

    # Keep running
    try:
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        await server.stop()

if __name__ == "__main__":
    asyncio.run(main())
```

### Client

```python
import asyncio
from capnweb.client import Client, ClientConfig

async def main() -> None:
    config = ClientConfig(url="http://localhost:8080/rpc/batch")

    # Use async context manager for automatic cleanup
    async with Client(config) as client:
        # Make RPC calls
        result = await client.call(0, "add", [5, 3])
        print(f"5 + 3 = {result}")  # Output: 5 + 3 = 8

        result = await client.call(0, "subtract", [10, 4])
        print(f"10 - 4 = {result}")  # Output: 10 - 4 = 6

if __name__ == "__main__":
    asyncio.run(main())
```

### Promise Pipelining

Batch multiple dependent calls into a single round trip:

```python
import asyncio
from capnweb.client import Client, ClientConfig

async def main() -> None:
    config = ClientConfig(url="http://localhost:8080/rpc/batch")

    async with Client(config) as client:
        # Create a pipeline batch
        batch = client.pipeline()

        # Make dependent calls - they will be batched
        user = batch.call(0, "authenticate", ["token-123"])
        profile = batch.call(0, "getUserProfile", [user.id])  # Property access on promise!
        notifications = batch.call(0, "getNotifications", [user.id])

        # All three calls execute efficiently
        u, p, n = await asyncio.gather(user, profile, notifications)

        print(f"User: {u['name']}")
        print(f"Profile: {p['bio']}")
        print(f"Notifications: {len(n)} unread")

if __name__ == "__main__":
    asyncio.run(main())
```

## Development

### Setup

```bash
# Clone and install with uv
git clone https://github.com/abilian/py-capnweb.git
cd py-capnweb
uv sync
```

### Testing

```bash
make test
# or
pytest
pytest tests/test_wire.py -v
# etc.
```

### Linting & Type Checking

```bash
# Run linter
ruff check

# Run type checker
pyrefly check src

# Run both
make check
```

## Project Structure

```
src/capnweb/
├── __init__.py         # Public API exports
├── ids.py              # ID types (ImportId, ExportId, IdAllocator)
├── error.py            # Error types (RpcError, ErrorCode)
├── wire.py             # Wire protocol messages and expressions
├── tables.py           # Import/Export tables with refcounting
├── types.py            # Core types (RpcTarget, Transport protocol)
├── evaluator.py        # Expression evaluator with remap support
├── transports.py       # Transport implementations (HTTP, WebSocket)
├── server.py           # Server with configurable security
├── client.py           # Client with automatic resource management
└── __main__.py         # CLI entry point (if applicable)

tests/
├── test_ids.py                 # ID allocation tests
├── test_wire.py                # Wire protocol tests
├── test_wire_protocol.py       # Advanced protocol features
├── test_tables.py              # Import/export table tests
├── test_error.py               # Error handling tests
├── test_evaluator.py           # Expression evaluation tests
├── test_remap_evaluation.py    # Remap (.map) tests
├── test_transports.py          # Transport abstraction tests
├── test_improvements.py        # Recent enhancements tests
├── test_integration.py         # End-to-end integration tests
└── test_bidirectional.py       # Peer-to-peer tests

examples/
├── calculator/          # Simple RPC calculator
├── batch-pipelining/    # Batching demonstration
└── peer_to_peer/        # Bidirectional RPC example
```

## Protocol Compliance

This implementation follows the official [Cap'n Web protocol specification](https://github.com/cloudflare/capnweb/blob/main/protocol.md) and supports:

### ✅ Implemented Features

- **Wire Protocol**: All core message types (push, pull, resolve, reject, release, abort)
- **Wire Expressions**: Error, import, export, promise, pipeline, date, remap
- **Array Escaping**: Proper `[[...]]` literal array escaping compatible with TypeScript implementation
- **Export ID Convention**: Positive export IDs matching TypeScript reference implementation
- **Release with refcount**: Proper reference counting for resource management
- **Remap expressions**: Full `.map()` operation support with captures and instructions
- **Transport abstraction**: HTTP batch and WebSocket transports
- **Security**: Configurable stack trace redaction
- **Error handling**: Structured error model with custom error data

### 🚧 Planned Features

- **WebTransport support**: H3-based transport for modern applications
- **IL plan execution**: Complex multi-step operations
- **Recorder macros**: Ergonomic client-side API generation

### Interoperability Testing

Comprehensive cross-implementation testing with the TypeScript reference implementation:

```bash
cd interop
bash run_tests.sh
```

**Test Matrix** (all passing ✅):
- Python Server ← Python Client
- Python Server ← TypeScript Client
- TypeScript Server ← Python Client
- TypeScript Server ← TypeScript Client

The interop test suite validates:
- Basic RPC operations (echo, arithmetic, string manipulation)
- Complex data types (arrays, objects)
- Error handling (not_found, bad_request)
- Concurrent batch calls
- Property access patterns

## License

Dual-licensed under MIT or Apache-2.0, at your option.
