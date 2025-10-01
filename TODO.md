# Cap'n Web Python - TODO

## Current Status

**v0.3.1-dev - Test Coverage & Code Quality** 🚧

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
- ✅ Promise pipelining (batching calls)
- ✅ TypeScript interoperability (array escaping)
- ✅ Code quality improvements (reduced cyclomatic complexity)
- ✅ 236 tests, 71% coverage

**See [CHANGES.md](CHANGES.md) for detailed changelog.**

---

## Next Steps (Priority Order)

### 1. Test Coverage Improvements (High Priority)
**Current:** 71% coverage, **Target:** 80%+

**Completed:**
- ✅ `session.py` - 44% → 99% (+55 points)
- ✅ `stubs.py` - 58% → 100% (+42 points)

**Areas needing coverage:**
- `parser.py` - Wire format parsing (47% → 70%)
- `hooks.py` - Error cases in hook types (54% → 75%)
- `client.py` - Error handling paths (60% → 80%)
- `evaluator.py` - Legacy code paths (31% → 50%, low priority)

**Implementation:**
- [ ] Add tests for parser edge cases (malformed wire expressions)
- [ ] Add tests for hook disposal and reference counting
- [ ] Add tests for client error scenarios (network failures, timeouts)
- [ ] Add tests for evaluator edge cases (deeply nested expressions)

**Files:**
- ✅ `tests/test_session.py` (31 tests added)
- ✅ `tests/test_stubs.py` (26 tests added)
- `tests/test_parser.py` (expand existing)
- `tests/test_hooks_lifecycle.py` (new)
- `tests/test_client_errors.py` (new)

---

### 2. Documentation & Examples (High Priority)
**What's missing:**
- User guide for getting started
- API reference documentation
- More realistic examples
- Migration guide from TypeScript

**Implementation:**
- [ ] Set up Sphinx documentation
- [ ] Write quickstart guide
- [ ] Document all public APIs
- [ ] Add chat application example (WebSocket + bidirectional)
- [ ] Add microservices example (service-to-service RPC)
- [ ] Write TypeScript → Python migration guide

**Files to create:**
- `docs/` directory with Sphinx setup
- `examples/chat/` - Real-time chat using WebSocket
- `examples/microservices/` - Service mesh example

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
| Promise Pipeline | ✅ | ✅ | Done (v0.3.0) |
| Remap (`.map()`) | ✅ | ✅ | Done |
| IL Execution | ✅ | ⚠️ Remap only | Low Priority |
| Release + Refcount | ✅ | ✅ | Done |
| Escaped Arrays | ✅ | ✅ | Done |
| Test Coverage | ~90% | 71% | 🔄 In Progress |
| Code Quality | ✅ | ✅ | ✅ Done (v0.3.1) |

**Overall Compliance: ~95%** (up from ~90%)

**Code Quality Metrics:**
- ✅ All linting checks passing (ruff + pyrefly)
- ✅ Type checking passing
- ✅ 236 tests passing (up from 179)
- ✅ Cyclomatic complexity under control
- ✅ No code smells (import violations, naming issues)
- ✅ 71% test coverage (up from 67%, target 80%)

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
