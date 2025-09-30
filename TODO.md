# Cap'n Web Python - TODO

## Current Status

**v0.3.0 - Resume Tokens Complete** ✅

- ✅ Core protocol types (IDs, errors, wire format)
- ✅ HTTP batch transport (client & server)
- ✅ WebSocket transport
- ✅ Transport abstraction layer
- ✅ Capability dispatch and method calls
- ✅ Expression evaluator with match statements
- ✅ Remap expressions (`.map()` operations)
- ✅ Release with refcount
- ✅ Escaped literal arrays
- ✅ Promise resolution
- ✅ Error handling with custom data fields
- ✅ Security: Stack trace redaction
- ✅ Bidirectional RPC (peer-to-peer)
- ✅ Resume tokens for session restoration
- ✅ 153 tests, 74% coverage

---

## High Priority

### 1. Promise Pipelining (Optimization)

Chain calls without waiting for intermediate results.

**Current limitation:**
```python
# Currently requires await at each step:
user = await client.call(0, "getUser", [123])
profile = await client.call(user.id, "getProfile", [])

# Should allow (not yet optimized):
# Multiple calls in single batch with promise references
```

**Implementation:**
- [ ] Optimize batch sending to include promise references
- [ ] Add `pipeline()` method to Client for ergonomic API
- [ ] Handle promise chains on server side
- [ ] Tests for optimized pipelined calls

**Files:**
- `src/capnweb/client.py` (modify)
- `tests/test_pipeline.py` (new)

---

### 2. Interoperability Tests

Test Python client/server against TypeScript reference implementation.

**Implementation:**
- [ ] Set up TypeScript test server
- [ ] Python client → TypeScript server tests
- [ ] TypeScript client → Python server tests
- [ ] Golden transcript validation
- [ ] Document interop test setup

**Files:**
- `tests/interop/test_typescript.py` (new)
- `tests/interop/fixtures/` (test data)
- `tests/interop/README.md` (setup instructions)

---

## Medium Priority

### 3. WebTransport / HTTP/3

Modern transport using HTTP/3 and QUIC.

**Why needed:**
- Better performance than WebSocket
- Built-in multiplexing
- 0-RTT reconnection
- Future-proof

**Challenges:**
- Requires HTTP/3 support (aioquic library)
- Complex setup (TLS certificates required)
- Limited browser support (but improving)

**Implementation:**
- [ ] Research aioquic library
- [ ] Create `WebTransportServer` class
- [ ] Create `WebTransportClient` class
- [ ] Handle bidirectional streams
- [ ] Certificate management
- [ ] Tests

**Files:**
- `src/capnweb/transports.py` (extend)
- `tests/test_webtransport.py` (new)

---

### 4. IL (Intermediate Language) Execution

Execute complex multi-step operations defined in IL on the server.

**Note:** Remap expressions (`.map()`) are already implemented. This would add support for more complex IL plans.

**Implementation:**
- [ ] Parse IL plans from wire format
- [ ] Create IL instruction executor
- [ ] Implement all IL operations (call, get, if, loop, etc.)
- [ ] Variable scope management
- [ ] Tests for IL execution

**Files:**
- `src/capnweb/il/` (new module)
- `tests/test_il.py` (new)

---

### 5. Connection Management Improvements

**What's missing:**
- Connection pooling
- Automatic reconnection with exponential backoff
- Graceful shutdown with connection draining
- Connection health checks
- Configurable timeouts per-operation

**Implementation:**
- [ ] Add connection pool to Client
- [ ] Implement exponential backoff for reconnection
- [ ] Add graceful shutdown with drain
- [ ] Health check pings
- [ ] Configurable timeouts

**Files:**
- `src/capnweb/client.py` (modify)
- `src/capnweb/server.py` (modify)
- `tests/test_connection.py` (new)

---

### 6. Performance Optimization

**Areas to optimize:**
1. **JSON serialization** - Use faster libraries (orjson)
2. **Object pooling** - Reuse message objects
3. **Batch processing** - Optimize batch encoding/decoding
4. **Async efficiency** - Reduce future creation overhead
5. **Memory usage** - Profile and reduce allocations

**Implementation:**
- [ ] Add performance benchmarks
- [ ] Profile hot paths
- [ ] Replace json with orjson
- [ ] Add object pooling for messages
- [ ] Optimize evaluator paths
- [ ] Benchmark before/after

**Files:**
- `benchmarks/bench_serialization.py` (new)
- `benchmarks/bench_calls.py` (new)
- `benchmarks/bench_concurrent.py` (new)

---

## Low Priority / Nice to Have

### 7. Logging & Observability

**What's missing:**
- Structured logging
- Request tracing with correlation IDs
- Metrics (call counts, latency, errors)
- Health endpoints
- Debug mode

**Implementation:**
- [ ] Add structlog for structured logging
- [ ] Add request ID tracking
- [ ] Prometheus metrics endpoint
- [ ] Health check endpoint (`/health`)
- [ ] Debug mode with verbose logging

**Files:**
- `src/capnweb/logging.py` (new)
- `src/capnweb/metrics.py` (new)
- `src/capnweb/health.py` (new)

---

### 8. Additional Examples

**Needed examples:**
- [x] Simple calculator
- [x] Batch vs sequential
- [x] Peer-to-peer RPC
- [ ] Chat application (WebSocket + bidirectional)
- [ ] File server (streaming)
- [ ] Database proxy (connection pooling)
- [ ] Microservices (service-to-service RPC)

**Files:**
- `examples/chat/` (new)
- `examples/fileserver/` (new)
- `examples/database/` (new)
- `examples/microservices/` (new)

---

### 9. API Documentation

**Needed:**
- Sphinx documentation site
- API reference
- User guide
- Protocol guide
- Migration guide from TypeScript

**Implementation:**
- [ ] Set up Sphinx
- [ ] Generate API docs from docstrings
- [ ] Write user guide
- [ ] Write protocol guide
- [ ] Write migration guide from TypeScript
- [ ] Deploy to Read the Docs

**Files:**
- `docs/conf.py` (new)
- `docs/index.rst` (new)
- `docs/api/` (new)
- `docs/guide/` (new)
- `docs/protocol/` (new)

---

### 10. Property-Based Testing

Generate random inputs to find edge cases using Hypothesis.

**Implementation:**
- [ ] Add Hypothesis library
- [ ] Property tests for wire serialization
- [ ] Property tests for ID allocation
- [ ] Property tests for expression evaluation
- [ ] Fuzz testing for error paths

**Files:**
- `tests/test_properties.py` (new)

---

### 11. Load Testing

Test behavior under high load.

**Implementation:**
- [ ] Create load test scenarios
- [ ] Test with Locust or similar
- [ ] Measure throughput
- [ ] Measure latency percentiles
- [ ] Identify bottlenecks

**Files:**
- `load_tests/locustfile.py` (new)

---

## Quick Wins

These can be done quickly for immediate value:

1. **Health checks** - Add `/health` endpoint to server
2. **Metrics** - Basic Prometheus metrics
3. **CI improvements** - Add coverage reports, benchmark tracking
4. **Example refinements** - Add more detailed comments and error handling
5. **Documentation improvements** - More examples in docstrings

---

## Protocol Compliance Status

| Feature | TypeScript | Python | Status |
|---------|------------|--------|--------|
| HTTP Batch | ✅ | ✅ | Done |
| WebSocket | ✅ | ✅ | Done |
| WebTransport | ✅ | ❌ | TODO |
| Resume Tokens | ✅ | ✅ | Done |
| Bidirectional | ✅ | ✅ | Done |
| Promise Pipeline | ✅ | ⚠️ Basic | Medium Priority |
| Remap (`.map()`) | ✅ | ✅ | Done |
| IL Execution | ✅ | ⚠️ Remap only | Low Priority |
| Release + Refcount | ✅ | ✅ | Done |
| Escaped Arrays | ✅ | ✅ | Done |
| Test Coverage | ~90% | 74% | Ongoing |

**Overall Compliance: ~90%**

---

## Contributing

To work on any of these items:

1. Check if there's an existing issue, or create one
2. Comment on the issue to claim it
3. Create a branch from `main`
4. Write tests first (TDD)
5. Implement the feature
6. Ensure all tests pass: `pytest`
7. Ensure linting passes: `make check`
8. Update documentation
9. Submit PR
