#!/usr/bin/env python3
import os
import sys
import time
import subprocess
import signal
import logging
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("app_watcher")

# Configuration
APP_MAIN_FILE = "chatapp.py"  # Your main application file
WATCH_DIRECTORIES = ["."]      # Directories to watch for changes
WATCH_EXTENSIONS = [".py"]     # File extensions to watch
IGNORE_PATTERNS = ["__pycache__", "*.pyc", "log"]  # Patterns to ignore

class AppReloader(FileSystemEventHandler):
    def __init__(self):
        self.process = None
        self.last_restart = 0
        self.restart_app()
        
    def on_any_event(self, event):
        # Ignore directory events and specified patterns
        if event.is_directory:
            return
            
        # Check if the file should be ignored
        for pattern in IGNORE_PATTERNS:
            if pattern in event.src_path:
                return
                
        # Check if the file extension should trigger a restart
        file_ext = os.path.splitext(event.src_path)[1]
        if file_ext not in WATCH_EXTENSIONS:
            return
            
        current_time = time.time()
        
        # Prevent multiple restarts within 2 seconds
        if current_time - self.last_restart < 2:
            return
            
        logger.info(f"Change detected in {event.src_path}")
        self.restart_app()
        
    def restart_app(self):
        self.last_restart = time.time()
        
        # Kill existing process if it exists
        if self.process and self.process.poll() is None:
            logger.info("Terminating existing process")
            os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                logger.warning("Process didn't terminate gracefully, forcing kill")
                os.killpg(os.getpgid(self.process.pid), signal.SIGKILL)
                
        # Start a new process
        logger.info(f"Starting application: python {APP_MAIN_FILE}")
        self.process = subprocess.Popen(
            ["python", APP_MAIN_FILE],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            preexec_fn=os.setsid  # Creates a new process group
        )
        
        # Start stdout/stderr reader threads
        self._start_log_reader(self.process.stdout, "APP-OUT")
        self._start_log_reader(self.process.stderr, "APP-ERR")
        
    def _start_log_reader(self, pipe, prefix):
        def reader():
            while self.process and self.process.poll() is None:
                line = pipe.readline().decode('utf-8').strip()
                if line:
                    print(f"[{prefix}] {line}")
                    
        import threading
        threading.Thread(target=reader, daemon=True).start()

def main():
    logger.info("Starting application watcher")
    print("Starting restart script...")
    
    # Setup the event handler and observer
    event_handler = AppReloader()
    observer = Observer()
    
    # Add watchers for each directory
    for directory in WATCH_DIRECTORIES:
        abs_path = os.path.abspath(directory)
        logger.info(f"Watching directory: {abs_path}")
        observer.schedule(event_handler, abs_path, recursive=True)
    
    # Start the observer
    observer.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Stopping application watcher")
        if event_handler.process and event_handler.process.poll() is None:
            os.killpg(os.getpgid(event_handler.process.pid), signal.SIGTERM)
        observer.stop()
        
    observer.join()

if __name__ == "__main__":
    main()