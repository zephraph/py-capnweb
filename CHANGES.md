# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.4.0] - 2025-10-02

### Added
- **WebTransport/HTTP/3 Support** - Full implementation of modern transport protocol
- **Examples**
  - `examples/webtransport/` - Standalone WebTransport echo server/client
  - `examples/webtransport-integrated/` - Integrated WebTransport with full RPC
  - `examples/actor-system/` - Distributed actor system with supervisor/worker pattern
- **Tests**
  - 12 new WebTransport unit tests in `tests/test_webtransport.py`
  - All 352 tests passing (up from 329, +23 tests)
- **Documentation**
  - Complete READMEs for all new examples
  - WebTransport vs WebSocket comparison
  - Certificate generation guides

### Changed
- **Code Quality Improvements**
  - Fixed all linting issues (0 errors with ruff)
  - Fixed all typing issues (0 errors with pyrefly, 17 intentional ignores)
  - Converted f-strings to lazy % formatting in logging statements
  - Used `asyncio.Event().wait()` instead of `while True: await asyncio.sleep(1)` patterns
  - Used `contextlib.suppress()` instead of try/except/pass patterns
- **Type Improvements**
  - Added `WebTransportTransport` to `Client._transport` type annotation
  - Added explicit type annotations for `asyncio.gather()` results
  - Added type ignores for aioquic library compatibility
- **API Improvements**
  - `Client` now supports all three transports: HTTP Batch, WebSocket, and WebTransport
  - Transport auto-detection based on URL scheme and path
  - Server can run multiple transports simultaneously

## [0.3.1] - 2025-10-01

### Added
- **Comprehensive Documentation**
  - Quickstart Guide (`docs/quickstart.md`) - Get started in 5 minutes
  - Architecture Guide (`docs/architecture.md`) - Understand the hook-based design
  - API Reference (`docs/api-reference.md`) - Complete API documentation
  - Documentation Index (`docs/README.md`) - Central documentation hub
- **Comprehensive test coverage improvements across core modules**
  - `session.py` - 44% → 99% coverage (+31 tests)
  - `stubs.py` - 58% → 100% coverage (+26 tests)
  - `parser.py` - 47% → 98% coverage (+30 tests)
  - `hooks.py` - 54% → 86% coverage (+36 tests)
  - `serializer.py` - 68% → 100% coverage (+26 tests)
  - `payload.py` - 84% → 100% coverage (+23 tests)
  - 172 new tests added (329 total, up from 179)
  - Test coverage now at 85% overall (up from 67%)

### Changed
- Improved code quality and reduced cyclomatic complexity in 8 functions
- Refactored `TestService.call()` with dispatch table pattern
- Extracted helper methods in `PipelineBatch._execute()`
- Simplified `TargetStubHook.call()` with method extraction

### Removed
- **Legacy code cleanup** - removed monolithic evaluator and table abstractions
- `evaluator.py` (286 lines, 31% coverage) - replaced by parser + serializer + hooks
- `tables.py` (82 lines, 0% coverage) - replaced by RpcSession
- `test_remap_evaluation.py` - tests for removed evaluator
- `test_tables.py` - tests for removed tables module
- Architecture now fully hook-based with no legacy code paths

## [0.3.0] - 2025-10-01

### Added
- Promise pipelining support for batching multiple dependent RPC calls
- `PipelineBatch` and `PipelinePromise` classes for client-side pipelining
- Property access on promises creates pipelined references
- TypeScript interoperability with array escaping
- 179 tests with 67% coverage

### Changed
- Replaced `isinstance()` chains with match statements throughout codebase
- All linting checks now passing (ruff + pyrefly)

## [0.2.1] - 2025-09-30

### Added
- Resume tokens for session restoration
- `ResumeToken` and `ResumeTokenManager` classes
- Bidirectional RPC (peer-to-peer capability passing)
- Server-side resume token management

### Changed
- Improved session lifecycle management

## [0.2.0] - 2025-09-30

### Added
- HTTP batch transport (client & server)
- WebSocket transport
- Transport abstraction layer
- Basic client/server implementation
- Wire protocol serialization/deserialization
- Capability dispatch and method calls
- Expression evaluator with match statements
- Remap expressions (`.map()` operations)
- Release with refcount
- Escaped literal arrays
- Promise resolution
- Error handling with custom data fields
- Security: Stack trace redaction
- 165 tests with 74% coverage

### Changed
- Complete protocol implementation matching TypeScript reference

## [0.1.0] - 2025-09-30

### Added
- Initial project structure
- Core protocol types (IDs, errors, wire format)
- Basic RPC framework
- Documentation and examples

[Unreleased]: https://github.com/abilian/capn-python/compare/v0.4.0...HEAD
[0.4.0]: https://github.com/abilian/capn-python/compare/v0.3.1...v0.4.0
[0.3.1]: https://github.com/abilian/capn-python/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/abilian/capn-python/compare/v0.2.1...v0.3.0
[0.2.1]: https://github.com/abilian/capn-python/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/abilian/capn-python/releases/tag/v0.2.0
[0.1.0]: https://github.com/abilian/capn-python/releases/tag/v0.1.0
