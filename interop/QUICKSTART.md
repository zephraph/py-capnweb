# Interop Tests - Quick Start

## TL;DR

```bash
./run_tests.sh
```

That's it! The script will test all combinations automatically.

## What Gets Tested

✅ **Python ← Python** - Python client talks to Python server
✅ **Python ← TypeScript** - TypeScript client talks to Python server
✅ **TypeScript ← Python** - Python client talks to TypeScript server
✅ **TypeScript ← TypeScript** - TypeScript client talks to TypeScript server

## Requirements

### Must Have
- Python 3.10+
- capnweb package: `uv sync`

### Optional (for full tests)
- Node.js 18+
- TypeScript dependencies: `cd typescript && npm install`

## Manual Testing

### Quick Python Test

Terminal 1:
```bash
python3 python/server.py 8080
```

Terminal 2:
```bash
python3 python/client.py http://127.0.0.1:8080/rpc/batch
```

You should see:
```
✅ All tests passed!
```

## What If It Fails?

1. **Check logs:**
   ```bash
   cat /tmp/server_*.log
   cat /tmp/client_*.log
   ```

2. **Kill stuck processes:**
   ```bash
   lsof -ti:8080 | xargs kill -9
   ```

3. **Verify setup:**
   ```bash
   python3 -c "import capnweb; print('✓ capnweb installed')"
   node --version  # Should be 18+
   ```

## Test Results

All tests return identical JSON output regardless of implementation:

```json
{
  "echo": "Hello, World!",
  "add": 8,
  "multiply": 42,
  "concat": "Hello World",
  ...
}
```

This proves protocol compatibility!

## Next Steps

- Read full [README.md](README.md) for details
- Check [TODO.md](../TODO.md) for roadmap
- See [examples/](../examples/) for more use cases
