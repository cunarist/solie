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
_prepared_version = "0.0"
_is_prepared = False


def get_updater_status():
    return _is_prepared


def prepare():
    global _latest_version
    global _prepared_version
    global _is_prepared

    if not check_internet.connected():
        return

    api_requester = ApiRequester()
    payload = {"id": "version"}
    response = api_requester.cunarist("GET", "/api/solie/latest-version", payload)
    _latest_version = response["value"]

    if _is_prepared:
        temp_folder = tempfile.gettempdir()

        if platform.system() == "Windows":
            filepath = temp_folder + "/SolieWindowsSetup.exe"
        elif platform.system() == "Linux":
            pass
        elif platform.system() == "Darwin":  # macOS
            pass

        if not os.path.isfile(filepath):
            # when temp directory is cleaned up for some reason...
            _is_prepared = False
            _prepared_version = "0.0"

    if compare_versions.do(_latest_version, introduction.CURRENT_VERSION):
        if not compare_versions.do(_latest_version, _prepared_version):
            return

        platform_system = platform.system()
        temp_folder = tempfile.gettempdir()

        if platform_system == "Windows":
            blob_demand = "SOLSOL_INSTALLER_WINDOWS"
            filepath = temp_folder + "/SolieWindowsSetup.exe"
        elif platform_system == "Linux":
            blob_demand = "SOLSOL_INSTALLER_LINUX"
            filepath = ""
        elif platform_system == "Darwin":
            blob_demand = "SOLSOL_INSTALLER_MAC"
            filepath = ""

        api_requester = ApiRequester()

        payload = {"blobDemand": blob_demand}
        response = api_requester.cunarist("GET", "/api/general/blob-url", payload)
        blob_url = response["blobUrl"]

        download_data = request.urlopen(blob_url).read()

        with open(filepath, mode="wb") as file:
            file.write(download_data)

        text = "Downloaded update installer."
        logger = logging.getLogger("solie")
        logger.info(text)

        _prepared_version = _latest_version
        _is_prepared = True


def apply():
    if _is_prepared:
        if platform.system() == "Windows":
            temp_folder = tempfile.gettempdir()
            filepath = temp_folder + "/SolieWindowsSetup.exe"
            if os.path.isfile(filepath):
                commands = [f"{filepath} /SILENT"]
                subprocess.Popen(
                    "&&".join(commands),
                    creationflags=subprocess.DETACHED_PROCESS,
                )

        elif platform.system() == "Linux":
            pass

        elif platform.system() == "Darwin":  # macOS
            pass
