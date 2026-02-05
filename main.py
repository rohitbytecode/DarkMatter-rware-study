import os
from dotenv import load_dotenv
from encryptor import encrypt_folder
from decryptor import decrypt_folder

load_dotenv()

def run(choice, folder, password):
    if choice == "1":
        encrypt_folder(folder, password)
        print("Encryption completed.")
    elif choice == "2":
        decrypt_folder(folder, password)
        print("Decryption completed.")
    else:
        raise ValueError("Invalid option")

if __name__ == "__main__":
    choice = os.getenv("DEFAULT_MODE") or input("Select option: ").strip()
    folder = input("Enter folder path: ").strip()

    password = os.getenv("ENCRYPT_PASSWORD")
    if not password:
        raise RuntimeError("ENCRYPT_PASSWORD not set")

    run(choice, folder, password)
