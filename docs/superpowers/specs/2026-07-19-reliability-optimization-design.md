# Pet Translator Reliability Optimization Design

## Context

The service already supports audio classification, visual detection, JSON event storage,
JWT authentication, and WebSocket delivery. The current work adds per-pet audio/visual
fusion and visual evidence persistence, but the implementation needs explicit production
boundaries before release.

This design follows the Superpowers brainstorming and review principles: keep the scope
small, compare alternatives, define observable behavior first, and verify every claim.

## Considered Approaches

### 1. Bounded in-memory, event-driven fusion (selected)

Each accepted audio or visual observation immediately produces a fusion result. Buffers
and history are isolated by `pet_id`, bounded, protected by a lock, and expired against an
injectable clock. This matches the current synchronous API and avoids a storage migration.

Trade-off: fusion history is reset when the process restarts.

### 2. Persist every fusion result

Store fusion records alongside behavior events. This supports audit and restart recovery,
but requires a schema, repository API, migration rules, and retention policy. It is larger
than the reliability objective of this iteration.

### 3. Continuous stream processor

Move camera sampling and audio/visual correlation into a background worker. This is the
right direction for continuous monitoring, but introduces worker lifecycle, backpressure,
deduplication, and shutdown concerns that need a separate design.

## Selected Design

### Fusion Engine

- Keep one audio and one visual buffer per pet.
- Normalize timestamps at ingestion. ISO 8601 values, including `Z` and timezone offsets,
  are converted to naive UTC strings; malformed or missing timestamps use the injected
  current UTC time.
- Remove entries older than the configured window relative to real current time. Also
  remove entries outside the latest observation's window so replayed test or device data
  cannot pair unrelated observations.
- Fuse only the latest valid audio and visual observations within the time window.
- Use a deterministic weighted confidence (`45%` audio, `55%` visual), clamped to `[0, 1]`.
- Preserve single-source results while waiting for a matching source.
- Bound history per pet and return defensive list/dict copies.

### API and Persistence

- `POST /api/upload_audio` accepts an optional `pet_id`; valid pet sounds are persisted and
  fed into fusion. Environmental noise is returned and broadcast but is not persisted or
  fused because it is not a pet behavior event.
- `POST /api/camera/detect` persists meaningful visual behaviors and JPEG evidence, then
  feeds the observation into fusion. `unknown` and `no_pet_detected` remain diagnostic
  responses and are not behavior events.
- `GET /api/fusions` returns recent results for one pet.
- Query limits are constrained to `1..100`. Omitting `pet_id` from `GET /api/events` means
  all pets, independent of the optional `PET_ID` ingestion default.
- Event and evidence identifiers use UUID-derived values to prevent same-second collisions.

### Authentication Compatibility

Use the maintained `bcrypt` API directly instead of Passlib. Password hashes remain
standard bcrypt strings, so existing users remain compatible. Replace deprecated
`datetime.utcnow()` calls with an explicit UTC helper while keeping SQLite's existing
naive UTC column representation.

### Delivery and CI

Add a lightweight test dependency file and a GitHub Actions workflow for Python 3.11.
CI runs the complete unit/API suite, byte-compilation, and whitespace validation without
downloading TensorFlow or model weights. Full ML dependencies remain in the production
requirements file and Docker image. A separate container job builds that production image,
starts it with the same command used for deployment, polls `/health` through the published
port, validates the response contract, prints container logs on failure, and always removes
the test container. Keeping the jobs separate preserves fast Python feedback while making
the full delivery artifact a required, observable acceptance boundary.

## Error Handling

- Invalid fusion configuration raises `ValueError` at construction.
- Invalid observation confidence degrades to `0.0`; invalid timestamps normalize to the
  ingestion time instead of failing an API request.
- API query violations return FastAPI's standard `422` response.
- Evidence persistence failure is logged and does not discard the behavior result.

## Acceptance Criteria

1. Audio and visual observations fuse only for the same pet and within the configured time.
2. Fusion state expires according to real/injected time and malformed timestamps do not
   crash ingestion.
3. Histories are per-pet, bounded, and query limits are validated.
4. Audio and visual API paths persist the correct event/evidence and expose fusion output.
5. Event listing without `pet_id` is not implicitly filtered by `PET_ID`.
6. Authentication imports without the Python `crypt` deprecation and uses no deprecated
   project-owned UTC calls.
7. The full test suite, byte compilation, diff checks, application import smoke test,
   production Docker build, and container `/health` smoke test pass.
8. Design, implementation, acceptance evidence, and remaining limitations are documented.

## Out of Scope

- Durable fusion history and database migration
- Continuous camera analysis workers
- User-level Pet/Event authorization
- Model accuracy validation requiring YAMNet/YOLO datasets or physical cameras
- HTTPS, rate limiting, and production secret management
