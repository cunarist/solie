"""HTTP API request handler."""

import hashlib
import hmac
import json
from datetime import UTC, datetime
from typing import Any, ClassVar
from urllib.parse import urlencode

from aiohttp import ClientSession

from solie.common import spawn

OK_CODE = 200


class ApiRequestError(Exception):
    """Exception raised when API request fails."""

    def __init__(self, info_text: str, payload: dict | None) -> None:
        """Initialize API request error."""
        error_message = info_text
        if payload:
            error_message += "\n"
            error_message += json.dumps(payload, indent=2)
        super().__init__(error_message)


class ApiRequester:
    """HTTP API requester for Binance and CoinGecko."""

    used_rates: ClassVar[dict[str, tuple[str, datetime]]] = {}

    def __init__(self) -> None:
        """Initialize API requester."""
        self._session = ClientSession()
        self._binance_api_key = ""
        self._binance_api_secret = ""

    def __del__(self) -> None:
        """Clean up session on deletion."""
        spawn(self._session.close())

    def update_keys(self, binance_api_key: str, binance_api_secret: str) -> None:
        """Update Binance API keys."""
        self._binance_api_key = binance_api_key
        self._binance_api_secret = binance_api_secret

    async def binance(
        self,
        http_method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        server: str = "futures",
    ) -> Any:
        """Make request to Binance API."""
        query_string = urlencode(payload or {})
        # replace single quote to double quote
        query_string = query_string.replace("%27", "%22")

        signature = hmac.new(
            self._binance_api_secret.encode("utf-8"),
            query_string.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        headers = {"X-MBX-APIKEY": self._binance_api_key}

        if server == "spot":
            url = "https://api.binance.com"
        elif server == "futures":
            url = "https://fapi.binance.com"
        else:
            msg = "This Binance server is not supported"
            raise ValueError(msg)
        url += path
        url += "?" + query_string + "&signature=" + signature

        async with self._session.request(http_method, url, headers=headers) as raw:
            response = await raw.json()

        # record api usage
        for header_key in raw.headers:
            if "X-MBX" in header_key:
                write_value = raw.headers[header_key]
                current_time = datetime.now(UTC)
                self.used_rates[header_key] = (write_value, current_time)

        # check if the response contains error message
        if "code" in response and response["code"] != OK_CODE:
            error_code = response["code"]
            error_message = response["msg"]
            text = f"Binance error code {error_code}\n{error_message}"
            raise ApiRequestError(text, payload)

        return response

    async def coingecko(
        self,
        http_method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> Any:
        """Make request to CoinGecko API."""
        query_string = urlencode(payload or {})
        # replace single quote to double quote
        query_string = query_string.replace("%27", "%22")

        url = "https://api.coingecko.com" + path + "?" + query_string

        async with self._session.request(http_method, url) as raw:
            return await raw.json()

    async def bytes(self, url: str) -> bytes:
        """Fetch bytes from URL."""
        headers = {
            "User-agent": "Mozilla/5.0",
        }

        async with self._session.request("GET", url, headers=headers) as raw:
            response = await raw.read()

        status_code = raw.status
        if not raw.ok:
            text = f"HTTP {status_code}\n{url}"
            raise ApiRequestError(text, None)

        return response
