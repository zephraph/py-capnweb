"""Main application demonstrating the distributed actor system.

This client connects to the supervisor, requests workers, and then
communicates with the workers directly, demonstrating location transparency.

Run (after starting supervisor.py):
    python examples/actor-system/main.py
"""

import asyncio

from capnweb.client import Client, ClientConfig
from capnweb.core.hooks import RpcImportHook


async def main() -> None:
    """Main application logic that uses the distributed actor system."""
    print("--- Distributed Actor System Demo ---")
    supervisor_url = "http://localhost:8080/rpc/batch"
    config = ClientConfig(url=supervisor_url)

    try:
        async with Client(config) as client:
            print(f"Connecting to supervisor at {supervisor_url}...")

            # === Step 1: Spawn two workers via the supervisor ===
            print("\n1. Spawning two workers...")
            spawn_task1 = client.call(0, "spawn_worker", ["Worker-A"])
            spawn_task2 = client.call(0, "spawn_worker", ["Worker-B"])

            results = await asyncio.gather(spawn_task1, spawn_task2)

            # The client library automatically converts the returned export IDs
            # into usable RpcStub objects (capabilities) wrapping RpcImportHooks.
            worker_a_cap = results[0]
            worker_b_cap = results[1]

            # Extract the import IDs so we can call methods using client.call()
            assert isinstance(worker_a_cap._hook, RpcImportHook)
            assert isinstance(worker_b_cap._hook, RpcImportHook)

            worker_a_id = worker_a_cap._hook.import_id
            worker_b_id = worker_b_cap._hook.import_id

            print(
                f"  - Received capabilities for Worker-A (import ID {worker_a_id}) and Worker-B (import ID {worker_b_id})."
            )

            # === Step 2: Interact with the workers directly ===
            # The client now has direct references to the workers and does not
            # need to go through the supervisor anymore. This is location transparency.
            print("\n2. Interacting directly with workers...")

            # Send messages (call methods) to the workers concurrently
            print("\n3. Sending 'increment' messages to workers concurrently...")
            # Use client.call() with the import IDs
            inc_task1 = client.call(worker_a_id, "increment", [])
            inc_task2 = client.call(worker_a_id, "increment", [])
            inc_task3 = client.call(worker_b_id, "increment", [])

            await asyncio.gather(inc_task1, inc_task2, inc_task3)
            print("  - Sent two increments to Worker-A, one to Worker-B.")

            # === Step 3: Verify the final state of the workers ===
            print("\n4. Verifying final worker states...")
            count_a = await client.call(worker_a_id, "get_count", [])
            count_b = await client.call(worker_b_id, "get_count", [])

            print(f"  - Final count for Worker-A: {count_a}")
            print(f"  - Final count for Worker-B: {count_b}")

            assert count_a == 2
            assert count_b == 1
            print("\n✅ Demo finished successfully!")

    except Exception as e:
        print(f"\n❌ An error occurred: {e}")
        print(
            "  Please ensure the supervisor is running: "
            "python examples/actor-system/supervisor.py"
        )


if __name__ == "__main__":
    asyncio.run(main())
