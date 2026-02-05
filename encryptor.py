import os
from crypto_utils import derive_key, MAGIC, SALT_SIZE, IV_SIZE
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def encrypt_file(path: str, password: str):
    with open(path, "rb") as f:
        data = f.read()

    salt = os.urandom(SALT_SIZE)
    iv = os.urandom(IV_SIZE)
    key = derive_key(password, salt)

    aes = AESGCM(key)
    encrypted = aes.encrypt(iv, data, None)

    with open(path, "wb") as f:
        f.write(MAGIC + salt + iv + encrypted)

    os.rename(path, path + ".bapu")


def encrypt_folder(folder: str, password: str):
    for root, _, files in os.walk(folder):
        for file in files:
            if not file.endswith(".bapu"):
                encrypt_file(os.path.join(root, file), password)