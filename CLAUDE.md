# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Python implementation of the Cap'n Web protocol - a capability-based RPC system with promise pipelining, structured errors, and multiple transport support. The implementation provides both client and server with full protocol compliance.

**Key characteristics:**
- Async/await based on Python's asyncio
- Type-safe with full type hints (pyright/mypy compatible)
- Protocol-compliant with TypeScript reference implementation
- Comprehensive test coverage (165 tests, 64%+ coverage)

## Important

1) DO NOT DO THE COMMITS YOURSELF. I will do the git commits after reviewing.

2) Use match statements instead of chains of "if isinstance(...)"..


## Essential Commands

### Development Setup
```bash
# Install dependencies
uv sync

# Activate virtual environment (if needed)
source .venv/bin/activate
```

### Testing
```bash
# Run all tests
pytest
# or
make test

# Run specific test file
pytest tests/test_wire.py -v

# Run specific test
pytest tests/test_wire.py::TestWireMessages::test_wire_push -v

# Run with coverage
pytest --cov=capnweb --cov-report=term-missing
# or
make test-cov

# Run tests without stopping on first failure
pytest -v

# Run tests with verbose output
pytest -xvs
```

### Linting and Type Checking
```bash
# Run linter
ruff check

# Run type checker
pyrefly check

# Run both linter and type checker
make lint

# Auto-fix linting issues
ruff check --fix

# Format code
ruff format
# or
make format
```

### Running Examples
```bash
# Run calculator server
python examples/calculator/server.py

# Run calculator client (in another terminal)
python examples/calculator/client.py
```

## Core Architecture

### Hook-Based Capability System

The architecture uses a **StubHook pattern** for decentralized capability handling. Instead of a monolithic evaluator, each hook type manages specific scenarios:

**Key components:**
- `StubHook` (abstract base in `hooks.py`): Defines interface for all hooks
  - `call(path, args)`: Call a method through this hook
  - `get(path)`: Get a property through this hook
  - `pull()`: Resolve to final value (for awaiting)
  - `dispose()`: Release resources
  - `dup()`: Duplicate (increment refcount)

**Hook implementations:**
- `ErrorStubHook`: Holds an error (errors propagate through chains)
- `PayloadStubHook`: Wraps locally-resolved data
- `TargetStubHook`: Wraps a local RpcTarget object (server-side capabilities)
- `RpcImportHook`: Represents a remote capability (communicates with RpcSession)
- `PromiseStubHook`: Wraps a future that resolves to another hook

**User-facing wrappers:**
- `RpcStub` (in `stubs.py`): Pythonic wrapper using `__getattr__` and `__call__`
- `RpcPromise` (in `stubs.py`): Awaitable wrapper with chaining support

### Session Management

`RpcSession` (in `session.py`) is the base class for both Client and Server:

**Responsibilities:**
- Manage import table (remote capabilities we reference)
- Manage export table (local capabilities we expose)
- Allocate import/export IDs
- Create hooks for imports/exports
- Handle promise resolution
- Implement Exporter and Importer protocols

**Subclasses:**
- `Client` (in `client.py`): Extends RpcSession with transport layer
- `Server` (in `server.py`): Extends RpcSession with HTTP/WebSocket endpoints

### Payload Ownership Semantics

`RpcPayload` (in `payload.py`) tracks data provenance to prevent mutation bugs:

**Sources:**
- `PARAMS`: From application parameters - must deep-copy before use
- `RETURN`: From application return value - we take ownership
- `OWNED`: Already copied/deserialized - safe to use

**Key method:** `ensure_deep_copied()` - ensures safe ownership before transmission

### Wire Protocol

**Messages** (in `wire.py`):
- `WirePush`: Client sends expression to evaluate (creates import)
- `WirePull`: Request resolution of an import
- `WireResolve`: Server returns resolved value
- `WireReject`: Server returns error
- `WireRelease`: Client releases import (with refcount)
- `WireAbort`: Fatal error, terminates session

**Expressions** (in `wire.py`):
- `WireError`: Error representation
- `WireExport`: Reference to exported capability `["export", id]`
- `WireImport`: Reference to imported capability `["import", id]`
- `WirePromise`: Promise reference `["promise", id]`
- `WirePipeline`: Method call expression `["pipeline", cap, path, args]`
- `WireRemap`: Map operation `["remap", instructions, value]`
- `WireDate`: Date serialization

### Serialization/Deserialization

**Serializer** (in `serializer.py`):
- Converts Python objects to wire format (JSON-serializable)
- Finds RpcStub/RpcPromise and exports them via RpcSession
- Replaces stubs with `["export", id]` expressions

**Parser** (in `parser.py`):
- Converts wire format back to Python objects
- Recognizes special forms like `["export", id]` and creates hooks
- Uses RpcSession to import capabilities

### Promise Pipelining

`PipelineBatch` (in `pipeline.py`):
- Batches multiple dependent calls into single HTTP request
- Tracks pending calls with allocated import IDs
- Returns `PipelinePromise` objects that can be awaited or used in subsequent calls
- Property access on promises: `user.id` creates dependent pipeline calls

### Transport Abstraction

`Transport` protocol (in `transports.py`):
- Abstract interface for different transport mechanisms
- `HttpBatchTransport`: HTTP POST with NDJSON batches
- `WebSocketTransport`: Persistent WebSocket connection

**Client auto-creates transport based on URL scheme:**
- `http://` or `https://` → HttpBatchTransport
- `ws://` or `wss://` → WebSocketTransport

## Important Patterns

### Type Checking vs Runtime Imports

To avoid circular imports, use TYPE_CHECKING for type hints and local imports for runtime:

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from capnweb.types import RpcTarget

class Foo:
    def method(self, target: RpcTarget) -> None:
        # Import locally at runtime if needed
        from capnweb.types import RpcTarget
        ...
```

### Error Handling

Always use structured error codes:
```python
from capnweb.error import RpcError

# Use factory methods
raise RpcError.not_found("Resource not found")
raise RpcError.bad_request("Invalid arguments")
raise RpcError.internal("Internal error")

# Or create with code
raise RpcError(ErrorCode.PERMISSION_DENIED, "Access denied")
```

### Resource Management

All capabilities support explicit disposal:
```python
# Manual disposal
stub = client.create_stub(...)
try:
    result = await stub.call(...)
finally:
    stub.dispose()

# Or use async context manager
async with client.create_stub(...) as stub:
    result = await stub.call(...)
```

### Testing Async Code

All async tests use `pytest-asyncio`:
```python
import pytest

@pytest.mark.asyncio
async def test_something():
    result = await async_function()
    assert result == expected
```

## Code Organization

```
src/capnweb/
├── session.py          # Base session (import/export management)
├── hooks.py            # Hook implementations (core capability system)
├── stubs.py            # User-facing RpcStub/RpcPromise wrappers
├── payload.py          # Payload ownership semantics
├── serializer.py       # Python → wire format
├── parser.py           # Wire format → Python
├── client.py           # Client implementation (extends RpcSession)
├── server.py           # Server implementation (extends RpcSession)
├── pipeline.py         # Promise pipelining support
├── wire.py             # Wire protocol messages and expressions
├── transports.py       # Transport abstraction
├── ids.py              # Type-safe ID wrappers
├── error.py            # Error codes and RpcError
├── types.py            # Core protocols (RpcTarget, Transport)
├── resume.py           # Resume token support
├── evaluator.py        # Legacy evaluator (being phased out)
└── tables.py           # Legacy tables (being phased out)

tests/
├── test_integration.py         # End-to-end client/server tests
├── test_pipeline.py            # Pipelining tests
├── test_bidirectional.py       # Peer-to-peer capability passing
├── test_wire.py                # Wire protocol serialization
├── test_wire_protocol.py       # Advanced wire features
├── test_remap_evaluation.py    # .map() operation tests
├── test_resume.py              # Resume token tests
├── test_improvements.py        # Recent feature tests
└── test_*.py                   # Unit tests for each module
```

## Architecture Evolution

**Current state (v0.3.0):**
- ✅ Core hook-based architecture implemented
- ✅ Session-based import/export management
- ✅ Promise pipelining with PipelineBatch
- ✅ Payload ownership tracking
- ✅ All 165 tests passing

**Legacy code (being phased out):**
- `evaluator.py`: Monolithic expression evaluator (replaced by hooks + serializer/parser)
- `tables.py`: Old import/export tables (replaced by RpcSession)

**Note:** When modifying code, prefer using the new hook-based architecture. The legacy evaluator is maintained for compatibility but should not be extended.

## Protocol Compliance

This implementation follows the [Cap'n Web protocol specification](https://github.com/cloudflare/capnweb/blob/main/protocol.md).

**Wire format:** NDJSON (newline-delimited JSON)
**Endpoints:**
- HTTP batch: `/rpc/batch`
- WebSocket: `/rpc/ws` (planned)

**Compatible with:**
- TypeScript reference implementation
- Rust implementation (in development)

## Security Considerations

**Stack trace redaction:**
Server has `include_stack_traces` flag (default: False) to prevent leaking internal details:
```python
config = ServerConfig(
    host="127.0.0.1",
    port=8080,
    include_stack_traces=False  # Never enable in production
)
```

**Capability security:**
- Capabilities are unforgeable references
- Explicit disposal prevents leaks
- No ambient authority

## Debugging Tips

### Enable verbose logging
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Inspect wire messages
The wire protocol uses NDJSON - you can inspect HTTP traffic:
```bash
# Watch network traffic
tcpdump -i lo0 -A 'tcp port 8080'
```

### Test individual hooks
```python
from capnweb.hooks import PayloadStubHook
from capnweb.payload import RpcPayload

# Create a test hook
hook = PayloadStubHook(RpcPayload.owned({"user": {"id": 123}}))

# Test property access
result_hook = hook.get(["user", "id"])
payload = await result_hook.pull()
print(payload.value)  # 123
```

## Common Pitfalls

1. **Circular imports**: Use TYPE_CHECKING for type hints, local imports at runtime
2. **Forgetting ensure_deep_copied()**: Always call on payloads before transmission
3. **Not disposing resources**: Use async context managers or explicit dispose()
4. **Mixing old and new architecture**: Don't extend evaluator.py - use hooks instead
5. **Assuming synchronous behavior**: All RPC calls are async - must await

## Version History

- **v0.3.0**: Promise pipelining, hook-based architecture
- **v0.2.1**: Resume tokens, bidirectional RPC
- **v0.2.0**: Basic client/server, wire protocol
- **v0.1.0**: Initial release
