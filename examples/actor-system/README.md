# Distributed Actor System Example

This example demonstrates a distributed actor system built with Cap'n Web, showcasing:

- **Dynamic capability creation** - Supervisor spawns workers on demand
- **Capability passing** - Worker references returned as first-class objects
- **Location transparency** - Client interacts with workers directly without knowing their location
- **Stateful actors** - Each worker maintains independent state

## Architecture

```
┌─────────┐                    ┌────────────────────────────┐
│ Client  │ ──── spawn ───→    │   Supervisor Process       │
│         │                    │  ┌──────────────────────┐  │
│         │ ←── worker_cap ──  │  │    Supervisor        │  │
│         │                    │  └──────────────────────┘  │
│         │                    │           │                │
│         │                    │           ├─ Worker-A      │
│         │ ──── increment ────┼───────────┘                │
│         │                    │           └─ Worker-B      │
└─────────┘                    └────────────────────────────┘
```

## Files

- **`worker.py`** - Defines a stateful worker actor with a counter
- **`supervisor.py`** - Long-running server that spawns and manages workers
- **`main.py`** - Client application that demonstrates the system

## Running the Demo

### Terminal 1: Start the Supervisor

```bash
python examples/actor-system/supervisor.py
```

Expected output:
```
Server listening on 127.0.0.1:8080
Supervisor listening on http://127.0.0.1:8080/rpc/batch
Press Ctrl+C to stop
```

The supervisor will show when workers are created:
```
  [Worker 'Worker-A' created in PID 12345]
Supervisor spawned worker 'Worker-A' with export ID 1
```

### Terminal 2: Run the Client

```bash
python examples/actor-system/main.py
```

Expected output:
```
--- Distributed Actor System Demo ---
Connecting to supervisor at http://127.0.0.1:8080/rpc/batch...

1. Spawning two workers...
  - Received capabilities for Worker-A (import ID 2) and Worker-B (import ID 1).

2. Interacting directly with workers...

3. Sending 'increment' messages to workers concurrently...
  - Sent two increments to Worker-A, one to Worker-B.

4. Verifying final worker states...
  - Final count for Worker-A: 2
  - Final count for Worker-B: 1

✅ Demo finished successfully!
```

## How It Works

### 1. Spawning Workers

The client requests workers from the supervisor:

```python
spawn_task1 = client.call(0, "spawn_worker", ["Worker-A"])
spawn_task2 = client.call(0, "spawn_worker", ["Worker-B"])
results = await asyncio.gather(spawn_task1, spawn_task2)
```

The supervisor creates worker instances, registers them with the server, and returns RpcStub capabilities:

```python
worker = Worker(name)
export_id = self._next_export_id
self._server.register_capability(export_id, worker)
hook = TargetStubHook(worker)
return RpcStub(hook)
```

### 2. Location Transparency

The client receives RpcStub objects wrapping RpcImportHooks. These stubs can be used to call methods on the workers directly:

```python
worker_a_cap = results[0]  # RpcStub wrapping RpcImportHook
worker_a_id = worker_a_cap._hook.import_id

# Call methods on the worker
await client.call(worker_a_id, "increment", [])
count = await client.call(worker_a_id, "get_count", [])
```

### 3. Stateful Actors

Each worker maintains its own state independently:

```python
class Worker(RpcTarget):
    def __init__(self, name: str):
        self._name = name
        self._count = 0
        self._pid = os.getpid()

    async def call(self, method: str, args: list[Any]) -> Any:
        match method:
            case "increment":
                self._count += 1
                return self._count
            case "get_count":
                return self._count
```

## Key Concepts

### Object Capabilities

Workers are **unforgeable references** - the client can only interact with workers the supervisor explicitly gave it. There's no global registry or ambient authority.

### Dynamic Creation

Unlike static service endpoints, workers are created dynamically at runtime. Each has a unique export ID allocated by the supervisor.

### Capability Passing

The supervisor doesn't just return data about workers - it returns **actual capabilities** (RpcStub objects) that the client can use to interact with them.

### Distributed State

Each worker maintains its own counter. The supervisor doesn't track worker state - it's truly distributed.

## Comparison to Traditional RPC

**Traditional RPC:**
```python
# Client calls supervisor for every operation
supervisor.increment_worker("Worker-A")
supervisor.get_worker_count("Worker-A")
```

**Cap'n Web:**
```python
# Client gets worker capability once, then uses it directly
worker = await supervisor.spawn_worker("Worker-A")
await worker.increment()
await worker.get_count()
```

This reduces latency, improves scalability, and follows the principle of least authority.

## Inspiration

This pattern is inspired by:

- **Erlang/OTP** - Supervisor trees and actor spawning
- **Akka** - Actor systems and location transparency
- **E language** - Object capabilities and promise pipelining

## Next Steps

Try modifying the example to:

- Add more worker methods (e.g., `decrement`, `reset`)
- Implement worker supervision (restart failed workers)
- Pass worker capabilities between workers
- Create hierarchical supervisor trees
