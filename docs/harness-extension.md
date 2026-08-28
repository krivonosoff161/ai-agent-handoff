# Optional Harness extension distribution

Status: source-owned review candidate; not released or automatically installed.

`extensions/harness-v1/` is a separate six-file wheel surface for the future Harness
`>=1.3,<2` package line. It leaves the standalone `ai-agent-handoff` package and its
Python 3.9+ guard unchanged. The optional extension requires Python `>=3.11,<3.14`.

Build and install the coordinated source pair explicitly:

```text
python -m build --outdir dist/core .
python -m build --outdir dist/extension extensions/harness-v1
python -m pip install --no-deps dist/core/ai_agent_handoff-0.3.0-py3-none-any.whl dist/extension/ai_agent_handoff_harness_extension-1.0.0-py3-none-any.whl
```

After separately approved publication, a Harness `handoff` extra may select these same
exact distributions. The extension itself intentionally performs no dependency resolution.

## Controlled operator sequence

1. Install and verify `ai-agent-handoff>=0.3,<1` and a compatible Harness environment.
   This V1 factory additionally requires exact Handoff 0.3.0 canonical-LF runtime bytes
   whose three digests are public in `ash-extension-config.json`. CRLF and LF source
   materializations have the same declared text commitment; a bare CR is rejected.
2. Build the nested wheel locally. It declares no `Requires-Dist`, because Harness
   Distribution Discovery V1 rejects dependency-bearing extension wheels.
3. Install it into a dedicated inspection root with
   `python -m pip install --no-index --no-deps --no-compile --target <root> <wheel>`.
   The `--no-compile` flag is required: additional bytecode and RECORD rows are outside
   the closed six-file distribution contract.
4. Supply the exact public `ash-extension-config.json` bytes to explicit distribution
   inspection and repeat the resulting inspection id for approval.
5. Only after approval, explicitly load the one named entry point and call its factory.
   Loading the entry point does not import Handoff. The factory rejects a preloaded
   `agent_guard` namespace, verifies exact runtime files, imports the bound codec, checks
   exact origins, and re-verifies the files before returning.
6. Bind the constructed object with the exact approval receipt and run it through the
   existing Extension SDK pipeline.

The configuration records `agentic-security-harness>=1.3,<2` and
`ai-agent-handoff>=0.3,<1` as operator-preflight requirements. Wheel metadata does not
enforce or resolve those dependencies. The current cross-repository test uses exact
released Harness source HEAD `c1dd69856212458ae952e43aeb2b0cc9290e8205` and its
closed file digests as compatibility evidence; it does not make the extension itself a
published package.

## Data and authority boundary

The extension sees only validated `CanonicalObservationEventV1` objects. For activities
`handoff.task` and `handoff.session`, it round-trips the canonical content-free bytes
through the Handoff repository's deterministic observation decoder/encoder and checks for
one digest-only artifact pointer plus complete telemetry. It never accepts Markdown,
handoff bodies, machine paths, credentials, provider data, injected callables, or network
access.

Results are `ExtensionFindingV1` advisories. Mixed observations are evaluated completely
and grouped into separate findings whose evidence IDs contain only the events that caused
that exact result. A valid observation may receive a `pass`
outcome inside the advisory result model, but this is not an action authorization or a
security guarantee. Missing matching observations are inconclusive. Contract drift and
missing artifact bindings are findings. Every manifest, result, run receipt, distribution
inspection, approval, and lifecycle wrapper keeps operational authority `none`.

## Verification

```bash
python tools/harness_extension_contracts.py check
python -m pytest -q tests/test_harness_extension_distribution.py
python -m build --wheel --sdist extensions/harness-v1
```

Linux and Windows CI on Python 3.11, 3.12, and 3.13 check out the exact Harness reference,
build and install the wheel with real pip using `--no-compile`, inspect and approve it
without importing code, then explicitly load the factory,
bind it through the lifecycle wrapper, and execute synthetic content-free observations.
No package index, provider, live input, or deployment surface is used.

All generated local contract bindings use explicit canonical-LF byte semantics, and
`.gitattributes` pins every bound input to LF. The actual extension manifest still binds
the raw installed implementation/configuration bytes that the closed wheel contains.
