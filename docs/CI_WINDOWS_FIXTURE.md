# Windows fixture startup and resource cleanup

The initial matrix exposed an upstream Blender startup error while replacing
`free` in `ucrtbase.dll`. Direct Windows fixture-generation and independent
verification subprocesses use oneTBB's documented
`TBB_MALLOC_DISABLE_REPLACEMENT=1` setting (standard CRT allocator). The setting
is local to the disposable fixture environment and recorded in the report. It
does not replace the Blender binary, skip execution, install a DLL, or alter a
user's preferences. Actual harness workers retain the existing sanitized
environment policy; that policy is not relaxed to inherit this variable.
See the [oneTBB invocation-level documentation](https://uxlfoundation.github.io/oneTBB/main/tbb_userguide/Windows_C_Dynamic_Memory_Interface_Replacement.html).
This suite is not an allocator-performance qualification.

Catalog verification explicitly closes its real SQLite connection on both
success and assertion failure. A startup failure must not leave that test handle
open and obscure the original error during Windows temporary-directory cleanup.


This note describes test setup, not a claim that a queued or historical run passed.
Use the exact-commit reports from [Harness acceptance](CI_WORKFLOWS.md).
