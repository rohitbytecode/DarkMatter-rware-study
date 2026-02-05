import os
from crypto_utils import derive_key, MAGIC, SALT_SIZE, IV_SIZE
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def decrypt_file(path: str, password: str):
    with open(path, "rb") as f:
        content = f.read()

    if not content.startswith(MAGIC):
        return

    salt_start = len(MAGIC)
    salt = content[salt_start : salt_start + SALT_SIZE]
    iv_start = salt_start + SALT_SIZE
    iv = content[iv_start : iv_start + IV_SIZE]
    ciphertext = content[iv_start + IV_SIZE :]

    key = derive_key(password, salt)
    aes = AESGCM(key)

    decrypted = aes.decrypt(iv, ciphertext, None)

    original_path = path.replace(".bapu", "")
    with open(original_path, "wb") as f:
        f.write(decrypted)

    os.remove(path)


def decrypt_folder(folder: str, password: str):
    for root, _, files in os.walk(folder):
        for file in files:
            if file.endswith(".bapu"):
                decrypt_file(os.path.join(root, file), password)