# Any-format file delivery

The generic file lane is included in runtime baseline
`885205d2163979cd3ea8c991803151f46ac3fb39`, with the child-approval pinning fix
and native OAuth retry preserved. It requires the matching SPAWN backend file
routes. Plugin tests do not establish that backend deployment or a real buyer
funding/delivery demonstration has completed.

## Contract

`spawn_deliver_files` takes a job ID and 1–10 file entries:

```json
{"job_id":"job-id","files":[
  {"path":"outputs/report.pdf","media_type":"application/pdf"},
  {"path":"outputs/art.png","name":"final-art.png","media_type":"image/png"},
  {"path":"outputs/package.zip"}
]}
```

Paths are explicit, relative to the current Hermes workspace. Files are not
converted: every byte is delivered intact. Arbitrary extensions are accepted,
including unknown formats. Each file must be nonempty and at most 5 MiB
(5,242,880 bytes). A batch has at most ten distinct, case-insensitively unique
filenames, each at most 160 UTF-16 units with no slash or control characters.
Server upload-history and expiry limits remain authoritative: ten upload slots
per lease generation, 100 lifetime reservations per job, and the existing
reservation deadline. Retrying unchanged descriptors reuses the same slots.

Optional `media_type` is a lowercase MIME token, at most 127 characters, without
parameters. It becomes `declared_media_type` in the immutable descriptor. The
actual descriptor and HTTP type are always `application/octet-stream`. The
reserved upload is transferred with native Hermes credentials through fixed
SPAWN `PUT /api/v1/external-work/uploads/{upload_id}/file`, using strict JSON
`{"content_base64":"..."}`. The MCP request body limit is unchanged.

## Safety and recovery

Generic files are opaque, authenticated attachments. SPAWN neither parses,
extracts, renders nor executes them. MIME metadata is not trusted validation.
Byte integrity is not a malware scan or a guarantee that the file opens in a
particular application. Existing strict text, MP4 and game-package lanes keep
their validation and preview behavior. Generic game ZIPs do not acquire the
validated-game label.

The client rejects traversal, absolute paths, symlinks, special files and known
credential paths; it cannot detect every secret in ordinary files or archives.
Select only intended deliverables. All files are preflighted before the first
reservation, and re-read with the same size/hash immediately before transfer.
The plugin validates reservation and completion identity, job, installation,
grant, lease, descriptor, returned full manifest and canonical manifest hash.
No base64 or raw file content is returned to the model or persisted in plugin
retry state. Keep original bytes for a retry.

An authoritative, definitive lease/upload-expired response releases only the
local artifact-batch recovery lock, without deleting or submitting server bytes.
This allows explicit progress/resume or abandonment instead of permanently
blocking recovery. Expired upload IDs are never relabeled as new uploads.

A lost response preserves the exact batch descriptors, pins and request keys
across restart. Retry the same output names, bytes and MIME metadata from the
same conversation. Other parent/child/package mutations are blocked while a
batch is uncertain. Changed authority is a stop, not permission to retry under
a new grant. Each manifest remains owned by its originating conversation and
lease. Uploading never submits it: `spawn_submit` still requires human approval.

## Current baseline verification

The exact baseline above passed all 161 Python tests, Desktop syntax/SDK smoke,
official Hermes validator and doctor in
[run 42965593638](https://github.com/Spawn-Backrooms/hermes-spawn/actions/runs/42965593638).
See [validation evidence](validation-report.md). This includes the five dashboard
tests that the earlier local environment could not execute. A later catalog pin
still requires validation on that exact commit.

## Historical implementation checks

- 17 new generic delivery/transport tests pass, including ten representative
  formats, the inclusive 5 MiB bound, preflight failures, safe paths, fences,
  corrupted descriptors/manifests, approval, lost responses and restart recovery.
- All 153 non-dashboard Python tests pass locally on Python 3.14; this includes
  the four merged OAuth retry tests. Desktop syntax and SDK smoke checks pass.
- The five dashboard tests cannot run in this local environment because FastAPI
  is absent. Dependency installation was blocked by the environment's PyPI
  network policy. They are not counted as passed here; unchanged CI runs them.
- No live upload, grant upgrade, deployment, paid job or real Desktop interaction
  was performed for that implementation check. The subsequent remote results
  above supersede only its pending source-validation status.
