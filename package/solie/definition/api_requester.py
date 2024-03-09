import hashlib
import hmac
from datetime import datetime, timezone
from urllib.parse import urlencode

import aiohttp

from solie.definition.errors import ApiRequestError


class ApiRequester:
    used_rates = {}

    def __init__(self):
        self.keys = {
            "binance_api": "",
            "binance_secret": "",
        }

    def update_keys(self, keys):
        self.keys.update(keys)

    async def binance(
        self, http_method: str, path: str, payload: dict = {}, server="futures"
    ):
        query_string = urlencode(payload)
        # replace single quote to double quote
        query_string = query_string.replace("%27", "%22")

        signature = hmac.new(
            self.keys["binance_secret"].encode("utf-8"),
            query_string.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        headers = {"X-MBX-APIKEY": self.keys["binance_api"]}

        if server == "spot":
            url = "https://api.binance.com"
        elif server == "futures":
            url = "https://fapi.binance.com"
        else:
            raise ApiRequestError("This Binance server is supported")
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
            text = "There was a problem with Binance API request"
            text += f" (Error {error_code}: {error_message})"
            raise ApiRequestError(text)

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
            text = f"There was a problem with bytes request (HTTP {status_code})"
            text += "\n"
            text += url
            raise ApiRequestError(text)

        return response
