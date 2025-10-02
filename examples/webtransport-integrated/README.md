# WebTransport Integrated Example

This example demonstrates WebTransport/HTTP/3 with the fully integrated Cap'n Web Server and Client.

## Difference from Basic Example

- **Basic example** (`examples/webtransport/`): Uses standalone WebTransportServer/Client classes
- **This example**: Uses integrated `Server` and `Client` classes with full RPC protocol support

## Features

- Full Cap'n Web RPC protocol over WebTransport
- Calculator RPC target
- Server serves both HTTP and WebTransport simultaneously
- Client auto-detects transport based on URL

## Files

- `server.py` - Integrated server with both HTTP and WebTransport
- `client.py` - Client using WebTransport URL
- `generate_certs.py` - Certificate generation script

## Running

### Step 1: Generate Certificates

```bash
python examples/webtransport-integrated/generate_certs.py
```

### Step 2: Start Server

```bash
python examples/webtransport-integrated/server.py
```

Output:
```
Server listening on localhost:8080
WebTransport server listening on https://localhost:4433/rpc/wt
```

### Step 3: Run Client

```bash
python examples/webtransport-integrated/client.py
```

## Key Differences

### Server Configuration

```python
from capnweb.server import Server, ServerConfig

config = ServerConfig(
    host="localhost",
    port=8080,
    # Enable WebTransport
    enable_webtransport=True,
    webtransport_port=4433,
    webtransport_cert_path="localhost.crt",
    webtransport_key_path="localhost.key",
)

server = Server(config)
server.register_capability(0, Calculator())
await server.start()
```

### Client Usage

```python
from capnweb.client import Client, ClientConfig

# WebTransport URL - client auto-detects transport
config = ClientConfig(url="https://localhost:4433/rpc/wt")

async with Client(config) as client:
    result = await client.call(0, "add", [5, 3])
    print(result)  # 8
```

The Client automatically uses WebTransportTransport based on the URL!

## Simultaneous Transports

The server can serve multiple transports simultaneously:

```python
# HTTP client
http_client = Client(ClientConfig(url="http://localhost:8080/rpc/batch"))

# WebTransport client
wt_client = Client(ClientConfig(url="https://localhost:4433/rpc/wt"))

# Both connect to the same server, same RPC targets!
```

## Advantages

1. **Unified API** - Same Server/Client classes for all transports
2. **Transport Transparency** - Client auto-selects based on URL
3. **Shared State** - All transports share the same RPC targets
4. **Production Ready** - Full protocol support, not just echo
