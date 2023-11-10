from module import introduction
from module.instrument.api_requester import ApiRequester
from module.recipe import compare_versions
from module.recipe import check_internet

_latest_version = "0.0"


def is_newer_version_available() -> bool:
    global _latest_version

    if not check_internet.connected():
        raise ConnectionError("Internet not connected, cannot check new version")

    api_requester = ApiRequester()
    payload = {"id": "version"}
    response = api_requester.cunarist("GET", "/api/solie/latest-version", payload)
    _latest_version = response["value"]

    if compare_versions.is_left_higher(_latest_version, introduction.CURRENT_VERSION):
        return True
    else:
        return False


def get_latest_version() -> str:
    return _latest_version
