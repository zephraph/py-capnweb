# Cap'n Web Python Implementation

Python implementation of the [Cap'n Web protocol](https://github.com/cloudflare/capnweb), delivering both server and client with support for HTTP batch and WebSocket transports.

## Features

- **Capability-based security**: Unforgeable object references with explicit disposal
- **Expression evaluation**: Full support for wire expressions including remap (`.map()` operations)
- **Multiple transports**: HTTP batch and WebSocket with pluggable transport abstraction
- **Type-safe**: Full type hints with pyright/mypy compatibility
- **Async/await**: Built on Python's asyncio
- **Error handling**: Structured error model with security-conscious stack trace redaction
- **Reference counting**: Automatic resource management with proper refcounting
- **Interoperable**: Compatible with TypeScript and Rust implementations

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
- **Release with refcount**: Proper reference counting for resource management
- **Remap expressions**: Full `.map()` operation support with captures and instructions
- **Escaped literal arrays**: `[[...]]` format to prevent special form confusion
- **Transport abstraction**: HTTP batch and WebSocket transports
- **Security**: Configurable stack trace redaction
- **Error handling**: Structured error model with custom error data

### 🚧 Planned Features

- **Promise pipelining**: Chaining calls without waiting for intermediate results
- **WebTransport support**: H3-based transport for modern applications
- **IL plan execution**: Complex multi-step operations
- **Recorder macros**: Ergonomic client-side API generation

### Interoperability

Designed to be fully compatible with:
- [TypeScript reference implementation](https://github.com/cloudflare/capnweb)
- Rust implementation (in development)

## License

Dual-licensed under MIT or Apache-2.0, at your option.
