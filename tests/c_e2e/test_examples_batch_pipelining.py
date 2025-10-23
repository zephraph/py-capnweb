"""End-to-end test for the batch-pipelining example."""

import asyncio
import sys
from pathlib import Path

import pytest

# Add examples directory to path to locate the scripts
examples_dir = Path(__file__).parent.parent.parent / "examples"
sys.path.insert(0, str(examples_dir))


@pytest.fixture
async def pipelining_server():
    """Starts the batch-pipelining server as a subprocess."""
    server_path = examples_dir / "batch-pipelining" / "server.py"
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        str(server_path),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    # Wait for the server to be ready
    await asyncio.sleep(3)

    yield process

    # Cleanup
    process.terminate()
    await process.wait()


@pytest.mark.asyncio
async def test_batch_pipelining_example(pipelining_server):
    """
    Tests the batch-pipelining example by running the server and client
    and verifying the final output.
    """
    client_path = examples_dir / "batch-pipelining" / "client.py"
    client_process = await asyncio.create_subprocess_exec(
        sys.executable,
        str(client_path),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    try:
        stdout, stderr = await asyncio.wait_for(
            client_process.communicate(), timeout=15
        )
    except asyncio.TimeoutError:
        client_process.kill()
        stdout, stderr = await client_process.communicate()
        pytest.fail("Client process timed out.")

    stdout_str = stdout.decode()
    stderr_str = stderr.decode()

    print("--- Client STDOUT ---")
    print(stdout_str)
    print("--- Client STDERR ---")
    print(stderr_str)

    assert client_process.returncode == 0, "Client process should exit cleanly"
    assert "--- Running pipelined" in stdout_str
    assert "--- Running sequential" in stdout_str
    assert "Summary:" in stdout_str
    assert "Authenticated user:" in stdout_str
    assert "Profile:" in stdout_str
    assert "Notifications:" in stdout_str
