import base64
import json
import time

import requests
from django.conf import settings
from django.core.cache import cache


class PRPApiError(Exception):
    pass


class PRPApiClient:
    """
    HTTP client for the PRP (Parliament Resource Portal) external API.

    Handles JWT authentication and transparent token refresh. The Bearer token
    is cached in Django's cache backend — shared across workers so we don't
    re-authenticate on every Celery task invocation.
    """

    BASE_URL = "https://prp.parliament.gov.bd"
    _TOKEN_CACHE_KEY = "prp_api_bearer_token"

    # ── Authentication ────────────────────────────────────────────────────────

    def authenticate(self) -> str:
        """Return a valid Bearer token, fetching from API if cache is empty."""
        cached = cache.get(self._TOKEN_CACHE_KEY)
        if cached:
            return cached
        return self._fetch_token()

    def _fetch_token(self) -> str:
        try:
            resp = requests.post(
                f"{self.BASE_URL}/api/authentication/external",
                params={"action": "token"},
                json={
                    "username": settings.PRP_API_USERNAME,
                    "password": settings.PRP_API_PASSWORD,
                },
                timeout=30,
            )
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise PRPApiError(f"Auth request failed: {exc}") from exc

        data = resp.json()
        if data.get("responseCode") != 200:
            raise PRPApiError(f"Auth rejected by PRP API: {data.get('msg')}")

        token: str = data["payload"]
        cache.set(self._TOKEN_CACHE_KEY, token, timeout=self._token_ttl(token))
        return token

    @staticmethod
    def _token_ttl(token: str) -> int:
        """
        Decode JWT exp claim without signature verification and return
        seconds until expiry minus a 60-second safety buffer.
        """
        try:
            # JWT = header.payload.signature — we only need the middle part
            raw = token.split(".")[-2]  # handles "Bearer eyJ..." and raw JWT
            if raw.startswith("Bearer"):
                raw = token.replace("Bearer ", "").split(".")[1]
            raw += "=" * (-len(raw) % 4)
            payload = json.loads(base64.urlsafe_b64decode(raw))
            exp = int(payload.get("exp", 0))
            return max(exp - int(time.time()) - 60, 60)
        except Exception:
            return 3600

    # ── Data endpoints ────────────────────────────────────────────────────────

    def get_employees(self) -> list:
        return self._get("employeeInformations")

    def get_mps(self) -> list:
        return self._get("mpInformations")

    def get_offices(self) -> list:
        return self._get("offices")

    # ── HTTP helpers ──────────────────────────────────────────────────────────

    def _get(self, action: str) -> list:
        token = self.authenticate()
        resp = self._raw_get(action, token)

        if resp.status_code == 401:
            # Token may have expired between requests — clear cache and retry once
            cache.delete(self._TOKEN_CACHE_KEY)
            token = self._fetch_token()
            resp = self._raw_get(action, token)

        try:
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise PRPApiError(f"GET {action} failed ({resp.status_code}): {exc}") from exc

        data = resp.json()
        if data.get("responseCode") != 200:
            raise PRPApiError(f"PRP API error for '{action}': {data.get('msg')}")
        return data.get("payload") or []

    def _raw_get(self, action: str, token: str) -> requests.Response:
        return requests.get(
            f"{self.BASE_URL}/api/secure/external",
            params={"action": action},
            headers={"Authorization": token},
            timeout=60,
        )
