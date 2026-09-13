# AGENTS.md

Guide for coding agents and contributors working on crux-backend. Read
[README.md](README.md) first for what the system does. The Python package
and the CLI commands are named `konspekt`.

## Commands

```sh
uv sync                                   # Python environment
uv run pytest -q                          # Python tests
cd control-plane && npm ci                # control-plane dependencies
cd control-plane && npm test              # control-plane tests (vitest + convex-test)
cd control-plane && npm run typecheck     # tsc --noEmit -p convex
sdd lint                                  # spec gate, after every spec edit
sdd ready                                 # implementation gate, before every commit
```

Tests never touch the network. Daytona, Claude, Exa, ElevenLabs and the
worker API are replaced by fakes or stubs at their ports.

## Spec-driven development

`spec/*.md` is the source of truth. It has one partition per file:
`pipeline`, `extraction`, `analysis`, `output` and `service`, configured
in `.sdd/config.json`. The `sdd` CLI comes from
[agent-sdd](https://github.com/cyberash-dev/agent-sdd).

1. **Change the spec before the code.**
   - Find and read records with `sdd record list --partition <p>` and
     `sdd record get <partition>:<ID>`; spec files are long, so don't
     read them whole.
   - Edit `draft` or `proposed` records with `sdd record set` or
     `sdd record add`.
   - `sdd lint` must exit 0.
2. **Changing an `approved` record takes a `Delta` record.** It carries
   `target_id`, `kind`, `compatibility_action` and `baseline_version`.
   Edit the approved record in the same change.
3. **Only a human approves.** Approval goes through `sdd approve` and
   `sdd finalize`, and an agent never records an approval on its own.
   Queue records that reference each other, such as a Surface and its
   Contracts, in one plan.
4. **Cover every test obligation.** Each one gets an executable test with
   a marker next to it: `# @covers service:REQ-003` in Python,
   `/* @covers service:CON-003 */` in TypeScript. Delta records need
   markers too.
5. **Bump Surface versions.** An additive API change is a minor bump of
   the Surface. `control-plane/openapi.yaml` (`service:GEN-001`) changes
   in the same commit as the contracts it renders.
6. **`sdd ready` must exit 0 before a commit.** After committing changes
   under `src/`, `tests/` or to `pyproject.toml`, refresh the baseline
   token and commit it separately as `refresh baseline token`:
   - run `sdd token --format=json`;
   - copy the new token and commit sha into `pipeline:BL-001` in
     `spec/pipeline.md` (`reference`, `freshness_token`,
     `baseline_commit_sha`).

## Architecture

- **Python: vertical slices with hexagonal ports.** Each slice lives in
  `src/konspekt/features/<slice>/` with `domain/`, `application/`,
  `ports/inbound|outbound/` and `adapters/inbound|outbound/`.
  - Dependencies point inward, and the domain imports nothing external.
  - Normalizing a provider response belongs in its outbound adapter.
  - One public class per file, type annotations on every argument, and
    specific types (Literal, Enum, Mapping, Sequence) over generic ones.
- **Composition roots.** The pipeline's is `src/konspekt/pipeline/`
  (CLI, orchestrator, MCP server), the cloud worker's is
  `src/konspekt/worker/`.
- **Control plane.** Entry points live in `control-plane/convex/`: HTTP
  handlers in `clientApi.ts`, `workerApi.ts` and `examApi.ts`. Beside
  them: request parsing in `httpBoundary/`, vocabularies and validators
  in `model/`, the sandbox ports and Daytona adapters in `sandbox/`, and
  fakes in `test-support/`.
  - No `any`, no non-null assertions and no narrowing `as` casts; narrow
    `unknown` at the boundary instead.
- **Comments** only for a non-obvious why. In TypeScript use the block
  form `/* */`.

## Contracts that change together

- **Worker.** `src/konspekt/worker/` implements the worker API
  (`service:CON-002`) and is baked into the worker snapshot. After any
  change, rebuild the snapshot with `deploy/daytona/build_snapshot.py`
  and point `WORKER_SNAPSHOT` at it.
- **Examiner.** `konspekt-exam-turn` (`src/konspekt/features/exam/`)
  implements the turn protocol (`service:CON-004`) and is baked into the
  examiner snapshot. After any change, rebuild it with
  `deploy/daytona/build_examiner_snapshot.py` and update
  `EXAMINER_SNAPSHOT`.
  - The examiner snapshot installs the package with `pip install
    --no-deps`, so the exam slice may import only the standard library
    and `konspekt.shared.claude_cli`.
- **Result shapes.** Outline, sections, claims, quiz and cut log are
  pipeline contracts. The control plane passes them through, and
  `openapi.yaml` describes them.

## Platform pitfalls

- **Convex edge replaces 5xx bodies.** The edge in front of a Convex
  deployment swaps the body of a 502 or 504 response for its own page.
  A JSON error meant for the client uses 503 (or a 4xx) and is told
  apart by its `code`.
- **Daytona SDK must be external.** `@daytona/sdk` uploads files through
  a dynamic `form-data` import, which the Convex bundler drops, so the
  SDK is listed under `node.externalPackages` in
  `control-plane/convex.json`.
- **Daytona exec needs a shell.** Daytona command execution merges
  stderr into the result, and redirects need a shell: run
  `sh -c '... 2>file'` and keep stdout for machine-readable output.
- **Claude Code in a sandbox uses the OAuth token.** It authenticates with
  `CLAUDE_CODE_OAUTH_TOKEN`; never set `ANTHROPIC_API_KEY` there,
  because it takes precedence.
- **Proxy only for YouTube.** YouTube downloads from Daytona need the
  outbound proxy (`PROXY_URL`); Anthropic is reachable without it.

## Secrets and data

- Local keys live in `.env`, which is gitignored. Load them with
  `uv run --env-file .env ...`, and never print, log or commit their
  values.
- Service secrets live only in the Convex environment and in the sandbox
  environments the control plane creates (`service:POL-001`). An examiner
  sandbox receives `CLAUDE_CODE_OAUTH_TOKEN` and no other secret.
- The service stores no student identity.

## Commits

- The subject is imperative and at most 72 characters; the body explains
  why.
- Spec changes go in their own `spec: ...` commit ahead of the code that
  implements them.
- Don't commit run outputs (`out/`), local caches or `.env`.
