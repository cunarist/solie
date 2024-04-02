import hashlib
import hmac
import json
from datetime import datetime, timezone
from urllib.parse import urlencode

import aiohttp


class ApiRequestError(Exception):
    def __init__(self, info_text: str, payload: dict | None):
        error_message = info_text
        if payload:
            error_message += "\n"
            error_message += json.dumps(payload, indent=2)
        super().__init__(error_message)


class ApiRequester:
    used_rates = {}

    def __init__(self):
        self.binance_api_key = ""
        self.binance_api_secret = ""

    def update_keys(self, binance_api_key: str, binance_api_secret: str):
        self.binance_api_key = binance_api_key
        self.binance_api_secret = binance_api_secret

    async def binance(
        self, http_method: str, path: str, payload: dict = {}, server="futures"
    ):
        query_string = urlencode(payload)
        # replace single quote to double quote
        query_string = query_string.replace("%27", "%22")

        signature = hmac.new(
            self.binance_api_secret.encode("utf-8"),
            query_string.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        headers = {"X-MBX-APIKEY": self.binance_api_key}

        if server == "spot":
            url = "https://api.binance.com"
        elif server == "futures":
            url = "https://fapi.binance.com"
        else:
            raise ValueError("This Binance server is not supported")
        url += path
        url += "?" + query_string + "&signature=" + signature

        async with aiohttp.ClientSession() as session:
            async with session.request(
                method=http_method, url=url, headers=headers
            ) as raw_response:
                response = await raw_response.json()

        # record api usage
        for header_key in raw_response.headers.keys():
            if "X-MBX" in header_key:
                write_value = raw_response.headers[header_key]
                current_time = datetime.now(timezone.utc)
                self.used_rates[header_key] = (write_value, current_time)

        # check if the response contains error message
        if "code" in response and response["code"] != 200:
            error_code = response["code"]
            error_message = response["msg"]
            text = f"Binance error code {error_code}\n{error_message}"
            raise ApiRequestError(text, payload)

        return response

    async def coingecko(self, http_method: str, path: str, payload: dict = {}):
        query_string = urlencode(payload)
        # replace single quote to double quote
        query_string = query_string.replace("%27", "%22")

        url = "https://api.coingecko.com" + path + "?" + query_string

        async with aiohttp.ClientSession() as session:
            async with session.request(method=http_method, url=url) as raw_response:
                response = await raw_response.json()

        return response

    async def bytes(self, url: str):
        headers = {
            "User-agent": "Mozilla/5.0",
        }

        async with aiohttp.ClientSession() as session:
            async with session.request(
                method="GET", url=url, headers=headers
            ) as raw_response:
                response = await raw_response.read()

        status_code = raw_response.status
        if status_code != 200:
            text = f"HTTP {status_code}\n{url}"
            raise ApiRequestError(text, None)

        return response
