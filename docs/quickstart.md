# Cap'n Web Python - Quickstart Guide

This guide will get you up and running with Cap'n Web Python in 5 minutes.

## What is Cap'n Web?

Cap'n Web is a capability-based RPC protocol that enables:
- **Type-safe remote procedure calls** between Python services
- **Promise pipelining** to batch multiple dependent calls into one round-trip
- **Bidirectional RPC** where both client and server can export capabilities
- **Resume tokens** for session restoration after disconnects
- **Multiple transports** (HTTP batch, WebSocket)

## Installation

```bash
# Clone the repository
git clone https://github.com/abilian/capn-python
cd capn-python

# Install with uv (recommended)
uv sync

# Or with pip
pip install -e .
```

## Your First RPC Service

### 1. Define Your Service

Create a service by implementing the `RpcTarget` protocol:

```python
# server.py
from capnweb.types import RpcTarget
from capnweb.server import Server, ServerConfig
from capnweb.error import RpcError

class Calculator(RpcTarget):
    """A simple calculator service."""

    async def call(self, method: str, args: list) -> int:
        """Handle RPC method calls."""
        match method:
            case "add":
                return args[0] + args[1]
            case "multiply":
                return args[0] * args[1]
            case _:
                raise RpcError.not_found(f"Method {method} not found")

    async def get_property(self, property: str):
        """Handle property access."""
        raise RpcError.not_found(f"Property {property} not found")

# Create and run server
async def main():
    config = ServerConfig(host="127.0.0.1", port=8080)
    server = Server(config)

    # Register the calculator at capability ID 0
    server.register_capability(0, Calculator())

    # Run the server
    async with server:
        print("Calculator server running on http://127.0.0.1:8080")
        await asyncio.Event().wait()  # Run forever

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

### 2. Create a Client

Connect to your service and make calls:

```python
# client.py
import asyncio
from capnweb.client import Client, ClientConfig

async def main():
    config = ClientConfig(url="http://127.0.0.1:8080/rpc/batch")

    async with Client(config) as client:
        # Simple call
        result = await client.call(0, "add", [5, 3])
        print(f"5 + 3 = {result}")  # 8

        # Another call
        result = await client.call(0, "multiply", [4, 7])
        print(f"4 * 7 = {result}")  # 28

if __name__ == "__main__":
    asyncio.run(main())
```

### 3. Run It

```bash
# Terminal 1 - Start server
python server.py

# Terminal 2 - Run client
python client.py
```

## Promise Pipelining

One of Cap'n Web's most powerful features is **promise pipelining** - batching multiple dependent calls into a single network round-trip:

```python
from capnweb.pipeline import PipelineBatch

async def pipeline_example():
    config = ClientConfig(url="http://127.0.0.1:8080/rpc/batch")

    async with Client(config) as client:
        # Create a pipeline batch
        batch = PipelineBatch(client, capability_id=0)

        # Queue multiple calls - they execute in one round-trip!
        call1 = batch.call("add", [10, 20])      # Returns a promise
        call2 = batch.call("multiply", [5, 6])    # Returns a promise
        call3 = batch.call("add", [100, 200])     # Returns a promise

        # Execute the batch (single network request)
        await batch.execute()

        # Await the results
        result1 = await call1  # 30
        result2 = await call2  # 30
        result3 = await call3  # 300

        print(f"Results: {result1}, {result2}, {result3}")
```

**Without pipelining:** 3 network round-trips
**With pipelining:** 1 network round-trip ⚡

## Working with Capabilities

Capabilities are unforgeable references to remote objects. They can be:
- Returned from RPC calls
- Passed as arguments to other calls
- Stored and reused

```python
class UserService(RpcTarget):
    """Service that returns user capabilities."""

    async def call(self, method: str, args: list):
        match method:
            case "getUser":
                # Return a capability (another RpcTarget)
                return User(name=args[0])
            case _:
                raise RpcError.not_found(f"Method {method} not found")

    async def get_property(self, property: str):
        raise RpcError.not_found(f"Property {property} not found")

class User(RpcTarget):
    """A user capability."""

    def __init__(self, name: str):
        self.name = name

    async def call(self, method: str, args: list):
        match method:
            case "getName":
                return self.name
            case "greet":
                return f"Hello, I'm {self.name}!"
            case _:
                raise RpcError.not_found(f"Method {method} not found")

    async def get_property(self, property: str):
        match property:
            case "name":
                return self.name
            case _:
                raise RpcError.not_found(f"Property {property} not found")

# Client usage
async def use_capabilities():
    async with Client(config) as client:
        # Get a user capability
        user_stub = await client.call(0, "getUser", ["Alice"])

        # Call methods on the capability
        name = await user_stub.getName()
        greeting = await user_stub.greet()

        print(name)      # "Alice"
        print(greeting)  # "Hello, I'm Alice!"

        # Access properties
        name_prop = await user_stub.name
        print(name_prop)  # "Alice"
```

## Error Handling

Cap'n Web has structured error handling:

```python
from capnweb.error import RpcError, ErrorCode

# Server side - raise structured errors
async def call(self, method: str, args: list):
    if method == "divide":
        if args[1] == 0:
            raise RpcError.bad_request(
                "Division by zero",
                data={"dividend": args[0], "divisor": args[1]}
            )
        return args[0] / args[1]
    raise RpcError.not_found(f"Method {method} not found")

# Client side - catch errors
try:
    result = await client.call(0, "divide", [10, 0])
except RpcError as e:
    print(f"Error: {e.code} - {e.message}")
    print(f"Data: {e.data}")
    # Error: bad_request - Division by zero
    # Data: {'dividend': 10, 'divisor': 0}
```

## Next Steps

- **[Architecture Guide](architecture.md)** - Understand the hook-based architecture
- **[API Reference](api-reference.md)** - Detailed API documentation
- **[Examples](../examples/)** - More complete examples
- **[Advanced Topics](advanced.md)** - Resume tokens, bidirectional RPC, transports

## Common Patterns

### Resource Cleanup

Always use async context managers to ensure proper cleanup:

```python
# Good - resources cleaned up automatically
async with Client(config) as client:
    result = await client.call(0, "method", [])

# Also good - manual cleanup
client = Client(config)
try:
    result = await client.call(0, "method", [])
finally:
    await client.close()
```

### Structuring Services

Organize your services into classes:

```python
class MyService(RpcTarget):
    def __init__(self, db_connection):
        self.db = db_connection

    async def call(self, method: str, args: list):
        # Use match statements for method dispatch
        match method:
            case "create":
                return await self._create(args[0])
            case "read":
                return await self._read(args[0])
            case "update":
                return await self._update(args[0], args[1])
            case "delete":
                return await self._delete(args[0])
            case _:
                raise RpcError.not_found(f"Method {method} not found")

    async def _create(self, data):
        # Implementation
        pass

    async def _read(self, id):
        # Implementation
        pass

    # ... etc
```

## Troubleshooting

### Server not responding

Check that:
1. Server is running on the correct port
2. Client URL matches server address
3. Firewall isn't blocking the port

### Import errors

Make sure you've installed the package:
```bash
uv sync  # or pip install -e .
```

### Type errors

Enable type checking during development:
```bash
pyrefly check
```

## Getting Help

- **GitHub Issues**: https://github.com/abilian/capn-python/issues
- **Examples**: See the `examples/` directory
- **Tests**: The test suite has many usage examples
