import platform
from urllib import request
import tempfile
import subprocess

import pyzipper

from instrument.api_requester import ApiRequester
from recipe import compare_versions
from recipe import check_internet


def check():

    if not check_internet.connected():
        return False

    api_requester = ApiRequester()
    payload = {"id": "version"}
    response = api_requester.cunarist("GET", "/solsol/latest-information", payload)

    with open("./resource/version.txt", mode="r", encoding="utf8") as file:
        current_version = file.read()

    latest_version = response["value"]

    if not compare_versions.do(latest_version, current_version):

        return False

    return True


def apply():

    platform_system = platform.system()
    if platform_system == "Windows":
        platform_name = "Windows"
    elif platform_system == "Linux":
        platform_name = "Linux"
    elif platform_system == "Darwin":
        platform_name = "macOS"

    blob_name = f"Solsol{platform_name}Setup.zip"

    api_requester = ApiRequester()

    payload = {"blobName": blob_name}
    response = api_requester.cunarist("GET", "/solsol/blob-url", payload)
    blob_url = response["blobUrl"]

    if platform.system() == "Windows":

        download_data = request.urlopen(blob_url).read()
        temp_folder = tempfile.gettempdir()

        filepath = temp_folder + "/SolsolWindowsSetup.zip"
        with open(filepath, mode="wb") as file:
            file.write(download_data)

        filepath = temp_folder + "/SolsolWindowsSetup.exe"
        with open(filepath, mode="wb") as file:
            filepath = temp_folder + "/SolsolWindowsSetup.zip"
            with pyzipper.AESZipFile(filepath) as zipfile:
                zipfile.setpassword(bytes("x2P64ETS3xKdFULJxYR38kCs8dW3jp6P", "utf8"))
                original_data = zipfile.read("SolsolWindowsSetup.exe")
            file.write(original_data)

        filepath = temp_folder + "/SolsolWindowsSetup.exe"
        commands = ["timeout 5", f"{filepath} /VERYSILENT"]
        subprocess.Popen(
            "&&".join(commands),
            creationflags=subprocess.CREATE_NO_WINDOW,
            shell=True,
        )

    elif platform.system() == "Linux":

        pass

    elif platform.system() == "Darwin":  # macOS

        pass
