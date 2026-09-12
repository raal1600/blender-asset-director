# Security model

This is local agent-accessible code with the user's ordinary filesystem privileges, **not an OS sandbox** and not a completed security audit. Review before deployment on sensitive machines.

## Implemented restrictions

- The runtime provides no arbitrary shell/eval tool, server/listening port, browser automation, clipboard access, GPU inference or LLM/cloud-generation call.
- Networking is GET-only and origin-allowlisted. Each redirect is revalidated. DNS destinations must be globally routable; the validated address is used for TLS with original-host SNI/certificate checks. Environment proxy/cookie/browser sessions are not reused.
- Provider credentials stay in an explicit environment variable, are not put in process arguments/catalogs, and are not forwarded to storage hosts. Error bodies and signed URLs are not printed.
- Downloads and archive extraction are bounded. Extraction rejects traversal, absolute/drive paths, device names, special files/symlinks, encrypted entries, case collisions and suspicious compression ratios. Unsupported executable files are skipped.
- glTF imports validate resource URIs. Downloaded Python is not executed as an asset. Native Blender formats/importers still process complex untrusted data; use trusted publishers and updated Blender.
- Blender mutation runs in a separate process with factory startup, `--disable-autoexec`, `use_scripts=False` when opening files, a clean environment, timeout, bounded logs and new output paths. No global preferences are saved.
- The reviewed retarget backend is pinned and verified before import. Full add-on registration/scripted drivers are not enabled. Running reviewed third-party Python still requires trust in that source and Blender itself.
- Skill install/update/uninstall checks ownership receipts and preserves the independent asset library. It never edits Codex/DeepSeek authentication or MCP configuration.

## Trust boundaries and limits

The agent host can still have shell or Blender MCP capabilities outside this package. Instructions alone cannot cryptographically prevent that host from ignoring policy. The toolkit's constrained commands improve auditability but do not reduce the host's pre-existing OS permissions.

Source/asset license evidence is a recorded claim, not a legal guarantee or trademark/likeness clearance. HTML, filenames, metadata and `.blend` text blocks are task data, never executable instructions granting permissions. Do not bulk scrape accounts or upload user models to cloud services without explicit approval.

Window/scene images handed to an agent host may leave the machine through that host's configured model. The helper itself sends no telemetry. Provider searches disclose the submitted keywords to the selected provider. Logs/reports may contain local paths and asset names; keep user logs private and do not commit them.

## Verification status

Offline tests cover important schema, archive, credential-forwarding and job-integrity behaviors with synthetic data/mocked networking. They are not live penetration testing. See `docs/ACCEPTANCE.md` for what has actually run. Report issues privately to the repository owner when they may expose user data; do not publish keys, sensitive assets or exploit logs.
