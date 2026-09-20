# Windows JSON persistence and recovery


The Windows full journey at head `fe7e4f6fb82c1e64bf67dd894c0f1911d97caa22`
retained a real failed `project.json` replacement (`EPERM`) after a successful
Blender preview. The exact process holding that handle was not identified. The
production-only Windows scenario passed; rerunning a transient failure is not a
fix for production persistence.

Launcher JSON writes now retry only Windows `EPERM`/`EACCES`/`EBUSY` rename
conflicts for at most nine attempts and 2270 ms of total backoff. The destination
is never unlinked or copied over. Persistent and other OS/storage errors still
fail; a complete unpublished temporary snapshot is retained and identified in
the error rather than presented as saved. Writer/revision checks are unchanged.

Contract tests inject bounded failures; a separate Windows-only test also holds
a real .NET read handle without delete sharing, requires actual rename refusal,
then releases that handle and verifies the atomic replacement. This is native
filesystem evidence, not Windows desktop/Blender GUI acceptance.
