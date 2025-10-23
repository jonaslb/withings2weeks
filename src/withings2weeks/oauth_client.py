"""Minimal Withings OAuth2 client.

Implements the authorization-code flow with a local HTTP callback server
listening on the redirect_uri host/port.

NOTE: Endpoint action names ("requesttoken", "refresh") based on public docs.
Verify against latest Withings API reference before production use.
"""

import contextlib
import json
import secrets
import threading
import time
import webbrowser
from collections.abc import Mapping
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

import requests

from .config import get_app_config_path, get_token_path, load_app_config

# Configuration and token paths now resolved via config module (XDG-aware).
AUTH_BASE = "https://account.withings.com/oauth2_user/authorize2"
TOKEN_ENDPOINT = "https://wbsapi.withings.net/v2/oauth2"


@dataclass
class OAuthTokens:
    access_token: str
    refresh_token: str
    expires_at: float  # epoch seconds
    scope: str
    userid: int | None = None

    @property
    def expired(self) -> bool:
        # Refresh slightly early (30s safety window)
        return time.time() >= (self.expires_at - 30)

    def to_dict(self) -> dict[str, object]:
        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "expires_at": self.expires_at,
            "scope": self.scope,
            "userid": self.userid,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> OAuthTokens:
        expires_raw = data.get("expires_at")
        if isinstance(expires_raw, (int, float, str)):
            try:
                expires_at = float(expires_raw)
            except ValueError:
                expires_at = time.time()  # fallback now
        else:
            expires_at = time.time()
        userid_raw = data.get("userid")
        userid: int | None
        if isinstance(userid_raw, (int, str)):
            try:
                userid = int(userid_raw)
            except ValueError:
                userid = None
        else:
            userid = None
        return cls(
            access_token=str(data.get("access_token", "")),
            refresh_token=str(data.get("refresh_token", "")),
            expires_at=expires_at,
            scope=str(data.get("scope", "")),
            userid=userid,
        )


class _CodeCaptureHandler(BaseHTTPRequestHandler):
    """HTTP handler capturing the authorization code from query params."""

    # Shared storage (updated before server start)
    code_container: dict[str, str] = {}

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        if "code" in params:
            self.code_container["code"] = params["code"][0]
            body = b"Authorization successful. You can close this window."
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            body = b"No authorization code found."
            self.send_response(400)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A003,D401
        # Silence default logging to stderr
        return


class WithingsOAuthClient:
    def __init__(self, client_id: str, client_secret: str, redirect_uri: str) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri

    @staticmethod
    def from_config(path: str | Path | None = None) -> WithingsOAuthClient:
        """Instantiate client from TOML config.

        If ``path`` is omitted, resolves the default XDG-aware config path.
        """
        if path is None:
            path = get_app_config_path()
        data = load_app_config(Path(path))
        oauth = data.get("withings", {}).get("oauth", {})
        try:
            client_id = oauth["client_id"]
            client_secret = oauth["client_secret"]
            redirect_uri = oauth["redirect_uri"]
        except KeyError as e:  # noqa: PERF203
            raise KeyError(f"Missing required oauth config key: {e}") from e
        return WithingsOAuthClient(client_id, client_secret, redirect_uri)

    def build_authorization_url(self, scopes: list[str], state: str) -> str:
        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "scope": ",".join(scopes),  # Withings expects comma-separated scopes
            "state": state,
            "redirect_uri": self.redirect_uri,
        }
        return f"{AUTH_BASE}?{urlencode(params)}"

    def _run_local_server_for_code(self, timeout: int = 120) -> str:
        """Start a tiny HTTP server and wait for the authorization code."""
        parsed = urlparse(self.redirect_uri)
        host = parsed.hostname or "localhost"
        port = parsed.port or 80
        code_holder: dict[str, str] = {}
        _CodeCaptureHandler.code_container = code_holder
        server = HTTPServer((host, port), _CodeCaptureHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        start = time.time()
        while "code" not in code_holder and (time.time() - start) < timeout:
            time.sleep(0.25)
        server.shutdown()
        if "code" not in code_holder:
            raise TimeoutError("Did not receive authorization code in time")
        return code_holder["code"]

    def exchange_code_for_tokens(self, code: str) -> OAuthTokens:
        """Exchange authorization code for access & refresh tokens."""
        payload = {
            "action": "requesttoken",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.redirect_uri,
        }
        resp = requests.post(TOKEN_ENDPOINT, data=payload, timeout=30)
        if resp.status_code != 200:
            raise RuntimeError(f"Token endpoint HTTP {resp.status_code}: {resp.text}")
        data: dict[str, Any] = resp.json()
        if data.get("status") != 0:
            raise RuntimeError(f"Token request failed: {data}")
        body: dict[str, Any] = data.get("body", {})
        expires_in = int(body.get("expires_in", 0))
        raw_userid = body.get("userid")
        userid = int(raw_userid) if isinstance(raw_userid, (int, str)) else None
        tokens = OAuthTokens(
            access_token=str(body["access_token"]),
            refresh_token=str(body["refresh_token"]),
            expires_at=time.time() + expires_in,
            scope=str(body.get("scope", "")),
            userid=userid,
        )
        self._save_tokens(tokens)
        return tokens

    def refresh_access_token(self, tokens: OAuthTokens) -> OAuthTokens:
        """Use refresh token to obtain a new access token."""
        payload = {
            "action": "requesttoken",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "refresh_token",
            "refresh_token": tokens.refresh_token,
        }
        resp = requests.post(TOKEN_ENDPOINT, data=payload, timeout=30)
        if resp.status_code != 200:
            raise RuntimeError(f"Refresh endpoint HTTP {resp.status_code}: {resp.text}")
        data: dict[str, Any] = resp.json()
        if data.get("status") != 0:
            raise RuntimeError(f"Refresh failed: {data}")
        body: dict[str, Any] = data.get("body", {})
        expires_in = int(body.get("expires_in", 0))
        raw_userid = body.get("userid")
        userid = int(raw_userid) if isinstance(raw_userid, (int, str)) else tokens.userid
        new_tokens = OAuthTokens(
            access_token=str(body["access_token"]),
            refresh_token=str(body.get("refresh_token", tokens.refresh_token)),
            expires_at=time.time() + expires_in,
            scope=str(body.get("scope", tokens.scope)),
            userid=userid,
        )
        self._save_tokens(new_tokens)
        return new_tokens

    def get_valid_access_token(self) -> str:
        tokens = self._load_tokens()
        if tokens is None:
            raise RuntimeError("No stored tokens; run authorization flow first.")
        if tokens.expired:
            tokens = self.refresh_access_token(tokens)
        return tokens.access_token

    def authorize_interactive(self, scopes: list[str]) -> OAuthTokens:
        state = secrets.token_hex(16)
        url = self.build_authorization_url(scopes=scopes, state=state)
        print("Open (or opened) browser to authorize:")
        print(url)
        with contextlib.suppress(Exception):
            webbrowser.open(url)
        code = self._run_local_server_for_code()
        print("Received authorization code; exchanging for tokens...")
        tokens = self.exchange_code_for_tokens(code)
        print("Authorization complete. Tokens stored.")
        return tokens

    def _save_tokens(self, tokens: OAuthTokens) -> None:
        path = get_token_path()
        path.write_text(json.dumps(tokens.to_dict(), indent=2))

    def _load_tokens(self) -> OAuthTokens | None:
        path = get_token_path()
        if not path.exists():
            return None
        data = json.loads(path.read_text())
        return OAuthTokens.from_dict(data)


__all__ = ["WithingsOAuthClient", "OAuthTokens"]
