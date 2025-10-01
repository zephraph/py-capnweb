# Cap'n Web Python Documentation

Welcome to the Cap'n Web Python documentation!

## Getting Started

- **[Quickstart Guide](quickstart.md)** - Get up and running in 5 minutes
- **[Installation](#installation)** - How to install the library
- **[Examples](../examples/)** - Working code examples

## Core Documentation

- **[API Reference](api-reference.md)** - Complete API documentation
- **[Architecture Guide](architecture.md)** - Understand the hook-based architecture
- **[Advanced Topics](advanced.md)** - Resume tokens, bidirectional RPC, transports

## Installation

### Using uv (Recommended)

```bash
git clone https://github.com/abilian/capn-python
cd capn-python
uv sync
```

### Using pip

```bash
git clone https://github.com/abilian/capn-python
cd capn-python
pip install -e .
```

## Quick Example

```python
# Server
from capnweb.server import Server, ServerConfig
from capnweb.types import RpcTarget

class Calculator(RpcTarget):
    async def call(self, method: str, args: list):
        match method:
            case "add": return args[0] + args[1]
            case _: raise RpcError.not_found(f"{method} not found")

    async def get_property(self, property: str):
        raise RpcError.not_found(f"{property} not found")

async def main():
    config = ServerConfig(host="127.0.0.1", port=8080)
    server = Server(config)
    server.register_capability(0, Calculator())

    async with server:
        print("Server running on http://127.0.0.1:8080")
        await asyncio.Event().wait()
```

```python
# Client
from capnweb.client import Client, ClientConfig

async def main():
    config = ClientConfig(url="http://127.0.0.1:8080/rpc/batch")

    async with Client(config) as client:
        result = await client.call(0, "add", [5, 3])
        print(f"5 + 3 = {result}")  # 8
```

## What is Cap'n Web?

Cap'n Web is a capability-based RPC protocol that provides:

- **Type-safe RPC** - Fully type-hinted Python APIs
- **Promise Pipelining** - Batch multiple dependent calls into one round-trip
- **Bidirectional RPC** - Both client and server can export capabilities
- **Resume Tokens** - Session restoration after disconnects
- **Multiple Transports** - HTTP batch, WebSocket (WebTransport planned)
- **Structured Errors** - Rich error types with custom data
- **Reference Counting** - Automatic resource cleanup

## Documentation Structure

### For Users

1. Start with the **[Quickstart Guide](quickstart.md)**
2. Review the **[API Reference](api-reference.md)** for details
3. Explore **[Examples](../examples/)** for real-world usage
4. Read **[Advanced Topics](advanced.md)** when needed

### For Contributors

1. Understand the **[Architecture Guide](architecture.md)**
2. Review the **[Contributing Guide](../CONTRIBUTING.md)** (if exists)
3. Check the **[TODO](../TODO.md)** for open tasks
4. Read the **[Changelog](../CHANGES.md)** for recent changes

## Features

### Implemented ✅

- HTTP batch transport (client & server)
- WebSocket transport
- Capability dispatch and method calls
- Hook-based architecture
- Promise pipelining
- Bidirectional RPC (peer-to-peer)
- Resume tokens for session restoration
- TypeScript interoperability
- Structured error handling
- Reference counting and resource management
- **329 tests, 85% coverage**

### Planned 🚧

- WebTransport / HTTP/3
- Full IL (Intermediate Language) execution
- Sphinx documentation site
- More examples (chat, microservices)

## Protocol Compliance

This implementation follows the [Cap'n Web protocol specification](https://github.com/cloudflare/capnweb/blob/main/protocol.md).

**Compatibility:** ~98% with TypeScript reference implementation

## Community

- **GitHub**: https://github.com/abilian/capn-python
- **Issues**: https://github.com/abilian/capn-python/issues
- **Discussions**: https://github.com/abilian/capn-python/discussions

## License

This project is licensed under the MIT License - see the LICENSE file for details.
