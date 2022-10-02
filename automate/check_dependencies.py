import subprocess
import json
import yaml
import sys
from importlib import metadata

commands = ["pip-licenses", "--format=json"]
output = subprocess.check_output(commands).decode()
all_licenses = json.loads(output)

commands = ["pipdeptree", "--json"]
output = subprocess.check_output(commands).decode()
tree = json.loads(output)

environment_string = ""
filepath = "environment.yaml"
with open(filepath, "r", encoding="utf8") as file:
    for line in file:
        if "dev" in line:
            break
        else:
            environment_string += line.split("=")[0] + "\n"
environments = yaml.safe_load(environment_string)
needed_packages = []
needed_packages += environments["dependencies"][:-1]
needed_packages += environments["dependencies"][-1]["pip"]

included_packages = []
for each_item in tree:
    if each_item["package"]["key"] in needed_packages:
        included_packages.append(each_item["package"]["key"])
        for dependency_item in each_item["dependencies"]:
            included_packages.append(dependency_item["key"])
included_packages = list(set(included_packages))  # make elements unique

inclusion_information = []
for package_key in included_packages:
    package_name = package_key
    package_version = "Unavailable"
    package_license = "Unavailable"
    package_url = metadata.metadata(package_name)["Home-page"]
    for license_item in all_licenses:
        if license_item["Name"].lower() == package_key:
            package_name = license_item["Name"]
            package_version = license_item["Version"]
            package_license = license_item["License"]
    new_data = [package_name, package_version, package_license, package_url]
    inclusion_information.append(new_data)
sys.stdout.write(json.dumps(inclusion_information, indent=4, default=str))
