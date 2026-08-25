# AI Agent Handoff Harness extension

This nested source distribution builds one dependency-free extension wheel for explicit
inspection and approval by Agentic Security Harness Distribution Discovery V1.

The wheel deliberately has no `Requires-Dist`. Discovery V1 rejects dependency-bearing
extensions, so the operator must install and verify `ai-agent-handoff>=0.2,<1` and the
future published `agentic-security-harness>=1.3,<2` environment separately. The exact
pre-1.3 Harness source candidate used by this repository's compatibility CI is pinned in
`contracts/harness-extension-v1.manifest.json`; it is test evidence, not a released
package-version claim.

The V1 factory is narrower than the compatibility range: it accepts only Handoff 0.2.0
with the three exact canonical-LF public runtime-file digests recorded in
`ash-extension-config.json`. LF and CRLF source materializations commit to the same text;
bare CR bytes are rejected.
It rejects an already-loaded `agent_guard` namespace, verifies those files before import,
binds all import origins, and verifies the bytes again after import. This closes ambient
module and alternate-path execution at the approval-to-factory boundary.

Install the built extension wheel into the explicit inspection directory with bytecode
generation disabled:

```bash
python -m pip install --no-index --no-deps --no-compile --target /safe/extension-root ./dist/ai_agent_handoff_harness_extension-1.0.0-py3-none-any.whl
```

Without `--no-compile`, pip may add interpreter-specific bytecode and RECORD entries that
the closed six-file Harness inspector correctly rejects.

The entry point is `ai-agent-handoff.validation` in the fixed
`agentic_security_harness.extensions.v1` group. It consumes canonical content-free
portfolio observations, revalidates them with the exact-bound source-owned deterministic
Handoff codec, and returns separately attributed advisory findings with operational authority `none`. It never accepts
handoff bodies, paths, credentials, providers, or network access.
