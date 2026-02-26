from creative_automation_cli.output.manifest import CampaignManifest
from creative_automation_cli.output.metrics import RunMetrics


def test_manifest_and_metrics_serializable() -> None:
    manifest = CampaignManifest(
        campaign_id="c1",
        target_region="US",
        target_audience="a",
        message="m",
        provider="mock",
        dry_run=True,
        started_at="2026-01-01T00:00:00Z",
    )
    metrics = RunMetrics(total_products_processed=2)
    assert manifest.to_dict()["campaign_id"] == "c1"
    assert metrics.to_dict()["total_products_processed"] == 2
