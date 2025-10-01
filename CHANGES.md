# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Comprehensive test coverage for `session.py` (44% → 99%)
- Comprehensive test coverage for `stubs.py` (58% → 100%)
- 57 new tests covering session management and RPC stubs/promises
- Test coverage now at 71% overall (up from 67%)

### Changed
- Improved code quality and reduced cyclomatic complexity in 8 functions
- Refactored `TestService.call()` with dispatch table pattern
- Extracted helper methods in `PipelineBatch._execute()`
- Simplified `TargetStubHook.call()` with method extraction

### Fixed
- Moved all imports to top-level (resolved 61 PLC0415 violations)
- Fixed circular imports between hooks ↔ payload ↔ stubs
- Improved logging (use `logger.exception()` instead of `exc_info=True`)
- Fixed naming conventions (camelCase → snake_case)
- Fixed type checking errors in pipeline.py and tests

## [0.3.0]

### Added
- Promise pipelining support for batching multiple dependent RPC calls
- `PipelineBatch` and `PipelinePromise` classes for client-side pipelining
- Property access on promises creates pipelined references
- TypeScript interoperability with array escaping
- 179 tests with 67% coverage

### Changed
- Replaced `isinstance()` chains with match statements throughout codebase
- All linting checks now passing (ruff + pyrefly)

### Fixed
- Array escaping in wire protocol for TypeScript compatibility
- Special form detection in wire expression parsing

## [0.2.1]

### Added
- Resume tokens for session restoration
- `ResumeToken` and `ResumeTokenManager` classes
- Bidirectional RPC (peer-to-peer capability passing)
- Server-side resume token management

### Changed
- Improved session lifecycle management

## [0.2.0]

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

## [0.1.0]

### Added
- Initial project structure
- Core protocol types (IDs, errors, wire format)
- Basic RPC framework
- Documentation and examples

[Unreleased]: https://github.com/abilian/capn-python/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/abilian/capn-python/compare/v0.2.1...v0.3.0
[0.2.1]: https://github.com/abilian/capn-python/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/abilian/capn-python/releases/tag/v0.2.0
