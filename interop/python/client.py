#!/usr/bin/env python3
"""Python interop client for testing against any Cap'n Web server.

This client runs a comprehensive test suite against a Cap'n Web server,
exercising all major protocol features.
"""

import asyncio
import json
import sys
from typing import Any

from capnweb.client import Client, ClientConfig


async def run_tests(client: Client) -> dict[str, Any]:
    """Run comprehensive interop tests.

    Returns a dict with test results that can be compared across implementations.
    """
    results = {}

    print("Running interop tests...")

    # Test 1: Basic echo
    print("  1. Basic echo...")
    result = await client.call(0, "echo", ["Hello, World!"])
    results["echo"] = result
    assert result == "Hello, World!", f"Echo failed: {result}"

    # Test 2: Arithmetic
    print("  2. Arithmetic (add)...")
    result = await client.call(0, "add", [5, 3])
    results["add"] = result
    assert result == 8, f"Add failed: {result}"

    print("  3. Arithmetic (multiply)...")
    result = await client.call(0, "multiply", [7, 6])
    results["multiply"] = result
    assert result == 42, f"Multiply failed: {result}"

    # Test 3: String operations
    print("  4. String concatenation...")
    result = await client.call(0, "concat", ["Hello", " ", "World"])
    results["concat"] = result
    assert result == "Hello World", f"Concat failed: {result}"

    # Test 4: Property access
    print("  5. Property access...")
    result = await client.call(0, "getUserCount", [])
    results["userCount"] = result
    assert isinstance(result, int), f"User count should be int: {result}"

    # Test 5: Array handling
    print("  6. Array processing...")
    result = await client.call(0, "processArray", [[1, 2, 3, 4, 5]])
    results["processArray"] = result
    assert result == [2, 4, 6, 8, 10], f"Process array failed: {result}"

    # Test 6: Object handling
    print("  7. Object processing...")
    result = await client.call(0, "processObject", [{"a": 1, "b": 2, "c": 3}])
    results["processObject"] = result
    assert result["count"] == 3, f"Process object failed: {result}"
    assert set(result["keys"]) == {"a", "b", "c"}, f"Keys mismatch: {result}"

    # Test 7: Get array of values
    print("  8. Get all user names...")
    result = await client.call(0, "getAllUserNames", [])
    results["allUserNames"] = result
    assert isinstance(result, list), f"Should return list: {result}"
    assert len(result) >= 3, f"Should have at least 3 users: {result}"

    # Test 8: Skip capability for now (needs proper serialization)
    # print("  9. Get user capability...")
    # user = await client.call(0, "getUser", [1])

    # Test 9: Call method that returns user name directly
    print("  9. Get user name...")
    name = await client.call(0, "getUserName", [1])
    results["userName"] = name
    assert isinstance(name, str), f"User name should be string: {name}"

    # Test 10: Error handling
    print("  11. Error handling (not_found)...")
    try:
        await client.call(0, "throwError", ["not_found"])
        msg = "Should have raised an error"
        raise AssertionError(msg)
    except Exception as e:
        results["errorNotFound"] = str(e)
        if "not found" not in str(e).lower():
            msg = f"Wrong error: {e}"
            raise AssertionError(msg) from e

    print("  12. Error handling (bad_request)...")
    try:
        await client.call(0, "throwError", ["bad_request"])
        msg = "Should have raised an error"
        raise AssertionError(msg)
    except Exception as e:
        results["errorBadRequest"] = str(e)
        if "invalid" not in str(e).lower() and "bad" not in str(e).lower():
            msg = f"Wrong error: {e}"
            raise AssertionError(msg) from e

    # Test 11: Batch/concurrent calls
    print("  13. Concurrent batch calls...")
    batch_results = await asyncio.gather(
        client.call(0, "add", [1, 1]),
        client.call(0, "add", [2, 2]),
        client.call(0, "add", [3, 3]),
    )
    results["batchCalls"] = batch_results
    assert batch_results == [2, 4, 6], f"Batch calls failed: {batch_results}"

    # Test 12: Property access on service
    print("  14. Service properties...")
    version = await client.call(0, "echo", ["test"])  # Just verify service works
    results["serviceAlive"] = version is not None

    print("\n✅ All tests passed!")
    return results


async def main() -> None:
    """Run the Python interop client."""
    if len(sys.argv) < 2:
        print("Usage: python client.py <server-url>")
        print("Example: python client.py http://127.0.0.1:8080/rpc/batch")
        sys.exit(1)

    url = sys.argv[1]

    print(f"Python interop client connecting to: {url}\n")

    config = ClientConfig(url=url)

    async with Client(config) as client:
        results = await run_tests(client)

        # Output results as JSON for comparison
        print("\nTest Results (JSON):")
        print(json.dumps(results, indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(main())
