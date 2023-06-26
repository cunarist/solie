import platform
from urllib import request
import tempfile
import subprocess
import os
import logging

from module import introduction
from module.instrument.api_requester import ApiRequester
from module.recipe import compare_versions
from module.recipe import check_internet

_latest_version = "0.0"


def is_newer_version_available():
    global _latest_version

    if not check_internet.connected():
        return

    api_requester = ApiRequester()
    payload = {"id": "version"}
    response = api_requester.cunarist("GET", "/api/solie/latest-version", payload)
    _latest_version = response["value"]

    if compare_versions.do(_latest_version, introduction.CURRENT_VERSION):
        return True
    else:
        return False


def get_latest_version():
    return _latest_version
