"""Prevent destructive re-acquisition while keeping all existing research evidence."""
import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "archive_jravan_free_trial_pre2025.py"
spec = importlib.util.spec_from_file_location("jravan_archive_cli_immutable", SCRIPT)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

@pytest.mark.parametrize("evidence", [
    "latest_manifest.json", "latest_manifest_v2.json",
    "relocated_manifest_v2.json", "migration_receipt.json",
    "migration_file_hashes.json", "MOVED_TO_D.json",
    "bldn_raw.jsonl", "race_raw.jsonl", "bldn_raw.jsonl.partial",
])
def test_existing_evidence_is_untouched(tmp_path, evidence):
    root = tmp_path / "private"
    root.mkdir()
    f = root / evidence
    original = b"DO NOT OVERWRITE"
    f.write_bytes(original)
    with pytest.raises(RuntimeError, match="refuse|immutable"):
        module.assert_fresh_archive_destination(root)
    assert f.read_bytes() == original

def test_fresh_destination_allowed(tmp_path):
    module.assert_fresh_archive_destination(tmp_path / "new")
    (tmp_path / "empty").mkdir()
    module.assert_fresh_archive_destination(tmp_path / "empty")

def test_existing_file_destination_fails(tmp_path):
    file = tmp_path / "notdir"
    file.write_text("existing", encoding="utf-8")
    with pytest.raises(RuntimeError, match="not a directory"):
        module.assert_fresh_archive_destination(file)
