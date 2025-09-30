Batch + Pipelining (Single Round Trip)

This example shows how to issue a sequence of dependent RPC calls that all execute on the server in a single HTTP round trip using batching and promise pipelining.

What it does

- Authenticates a user.
- Uses the returned user ID (without awaiting) to fetch the profile and notifications.
- Awaits all results together. Even though there are multiple calls and dependencies, they travel in one request and one response.

Run locally (Python 3.11+)

1) Install dependencies:
   uv pip install -e .

2) Start the server:
   python examples/batch-pipelining/server.py

3) In a separate terminal, run the client:
   python examples/batch-pipelining/client.py

Files

- server.py: Minimal aiohttp server using Cap'n Web Python server.
- client.py: Client demonstrating batching concept (full pipelining not yet implemented).
- server-node.mjs: Original Node.js server (reference)
- client.mjs: Original Node.js client (reference)

Why this matters

- With normal HTTP or naive GraphQL usage, each dependent call often needs another round trip. Here, dependent calls are constructed locally, sent once, and executed on the server with results streamed back — minimizing latency dramatically.
