"""HTTP API request handler."""

import hashlib
import hmac
import json
from datetime import UTC, datetime
from enum import Enum
from types import TracebackType
from typing import Any, Self
from urllib.parse import urlencode

from aiohttp import ClientError, ClientSession, ClientTimeout

OK_CODE = 200
HTTP_TIMEOUT_SECONDS = 15


class ServerType(Enum):
    """Enum for server types."""

    SPOT = 0
    FUTURES = 1


class ApiRequestError(Exception):
    """Exception raised when API request fails."""

    def __init__(self, info_text: str, payload: dict | None) -> None:
        """Initialize API request error."""
        error_message = info_text
        if payload:
            error_message += "\n"
            error_message += json.dumps(payload, indent=2)
        super().__init__(error_message)


class ApiRateStore:
    """Window-owned API usage records."""

    def __init__(self) -> None:
        """Initialize API usage records."""
        self.used_rates: dict[str, tuple[str, datetime]] = {}


class ApiRequester:
    """HTTP API requester for Binance and CoinGecko."""

    def __init__(self, rate_store: ApiRateStore | None = None) -> None:
        """Initialize API requester."""
        self._session: ClientSession | None = None
        self._rate_store = rate_store if rate_store is not None else ApiRateStore()
        self._binance_api_key = ""
        self._binance_api_secret = ""

    async def __aenter__(self) -> Self:
        """Enter the requester session scope."""
        if self._session is None or self._session.closed:
            self._session = ClientSession(
                timeout=ClientTimeout(total=HTTP_TIMEOUT_SECONDS),
            )
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Close the owned HTTP session."""
        del exc_type, exc, traceback
        await self._close()

    @property
    def used_rates(self) -> dict[str, tuple[str, datetime]]:
        """Get API usage records for this requester's rate store."""
        return self._rate_store.used_rates

    async def _close(self) -> None:
        """Close the owned HTTP session."""
        session = self._session
        if session is None or session.closed:
            return
        await session.close()

    def _require_session(self) -> ClientSession:
        session = self._session
        if session is None or session.closed:
            msg = "ApiRequester is not entered"
            raise RuntimeError(msg)
        return session

    def update_keys(self, binance_api_key: str, binance_api_secret: str) -> None:
        """Update Binance API keys."""
        self._binance_api_key = binance_api_key
        self._binance_api_secret = binance_api_secret

    async def binance(
        self,
        http_method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        server_type: ServerType = ServerType.FUTURES,
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

        match server_type:
            case ServerType.SPOT:
                url = "https://api.binance.com"
            case ServerType.FUTURES:
                url = "https://fapi.binance.com"
        url += path
        url += "?" + query_string + "&signature=" + signature

        session = self._require_session()
        async with session.request(http_method, url, headers=headers) as raw:
            response = await raw.json()

        # record api usage
        for header_key in raw.headers:
            if "X-MBX" in header_key:
                write_value = raw.headers[header_key]
                current_time = datetime.now(UTC)
                self._rate_store.used_rates[header_key] = (write_value, current_time)

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

        try:
            session = self._require_session()
            async with session.request(http_method, url) as raw:
                return await raw.json()
        except (ClientError, OSError, TimeoutError) as error:
            text = f"{error.__class__.__name__}\n{url}"
            raise ApiRequestError(text, None) from error

    async def bytes(self, url: str) -> bytes:
        """Fetch bytes from URL."""
        headers = {
            "User-agent": "Mozilla/5.0",
        }

        try:
            session = self._require_session()
            async with session.request("GET", url, headers=headers) as raw:
                response = await raw.read()
                status_code = raw.status
                is_ok = raw.ok
        except (ClientError, OSError, TimeoutError) as error:
            text = f"{error.__class__.__name__}\n{url}"
            raise ApiRequestError(text, None) from error

        if not is_ok:
            text = f"HTTP {status_code}\n{url}"
            raise ApiRequestError(text, None)

        return response
