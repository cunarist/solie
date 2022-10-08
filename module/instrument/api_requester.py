import hashlib
import hmac
from urllib.parse import urlencode
import json
from datetime import datetime, timezone

import requests

from module.instrument.api_request_error import ApiRequestError
from module.recipe import datalocks


class ApiRequester:
    _SESSION_COUNT = 64
    used_rates = {}
    _sessions = [requests.Session() for _ in range(_SESSION_COUNT)]

    def __init__(self):
        self.keys = {
            "binance_api": "",
            "binance_secret": "",
        }

    def _request(self, http_method, parameters):
        attempt = 0
        while True:
            slot = attempt % self._SESSION_COUNT
            if datalocks.hold(f"request_session_{slot}").locked():
                attempt += 1
            else:
                break
        with datalocks.hold(f"request_session_{slot}"):
            if http_method == "GET":
                raw_response = self._sessions[slot].get(**parameters)
            elif http_method == "DELETE":
                raw_response = self._sessions[slot].delete(**parameters)
            elif http_method == "PUT":
                raw_response = self._sessions[slot].put(**parameters)
            elif http_method == "POST":
                raw_response = self._sessions[slot].post(**parameters)

        return raw_response

    def update_keys(self, keys):
        self.keys.update(keys)

    def binance(self, http_method, path, payload={}, server="futures"):
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
        url += path
        url += "?" + query_string + "&signature=" + signature

        parameters = {"url": url, "headers": headers}
        raw_response = self._request(http_method, parameters)

        # decode to json
        try:
            response = raw_response.json()
        except json.decoder.JSONDecodeError:
            status_code = raw_response.status_code
            text = "There was a problem with Binance API request"
            text += f" (HTTP {status_code})"
            raise ApiRequestError(text)

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

    def coinstats(self, http_method, path, payload={}):
        query_string = urlencode(payload)
        # replace single quote to double quote
        query_string = query_string.replace("%27", "%22")

        url = "https://api.coinstats.app" + path + "?" + query_string
        parameters = {"url": url}
        raw_response = self._request(http_method, parameters)
        response = raw_response.json()

        return response

    def cunarist(self, http_method, path, payload={}):
        query_string = urlencode(payload)
        # replace single quote to double quote
        query_string = query_string.replace("%27", "%22")

        url = "https://cunarist.com" + path + "?" + query_string
        parameters = {"url": url}
        raw_response = self._request(http_method, parameters)
        response = raw_response.json()

        status_code = raw_response.status_code
        if status_code != 200:
            text = f"There was a problem with Cunarist API request (HTTP {status_code})"
            text += "\n"
            text += response["message"]
            raise ApiRequestError(text)

        return response
