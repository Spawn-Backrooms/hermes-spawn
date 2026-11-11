# Any-format file delivery

This is a source candidate extending dungeon draft PR #1 (`8a8bf829`) and
preserving merged main's OAuth retry change (`f9cb0d6`). It depends on the
companion arbitrary-file backend changes stacked on SPAWN draft PR #282. It is
not deployed or a completed live funding/delivery demonstration.

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

## Verification

- 17 new generic delivery/transport tests pass, including ten representative
  formats, the inclusive 5 MiB bound, preflight failures, safe paths, fences,
  corrupted descriptors/manifests, approval, lost responses and restart recovery.
- All 153 non-dashboard Python tests pass locally on Python 3.14; this includes
  the four merged OAuth retry tests. Desktop syntax and SDK smoke checks pass.
- The five dashboard tests cannot run in this local environment because FastAPI
  is absent. Dependency installation was blocked by the environment's PyPI
  network policy. They are not counted as passed here; unchanged CI runs them.
- Exact candidate CI and native Hermes validator/doctor results will be recorded
  when available. No live upload, grant upgrade, deployment, paid job or real
  Desktop interaction was performed for this change.
