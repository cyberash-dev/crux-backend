@AGENTS.md

# Claude Code notes

These notes add Claude Code specifics to AGENTS.md above; they do not
repeat it.

- **Local builds.** The project skill `.claude/skills/konspekt/SKILL.md`
  covers starting a build, mapping exit codes, polling stage artifacts in
  `out/<slug>/work/` and reading results. Use it instead of rediscovering
  the CLI.
  - A build takes 5-20 minutes: run it in the background and poll the
    artifacts; don't block on it.
- **Your own login is spent.** The pipeline and `konspekt-exam-turn` call
  `claude -p` themselves, so local runs use your own login and settings.
  - Your MCP servers and settings enlarge every such call's prompt, so
    local latency and cost are not representative.
  - Measure examiner or pipeline timings in a Daytona sandbox built from
    the snapshots in `deploy/daytona/`.
- **Spec records.** Read them with `sdd record get` rather than opening
  `spec/*.md`: the files are long and one record is usually enough.
- **Parallel subagents.** Give each agent a disjoint write set. The
  natural split is:
  - Python (`src/`, `tests/`);
  - control plane (`control-plane/convex/`);
  - `deploy/` together with `control-plane/openapi.yaml`.

  Agents must not run `git stash` or other whole-tree git commands, which
  rewrite the files other agents are editing.
- **Live checks** against the deployed API (`deploy/e2e_*.py`) and
  Daytona scripts read keys from `.env` through
  `uv run --env-file .env`. They create real sandboxes and spend
  subscription quota, so keep them short and make sure their sandboxes
  are deleted.
