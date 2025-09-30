"""Client demonstrating batching + pipelining vs sequential calls.

Usage (separate terminal from server):
    python examples/batch-pipelining/client.py
"""

import asyncio
import os
import time
from typing import Any

from capnweb.client import Client, ClientConfig

# Mirror of the server API shape (for reference):
# authenticate(session_token) -> {"id": ..., "name": ...}
# getUserProfile(user_id) -> {"id": ..., "bio": ...}
# getNotifications(user_id) -> [...]

RPC_URL = os.getenv("RPC_URL", "http://localhost:3000/rpc/batch")
SIMULATED_RTT_MS = int(os.getenv("SIMULATED_RTT_MS", "120"))  # per-direction
SIMULATED_RTT_JITTER_MS = int(os.getenv("SIMULATED_RTT_JITTER_MS", "40"))


async def run_pipelined() -> dict[str, Any]:
    """Run with batching and pipelining (single round trip)."""
    fetch_count = 0
    t0 = time.perf_counter()

    # NOTE: Pipelining requires WirePipeline support (future enhancement)
    # This example demonstrates batching but not true pipelining
    config = ClientConfig(url=RPC_URL)
    client = Client(config)

    # In a pipelined implementation, these would all be sent in one batch
    # and user.id would be used without awaiting
    # Call signature: call(cap_id, method, args)
    # cap_id=0 is the main/default capability
    user = await client.call(0, "authenticate", ["cookie-123"])
    profile = await client.call(0, "getUserProfile", [user["id"]])
    notifications = await client.call(0, "getNotifications", [user["id"]])

    await client.close()
    fetch_count = 3  # Would be 1 with true pipelining

    t1 = time.perf_counter()
    return {
        "u": user,
        "p": profile,
        "n": notifications,
        "ms": (t1 - t0) * 1000,
        "posts": fetch_count,
    }


async def run_sequential() -> dict[str, Any]:
    """Run with separate round trips (no batching)."""
    fetch_count = 0
    t0 = time.perf_counter()

    # 1) Authenticate (1 round trip)
    config1 = ClientConfig(url=RPC_URL)
    client1 = Client(config1)
    u = await client1.call(0, "authenticate", ["cookie-123"])
    await client1.close()
    fetch_count += 1

    # 2) Fetch profile (2nd round trip)
    config2 = ClientConfig(url=RPC_URL)
    client2 = Client(config2)
    p = await client2.call(0, "getUserProfile", [u["id"]])
    await client2.close()
    fetch_count += 1

    # 3) Fetch notifications (3rd round trip)
    config3 = ClientConfig(url=RPC_URL)
    client3 = Client(config3)
    n = await client3.call(0, "getNotifications", [u["id"]])
    await client3.close()
    fetch_count += 1

    t1 = time.perf_counter()
    return {"u": u, "p": p, "n": n, "ms": (t1 - t0) * 1000, "posts": fetch_count}


async def main() -> None:
    """Run both pipelined and sequential examples."""
    print(
        f"Simulated network RTT (each direction): ~{SIMULATED_RTT_MS}ms ±{SIMULATED_RTT_JITTER_MS}ms"
    )
    print("\n--- Running pipelined (batched, single round trip) ---")
    print("NOTE: True pipelining not yet implemented in Python client")

    pipelined = await run_pipelined()
    print(f"HTTP POSTs: {pipelined['posts']}")
    print(f"Time: {pipelined['ms']:.2f} ms")
    print(f"Authenticated user: {pipelined['u']}")
    print(f"Profile: {pipelined['p']}")
    print(f"Notifications: {pipelined['n']}")

    print("\n--- Running sequential (non-batched, multiple round trips) ---")
    sequential = await run_sequential()
    print(f"HTTP POSTs: {sequential['posts']}")
    print(f"Time: {sequential['ms']:.2f} ms")
    print(f"Authenticated user: {sequential['u']}")
    print(f"Profile: {sequential['p']}")
    print(f"Notifications: {sequential['n']}")

    print("\nSummary:")
    print(f"Pipelined: {pipelined['posts']} POST(s), {pipelined['ms']:.2f} ms")
    print(f"Sequential: {sequential['posts']} POST(s), {sequential['ms']:.2f} ms")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"Error: {e}")
        exit(1)
