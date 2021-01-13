import os
import string
import random


characters = list(string.ascii_letters + string.digits)
random.shuffle(characters)
license_keys = []
for _ in range(8):
    license_key = ""
    for _ in range(32):
        license_key += random.choice(characters)
    license_keys.append(license_key)
os.makedirs("./dist", exist_ok=True)
with open("./dist/license_keys.txt", mode="w", encoding="utf8") as file:
    file.write("\n".join(license_keys))
