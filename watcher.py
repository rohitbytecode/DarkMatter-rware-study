from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import time
import pathlib
import os

from main import run

EXCLUDED_DIRS = {
    ".git",
    "__pycache__",
    ".venv",
    "venv",
    "env",
    "node_modules",
    "build",
    "dist"
}

BASE_DIR = pathlib.Path(".").resolve()



def run_once_on_startup():
    choice = os.getenv("DEFAULT_MODE", "1")
    password = os.getenv("ENCRYPT_PASSWORD")

    if not password:
        raise RuntimeError("ENCRYPT_PASSWORD not set")

    for item in BASE_DIR.iterdir():
        if not item.is_dir():
            continue
        if item.name in EXCLUDED_DIRS:
            continue
        if item.name.startswith("."):
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
            if not item.is_dir():
                continue
            if item.name in EXCLUDED_DIRS:
                continue
            if item.name.startswith("."):
                continue

            self.safe_execute(item)

    def safe_execute(self, folder):
        choice = os.getenv("DEFAULT_MODE", "1")
        password = os.getenv("ENCRYPT_PASSWORD")

        if not password:
            raise RuntimeError("ENCRYPT_PASSWORD not set")

        run(choice, str(folder.resolve()), password)


if __name__ == "__main__":
    
    run_once_on_startup()
    
    observer = Observer()
    handler = SaveHandler()
    observer.schedule(handler, path=".", recursive=False)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()

    observer.join()