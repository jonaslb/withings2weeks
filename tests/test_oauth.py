import os
import time
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from withings2weeks.oauth_client import OAuthTokens, WithingsOAuthClient


def test_authorization_url_build(tmp_path: Path) -> None:
    cfg = tmp_path / "app_config.toml"
    cfg.write_text(
        """[withings.oauth]\nclient_id='cid123'\nclient_secret='secret456'\nredirect_uri='http://localhost:1992/callback'\n"""
    )
    client = WithingsOAuthClient.from_config(cfg)
    url = client.build_authorization_url(["user.info", "user.metrics"], state="xyzSTATE")
    parsed = urlparse(url)
    assert parsed.scheme == "https"
    assert parsed.netloc == "account.withings.com"
    qs = parse_qs(parsed.query)
    assert qs["client_id"][0] == "cid123"
    assert qs["state"][0] == "xyzSTATE"
    assert qs["scope"][0] == "user.info,user.metrics"  # comma separated per API


def test_token_persistence(tmp_path: Path) -> None:
    # Work in isolated directory so token file writes do not pollute repo
    # Point config dir to tmp_path to isolate token persistence
    orig_cfg_dir = os.environ.get("WITHINGS2WEEKS_CONFIG_DIR")
    os.environ["WITHINGS2WEEKS_CONFIG_DIR"] = str(tmp_path)
    try:
        client = WithingsOAuthClient("id", "secret", "http://localhost:1992/callback")
        tokens = OAuthTokens(
            access_token="ACCESS123",
            refresh_token="REFRESH456",
            expires_at=time.time() + 3600,
            scope="user.info",
            userid=42,
        )
        client._save_tokens(tokens)  # noqa: SLF001 (intentional test of private method)
        loaded = client._load_tokens()
        assert loaded is not None
        assert loaded.access_token == "ACCESS123"
        assert loaded.refresh_token == "REFRESH456"
        assert loaded.userid == 42
        # Ensure file landed in config dir
        token_path = tmp_path / ".withings_tokens.json"
        assert token_path.exists()
    finally:
        if orig_cfg_dir is not None:
            os.environ["WITHINGS2WEEKS_CONFIG_DIR"] = orig_cfg_dir
        else:
            os.environ.pop("WITHINGS2WEEKS_CONFIG_DIR", None)
