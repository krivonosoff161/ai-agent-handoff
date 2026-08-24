# Package and CI contract

`ai-agent-handoff` has two distribution surfaces with intentionally different content:

- the wheel installs the dependency-free `agent_guard` Python API and the `agent-guard`
  console entry point;
- the source distribution also carries protocol templates, examples, contracts,
  reviewer documentation, configuration examples, and the synthetic self-test surface.

For Python 3.9, 3.10, 3.11, and 3.12, CI runs on Ubuntu and Windows and performs the
complete checkout test suite, independent sdist and wheel builds, bounded archive
path/link/size and required-content checks, the shipped tests from a safely reconstructed
sdist tree, and an isolated no-dependency wheel installation. The installed smoke checks
canonical metadata round-trip plus `agent-guard` ask, deny, allow, and malformed-input
channels from outside the source checkout.

A separate Ubuntu quality job runs Ruff, default mypy, Bandit medium/high checks, a
bounded supplemental public-tree hygiene scan, and focused source-owned/vendored contract
tests. The scan reports rule identifiers and locations, never matching values. Workflow
actions are pinned to exact commits, repository permission is read-only, and checkout
credentials are not persisted.

A separate Python 3.11/3.13 Linux/Windows matrix validates the optional nested Harness
extension. It checks out the exact source-level Distribution Discovery and lifecycle
contract, builds the dependency-free six-file wheel, safely unpacks it, proves inspection
and approval occur before explicit code loading, then constructs, binds, and runs the
extension over synthetic content-free observations. The matrix does not contact a package
index beyond installing declared test tooling, invoke a provider, or consume live data.

These checks demonstrate artifact completeness and behavior on the declared test matrix.
They do not prove absence of every secret or vulnerability, make the pattern guard a
sandbox, authenticate handoff authors, install a Harness extension, or grant operational
authority. Index publication, release tags, deployment, provider calls, and enforcement
remain separate gates.
