"""Two discovery platforms share the same persistence and identity rules."""

import json
from pathlib import Path

import httpx

from fdh.cli.main import main
from tests.integration.test_discover_cli import Provider, config, query


def test_two_platforms_keep_independent_identities(migrated: str, tmp_path: Path) -> None:
    path = Path(config(tmp_path, "budget"))
    second = path.read_text().replace('source_id = "alpha"', 'source_id = "beta"')
    second = second.replace('platform = "socrata"', 'platform = "data360"')
    second = second.replace('[sources.options]\ndomains = "data.example.org"\n', "")
    path.write_text(path.read_text() + second)
    socrata = Provider({"budget": ["shared-id"]})

    def respond(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return socrata(request)
        body = json.loads(request.content)
        assert body["filter"] == "type eq 'dataset'"
        assert body["skip"] == 0
        return httpx.Response(
            200,
            json={
                "@odata.count": 1,
                "value": [
                    {
                        "idno": "shared-id",
                        "type": "dataset",
                        "series_description": {"name": "Synthetic Data360"},
                    }
                ],
            },
        )

    transport = httpx.MockTransport(respond)
    for _ in range(2):
        assert main(["discover", "--all", "--config", str(path)], transport=transport) == 0
    assert query(
        migrated, "SELECT source_id, external_id FROM datasets ORDER BY source_id"
    ) == [("alpha", "shared-id"), ("beta", "shared-id")]
    assert query(migrated, "SELECT count(*) FROM dataset_observations") == [(4,)]
    assert query(migrated, "SELECT count(*) FROM runs WHERE status = 'succeeded'") == [(4,)]
