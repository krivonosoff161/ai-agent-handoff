import hashlib
import json
from pathlib import Path


def test_security_portfolio_contract() -> None:
    root = Path(__file__).resolve().parents[1]
    contract = json.loads(
        (root / "docs" / "security-portfolio-roadmap-contract.json").read_text(encoding="utf-8")
    )
    assert contract["schema_version"] == "SecurityPortfolioLocalContract.v2"
    assert contract["repository_id"] == "ai-agent-handoff"
    path = (root / contract["vendored_projection_path"]).resolve()
    assert root.resolve() in path.parents and path.is_file() and not path.is_symlink()
    raw = path.read_bytes()
    assert len(raw) == contract["public_projection_size"]
    assert hashlib.sha256(raw).hexdigest() == contract["public_projection_sha256"]
    projection = json.loads(raw)
    assert projection["roadmap_version"] == contract["roadmap_version"]
    assert projection["source_sha256"] == contract["upstream_private_source_sha256"]
    repository = next(
        item for item in projection["repositories"] if item["id"] == contract["repository_id"]
    )
    assert repository["roadmap_authority"] == contract["roadmap_authority"]
    owned = [
        {"id": item["id"], "status": item["status"]}
        for item in projection["modules"]
        if item["owner"] == contract["repository_id"]
    ]
    forbidden = sorted(
        {
            claim
            for item in projection["modules"]
            if item["owner"] == contract["repository_id"]
            for claim in item["forbidden_claims"]
        }
        | {"operational_authority"}
    )
    assert projection["authority"] == contract["authority"] == "none"
    assert contract["owned_modules"] == owned
    assert contract["forbidden_promotions"] == forbidden
    assert all(
        projection["status_profiles"][item["status"]]["authority"] == contract["authority"]
        for item in owned
    )


def test_human_contract_matches_machine_pin() -> None:
    root = Path(__file__).resolve().parents[1]
    contract = json.loads(
        (root / "docs" / "security-portfolio-roadmap-contract.json").read_text(
            encoding="utf-8"
        )
    )
    document = (root / "docs" / "security-portfolio-roadmap.md").read_text(encoding="utf-8")
    assert contract["roadmap_version"] in document
    assert all(
        item["id"] in document and item["status"] in document
        for item in contract["owned_modules"]
    )
    assert "`none`" in document
