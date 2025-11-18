from __future__ import annotations

import json
from pathlib import Path

from authority_site_engine.core.credentials import CredentialVault
from authority_site_engine.core.models import ProjectData
from authority_site_engine.core.task_state import TaskStateTracker
from authority_site_engine.core.version import ENGINE_VERSION
from authority_site_engine.modules.log_summary import LogSummaryModule
from authority_site_engine.modules.search import GlobalProjectSearch
from tests.factories import build_sample_project


def test_project_data_to_dict_strips_secrets(tmp_path: Path) -> None:
    project = build_sample_project(tmp_path)
    payload = project.to_dict()
    assert payload["basic_info"]["wp_password"] == ""
    assert payload["cloudflare"]["cloudflare_api_key"] == ""
    assert payload["engine_version"] == ENGINE_VERSION


def test_credential_vault_round_trip(tmp_path: Path) -> None:
    vault = CredentialVault(tmp_path / "vault.json", master_password="secret")
    identifier = vault.store_secret("proj", "wordpress", {"password": "top-secret"})
    restored = vault.retrieve_secret(identifier)
    assert restored == {"password": "top-secret"}


def test_task_state_tracker_resume(tmp_path: Path) -> None:
    tracker = TaskStateTracker(tmp_path, "posting")
    tracker.start(10, resume=False)
    tracker.advance(3)
    assert tracker.resume_index() == 4
    tracker.mark_error("boom")
    assert tracker.resume_index() == 4


def test_log_summary_module_counts(tmp_path: Path) -> None:
    log_path = tmp_path / "outputs" / "logs"
    log_path.mkdir(parents=True)
    logfile = log_path / "posting_engine.log"
    logfile.write_text("INFO ok\nERROR fail\nWARNING be careful\n", encoding="utf-8")
    summary = LogSummaryModule().summarize([logfile])
    assert summary["total_lines"] == 3
    assert summary["total_errors"] == 1
    assert summary["total_warnings"] == 1


def test_global_project_search(tmp_path: Path) -> None:
    projects_dir = tmp_path / "projects"
    project_root = projects_dir / "demo"
    project_root.mkdir(parents=True)
    settings = build_sample_project(tmp_path)
    payload = settings.to_dict()
    payload["basic_info"]["project_name"] = "Demo"
    payload["basic_info"]["niche"] = "sleep"
    (project_root / "settings.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    searcher = GlobalProjectSearch(projects_dir)
    results = searcher.search("sleep")
    assert any(result.project_name == "Demo" for result in results)
