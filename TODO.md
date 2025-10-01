# Cap'n Web Python - TODO

## Current Status

**v0.3.1-dev - Architecture Complete & High Test Coverage** ✅

- ✅ Core protocol types (IDs, errors, wire format)
- ✅ HTTP batch transport (client & server)
- ✅ WebSocket transport
- ✅ Transport abstraction layer
- ✅ Capability dispatch and method calls
- ✅ Hook-based architecture (replaced evaluator)
- ✅ Remap expressions (`.map()` operations)
- ✅ Release with refcount
- ✅ Escaped literal arrays
- ✅ Promise resolution
- ✅ Error handling with custom data fields
- ✅ Security: Stack trace redaction
- ✅ Bidirectional RPC (peer-to-peer)
- ✅ Resume tokens for session restoration
- ✅ Promise pipelining (batching calls)
- ✅ TypeScript interoperability (array escaping)
- ✅ Code quality improvements (reduced cyclomatic complexity)
- ✅ Legacy code removed (evaluator.py, tables.py)
- ✅ **329 tests, 85% coverage** (up from 179 tests, 67%)

**See [CHANGES.md](CHANGES.md) for detailed changelog.**

---

## Next Steps (Priority Order)

### 2. Documentation & Examples (High Priority) ✅ **COMPLETE**
**Completed:**
- ✅ Documentation created (quickstart, architecture, API reference)
- ✅ Chat application example (WebSocket + bidirectional RPC)
- ✅ Microservices example (service mesh with capability passing)

**Files created:**
- ✅ `docs/README.md` - Documentation hub
- ✅ `docs/quickstart.md` - Getting started guide
- ✅ `docs/architecture.md` - Hook-based architecture explanation
- ✅ `docs/api-reference.md` - Complete API documentation
- ✅ `examples/chat/` - Real-time chat (server.py, client.py, README.md)
- ✅ `examples/microservices/` - Service mesh (user_service.py, order_service.py, api_gateway.py, client.py, README.md)

**Still missing (lower priority):**
- [ ] Set up Sphinx for hosted docs (optional - markdown docs sufficient for now)
- [ ] Write TypeScript → Python migration guide

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

**Completed examples:**
- [x] Simple calculator
- [x] Batch vs sequential
- [x] Peer-to-peer RPC
- [x] Chat application (WebSocket + bidirectional)
- [x] Microservices (service-to-service RPC)

**Additional examples (nice to have):**
- [ ] File server (streaming)
- [ ] Database proxy (connection pooling)

**Files:**
- ✅ `examples/chat/` - Real-time chat with WebSocket
- ✅ `examples/microservices/` - Service mesh architecture
- `examples/fileserver/` (future)
- `examples/database/` (future)

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
| Promise Pipeline | ✅ | ✅ | Done (v0.3.0) |
| Remap (`.map()`) | ✅ | ✅ | Done |
| IL Execution | ✅ | ⚠️ Remap only | Low Priority |
| Release + Refcount | ✅ | ✅ | Done |
| Escaped Arrays | ✅ | ✅ | Done |
| Test Coverage | ~90% | **85%** | ✅ **Done** |
| Code Quality | ✅ | ✅ | ✅ Done (v0.3.1) |
| Hook Architecture | ✅ | ✅ | ✅ **Done** (v0.3.1) |

**Overall Compliance: ~98%** (up from ~90%)

**Code Quality Metrics:**
- ✅ All linting checks passing (ruff + pyrefly)
- ✅ Type checking passing (pyrefly)
- ✅ **329 tests passing** (up from 179, +150 tests)
- ✅ Cyclomatic complexity under control
- ✅ No code smells (import violations, naming issues)
- ✅ **85% test coverage** (up from 67%, exceeded 80% target!)
- ✅ **8 modules at 100% coverage**
- ✅ **Legacy code removed** (evaluator.py, tables.py)

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
