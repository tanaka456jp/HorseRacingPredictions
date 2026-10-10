from pathlib import Path


WORKFLOW = Path(
    ".github/workflows/phase11-bounded-jravan-self-hosted.yml"
)


def _text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_phase11_bounded_workflow_is_manual_only():
    text = _text()
    assert "workflow_dispatch:" in text
    assert "\n  push:" not in text
    assert "\n  schedule:" not in text


def test_phase11_bounded_workflow_defaults_to_no_provider_read():
    text = _text()
    assert "execute:" in text
    assert "zero_cost_entitlement_confirmed:" in text
    assert "personal_research_rights_confirmed:" in text
    assert text.count("default: false") >= 3
    assert "Execution blocked: zero-cost entitlement" in text
    assert "Execution blocked: personal research rights" in text


def test_phase11_bounded_workflow_uses_pre2025_setup_sentinel():
    text = _text()
    assert 'default: "20170101000000-20249999999999"' in text
    assert "20250101000000" not in text
    assert "2025-2026" not in text


def test_phase11_bounded_workflow_never_uploads_raw_provider_records():
    text = _text()
    upload_section = text.split(
        "- name: Publish sanitized plan/evidence only",
        maxsplit=1,
    )[1]
    assert "artifacts/phase11_jravan_bounded_plan.json" in upload_section
    assert "artifacts/phase11_jravan_bounded_summary.json" in upload_section
    assert "data\\jravan" not in upload_section
    assert "race_raw.jsonl" not in upload_section
