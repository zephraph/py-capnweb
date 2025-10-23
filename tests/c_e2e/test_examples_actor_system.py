"""End-to-end test for the actor-system example."""

import asyncio
import sys
from pathlib import Path

import pytest

# Add examples directory to path to locate the scripts
examples_dir = Path(__file__).parent.parent.parent / "examples"
sys.path.insert(0, str(examples_dir))


@pytest.fixture
async def supervisor_server():
    """Starts the actor-system supervisor as a subprocess."""
    server_path = examples_dir / "actor-system" / "supervisor.py"
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        str(server_path),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    # Wait for the server to be ready - give it more time to initialize
    await asyncio.sleep(3)

    yield process

    # Cleanup
    process.terminate()
    await process.wait()


@pytest.mark.asyncio
async def test_actor_system_example(supervisor_server):
    """
    Tests the actor-system example by running the supervisor and main client
    and verifying the client's successful completion message.
    """
    client_path = examples_dir / "actor-system" / "main.py"
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
    assert "✅ Demo finished successfully!" in stdout_str, "Demo should report success"
    assert "Final count for Worker-A: 2" in stdout_str
    assert "Final count for Worker-B: 1" in stdout_str
