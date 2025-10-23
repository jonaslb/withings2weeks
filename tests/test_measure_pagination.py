from typing import Any

import pandas as pd

from withings2weeks.measure_client import MeasureType, fetch_scale_measurements_all
from withings2weeks.oauth_client import OAuthTokens, WithingsOAuthClient


class DummyClient(WithingsOAuthClient):
    def __init__(self) -> None:  # type: ignore[override]
        super().__init__("id", "secret", "http://localhost:1992/callback")
        self._tokens = OAuthTokens(
            access_token="ACCESS",
            refresh_token="REFRESH",
            expires_at=9_999_999_999.0,
            scope="",
            userid=1,
        )

    def get_valid_access_token(self) -> str:  # override without refresh
        return self._tokens.access_token


def test_pagination_aggregates(monkeypatch) -> None:  # noqa: D401
    calls: list[dict[str, Any]] = []

    # Build two synthetic pages
    def fake_get(url: str, params: dict[str, Any], headers: dict[str, str], timeout: int):  # noqa: D401
        calls.append(params)
        offset = params.get("offset")
        if offset is None:
            body = {
                "measuregrps": [
                    {
                        "grpid": 1,
                        "category": 1,
                        "date": 1700000000,
                        "measures": [{"type": MeasureType.WEIGHT_KG, "value": 80000, "unit": -3}],
                    },
                ],
                "more": 1,
                "offset": 123,
            }
        else:
            body = {
                "measuregrps": [
                    {
                        "grpid": 2,
                        "category": 1,
                        "date": 1700000100,
                        "measures": [{"type": MeasureType.WEIGHT_KG, "value": 80100, "unit": -3}],
                    },
                ],
                "more": 0,
            }

        class Resp:
            status_code = 200

            def json(self_inner):  # noqa: D401
                return {"status": 0, "body": body}

            text = "OK"

        return Resp()

    monkeypatch.setattr("withings2weeks.measure_client.requests.get", fake_get)
    client = DummyClient()
    df = fetch_scale_measurements_all(
        client,
        start=pd.Timestamp("2025-01-01"),
        end=pd.Timestamp("2025-01-02"),
    )
    assert df.shape[0] == 2, df
    assert sorted(df["group_id"].tolist()) == [1, 2]
    # Confirm both pages requested (first without offset, second with offset)
    assert calls[0].get("offset") is None
    assert calls[1].get("offset") == 123
