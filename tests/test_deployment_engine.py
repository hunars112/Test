"""Tests for the full site deployment engine."""
from pathlib import Path

from authority_site_engine.modules.deployment import DeploymentEngine
from authority_site_engine.modules.posting import WordPressPostingEngine

from tests.factories import (
    FakeCloudflareClient,
    FakeCommandRunner,
    FakeWordPressClient,
    prepare_project,
)


def test_deployment_engine_runs_pipeline(tmp_path: Path) -> None:
    project_data, project_root = prepare_project(tmp_path)
    fake_wp = FakeWordPressClient()
    fake_cf = FakeCloudflareClient()
    cmd_runner = FakeCommandRunner()
    project_data.deployment.install_wordpress = False
    project_data.deployment.theme_slug = "twentytwentythree"
    project_data.deployment.plugin_slugs = ["classic-editor"]
    project_data.deployment.ping_sitemaps = False

    engine = DeploymentEngine(
        project_data,
        project_root,
        client=fake_wp,
        cloudflare_client=fake_cf,
        command_runner=cmd_runner,
        posting_engine_cls=WordPressPostingEngine,
    )
    summary = engine.run()

    assert summary["cloudflare"]["success"]
    assert summary["content"]["success"]
    assert fake_cf.records, "DNS records should be planned"
    assert fake_wp.created_posts, "Posting engine should create posts"
    status_path = project_root / "outputs" / "content" / "deployment_status.json"
    assert status_path.exists()
    assert "cloudflare" in status_path.read_text()
    log_path = project_root / "outputs" / "logs" / "deployment_engine.log"
    assert log_path.exists()


def test_deployment_engine_dry_run(tmp_path: Path) -> None:
    project_data, project_root = prepare_project(tmp_path)
    fake_wp = FakeWordPressClient()
    fake_cf = FakeCloudflareClient()
    cmd_runner = FakeCommandRunner()

    engine = DeploymentEngine(
        project_data,
        project_root,
        client=fake_wp,
        cloudflare_client=fake_cf,
        command_runner=cmd_runner,
    )
    summary = engine.run(dry_run=True)

    assert summary["cloudflare"]["success"]
    assert summary["content"]["success"]
    assert not fake_wp.created_posts, "Dry-run should not create posts"
    assert not cmd_runner.commands, "Dry-run should skip command execution"
