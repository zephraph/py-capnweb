"""End-to-end test for the peer-to-peer example."""

import asyncio
import sys
from pathlib import Path

import pytest

# Add examples directory to path to locate the scripts
examples_dir = Path(__file__).parent.parent.parent / "examples"
sys.path.insert(0, str(examples_dir))


@pytest.mark.asyncio
async def test_peer_to_peer_example():
    """
    Tests the peer-to-peer example by running both alice.py and bob.py
    as subprocesses and verifying they communicate with each other.
    """
    alice_path = examples_dir / "peer_to_peer" / "alice.py"
    bob_path = examples_dir / "peer_to_peer" / "bob.py"

    alice_proc = None
    bob_proc = None

    # Use unbuffered output to ensure prints are captured
    env = {"PYTHONUNBUFFERED": "1"}

    try:
        # Start Alice first
        alice_proc = await asyncio.create_subprocess_exec(
            sys.executable,
            "-u",  # Force unbuffered output
            str(alice_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )

        # Give Alice a moment to start her server
        await asyncio.sleep(3)

        # Start Bob
        bob_proc = await asyncio.create_subprocess_exec(
            sys.executable,
            "-u",  # Force unbuffered output
            str(bob_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )

        # Wait for Bob's server to start before connections are attempted
        await asyncio.sleep(3)

        # Let them run and communicate for a few seconds
        await asyncio.sleep(3)

        # Terminate both processes
        alice_proc.terminate()
        bob_proc.terminate()

        # Capture outputs
        alice_stdout, alice_stderr = await alice_proc.communicate()
        bob_stdout, bob_stderr = await bob_proc.communicate()

        alice_stdout_str = alice_stdout.decode()
        bob_stdout_str = bob_stdout.decode()

        print("--- Alice STDOUT ---")
        print(alice_stdout_str)
        print("--- Bob STDOUT ---")
        print(bob_stdout_str)

        # Verify Alice's output
        assert "🚀 Starting Alice" in alice_stdout_str
        assert "Alice is running" in alice_stdout_str
        assert "📨 Alice received: Hi Alice, this is Bob!" in alice_stdout_str
        assert not alice_stderr.decode(), "Alice should have no stderr output"

        # Verify Bob's output
        assert "🚀 Starting Bob" in bob_stdout_str
        assert "Connecting to Alice" in bob_stdout_str
        assert "Bob calls Alice.greet()" in bob_stdout_str
        assert (
            "Hello! I'm Alice" in bob_stdout_str
        )  # Bob successfully got Alice's response
        assert not bob_stderr.decode(), "Bob should have no stderr output"

    finally:
        # Ensure processes are cleaned up
        if alice_proc and alice_proc.returncode is None:
            alice_proc.kill()
            await alice_proc.wait()
        if bob_proc and bob_proc.returncode is None:
            bob_proc.kill()
            await bob_proc.wait()
