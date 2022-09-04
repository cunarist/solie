import pickle

from cryptography.fernet import Fernet

encrypter = Fernet("Fc2pyXg8WJYu93VILAxCaeavXqNOlfH-P6UgqT5zKNQ=")


def read(filepath):
    with open(filepath, "rb") as file:
        encrypted_bytes = file.read()
    original_bytes = encrypter.decrypt(encrypted_bytes)
    data_object = pickle.loads(original_bytes)
    return data_object


def write(data_object, filepath):
    original_bytes = pickle.dumps(data_object)
    encrypted_bytes = encrypter.encrypt(original_bytes)
    with open(filepath, "wb") as file:
        file.write(encrypted_bytes)
