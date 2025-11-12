
import time
import logging
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Configure logging
logging.basicConfig(
    filename='/var/log/watcher.log',
    level=logging.INFO,
    format='%(asctime)s - %(message)s'
)

class WatchHandler(FileSystemEventHandler):
    def on_created(self, event):
        if not event.is_directory:
            logging.info(f"File created: {event.src_path}")

if __name__ == "__main__":
    import os
    os.makedirs("/watched", exist_ok=True)

    event_handler = WatchHandler()
    observer = Observer()
    observer.schedule(event_handler, path="/watched", recursive=False)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
