"""
File Watcher Service
====================
Monitors a directory for new Terraform/Ansible files and triggers scanning.
"""

import os
import time
import hashlib
import logging
import threading
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Set, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
import fnmatch
import yaml

logger = logging.getLogger(__name__)


class FileType(Enum):
    TERRAFORM = "terraform"
    ANSIBLE = "ansible"
    YAML = "yaml"
    UNKNOWN = "unknown"


@dataclass
class WatchedFile:
    """Represents a file being watched."""
    path: Path
    file_type: FileType
    hash: str
    first_seen: datetime
    last_modified: datetime
    size: int
    scan_status: str = "pending"  # pending, scanning, scanned, failed
    fix_status: str = "none"  # none, fixing, fixed, failed


@dataclass
class WatcherConfig:
    """Configuration for file watcher."""
    watch_dir: Path
    poll_interval: int = 5
    patterns: Dict[str, List[str]] = field(default_factory=dict)
    ignore_patterns: List[str] = field(default_factory=list)


class FileWatcher:
    """
    Watches a directory for new/modified Terraform and Ansible files.
    Triggers callbacks when new files are detected.
    """
    
    def __init__(self, config: WatcherConfig):
        self.config = config
        self.watch_dir = Path(config.watch_dir)
        self.poll_interval = config.poll_interval
        
        # File tracking
        self._files: Dict[str, WatchedFile] = {}
        self._file_hashes: Dict[str, str] = {}
        
        # Callbacks
        self._on_new_file: List[Callable] = []
        self._on_file_changed: List[Callable] = []
        self._on_file_deleted: List[Callable] = []
        self._on_batch_ready: List[Callable] = []
        
        # State
        self._running = False
        self._watch_thread: Optional[threading.Thread] = None
        self._pending_batch: List[WatchedFile] = []
        self._batch_timeout = 10  # seconds to wait for more files
        self._last_file_time: Optional[datetime] = None
        
        # Default patterns if not provided
        if not config.patterns:
            self.config.patterns = {
                "terraform": ["*.tf", "*.tfvars"],
                "ansible": ["*.yml", "*.yaml", "playbook*.yml"],
            }
        
        if not config.ignore_patterns:
            self.config.ignore_patterns = [
                ".git/*", "__pycache__/*", "*.pyc", 
                ".terraform/*", "*.tfstate*"
            ]
        
        logger.info(f"FileWatcher initialized for: {self.watch_dir}")
    
    def start(self):
        """Start the file watcher in a background thread."""
        if self._running:
            logger.warning("FileWatcher is already running")
            return
        
        if not self.watch_dir.exists():
            self.watch_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created watch directory: {self.watch_dir}")
        
        self._running = True
        self._watch_thread = threading.Thread(target=self._watch_loop, daemon=True)
        self._watch_thread.start()
        logger.info("FileWatcher started")
    
    def stop(self):
        """Stop the file watcher."""
        self._running = False
        if self._watch_thread:
            self._watch_thread.join(timeout=5)
        logger.info("FileWatcher stopped")
    
    def on_new_file(self, callback: Callable[[WatchedFile], None]):
        """Register callback for new file detection."""
        self._on_new_file.append(callback)
    
    def on_file_changed(self, callback: Callable[[WatchedFile], None]):
        """Register callback for file modification."""
        self._on_file_changed.append(callback)
    
    def on_file_deleted(self, callback: Callable[[str], None]):
        """Register callback for file deletion."""
        self._on_file_deleted.append(callback)
    
    def on_batch_ready(self, callback: Callable[[List[WatchedFile]], None]):
        """Register callback for batch processing (all files in a deploy)."""
        self._on_batch_ready.append(callback)
    
    def _watch_loop(self):
        """Main watch loop."""
        logger.info(f"Starting watch loop on {self.watch_dir}")
        
        while self._running:
            try:
                self._scan_directory()
                self._check_batch_ready()
                time.sleep(self.poll_interval)
            except Exception as e:
                logger.error(f"Error in watch loop: {e}")
                time.sleep(self.poll_interval)
    
    def _scan_directory(self):
        """Scan directory for new/modified files."""
        current_files: Set[str] = set()
        
        for root, dirs, files in os.walk(self.watch_dir):
            # Filter out ignored directories
            dirs[:] = [d for d in dirs if not self._should_ignore(os.path.join(root, d))]
            
            for filename in files:
                filepath = Path(root) / filename
                relative_path = str(filepath.relative_to(self.watch_dir))
                
                if self._should_ignore(relative_path):
                    continue
                
                file_type = self._detect_file_type(filename)
                if file_type == FileType.UNKNOWN:
                    continue
                
                current_files.add(relative_path)
                self._check_file(filepath, relative_path, file_type)
        
        # Check for deleted files
        deleted_files = set(self._files.keys()) - current_files
        for deleted_path in deleted_files:
            self._handle_deleted_file(deleted_path)
    
    def _check_file(self, filepath: Path, relative_path: str, file_type: FileType):
        """Check if a file is new or modified."""
        try:
            stat = filepath.stat()
            current_hash = self._compute_hash(filepath)
            current_mtime = datetime.fromtimestamp(stat.st_mtime)
            
            if relative_path not in self._files:
                # New file
                watched_file = WatchedFile(
                    path=filepath,
                    file_type=file_type,
                    hash=current_hash,
                    first_seen=datetime.now(),
                    last_modified=current_mtime,
                    size=stat.st_size
                )
                self._files[relative_path] = watched_file
                self._file_hashes[relative_path] = current_hash
                self._pending_batch.append(watched_file)
                self._last_file_time = datetime.now()
                
                logger.info(f"New file detected: {relative_path} ({file_type.value})")
                self._trigger_callbacks(self._on_new_file, watched_file)
                
            elif self._file_hashes[relative_path] != current_hash:
                # File modified
                watched_file = self._files[relative_path]
                watched_file.hash = current_hash
                watched_file.last_modified = current_mtime
                watched_file.size = stat.st_size
                watched_file.scan_status = "pending"
                self._file_hashes[relative_path] = current_hash
                self._pending_batch.append(watched_file)
                self._last_file_time = datetime.now()
                
                logger.info(f"File modified: {relative_path}")
                self._trigger_callbacks(self._on_file_changed, watched_file)
                
        except Exception as e:
            logger.error(f"Error checking file {filepath}: {e}")
    
    def _handle_deleted_file(self, relative_path: str):
        """Handle file deletion."""
        logger.info(f"File deleted: {relative_path}")
        del self._files[relative_path]
        del self._file_hashes[relative_path]
        self._trigger_callbacks(self._on_file_deleted, relative_path)
    
    def _check_batch_ready(self):
        """Check if batch is ready for processing."""
        if not self._pending_batch:
            return
        
        if self._last_file_time:
            elapsed = (datetime.now() - self._last_file_time).total_seconds()
            if elapsed >= self._batch_timeout:
                # Batch is ready
                batch = self._pending_batch.copy()
                self._pending_batch.clear()
                self._last_file_time = None
                
                logger.info(f"Batch ready with {len(batch)} files")
                self._trigger_callbacks(self._on_batch_ready, batch)
    
    def _detect_file_type(self, filename: str) -> FileType:
        """Detect file type based on extension and patterns."""
        for pattern in self.config.patterns.get("terraform", []):
            if fnmatch.fnmatch(filename, pattern):
                return FileType.TERRAFORM
        
        for pattern in self.config.patterns.get("ansible", []):
            if fnmatch.fnmatch(filename, pattern):
                return FileType.ANSIBLE
        
        if filename.endswith((".yml", ".yaml")):
            return FileType.YAML
        
        return FileType.UNKNOWN
    
    def _should_ignore(self, path: str) -> bool:
        """Check if path should be ignored."""
        for pattern in self.config.ignore_patterns:
            if fnmatch.fnmatch(path, pattern):
                return True
        return False
    
    @staticmethod
    def _compute_hash(filepath: Path) -> str:
        """Compute MD5 hash of file content."""
        hash_md5 = hashlib.md5()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    
    @staticmethod
    def _trigger_callbacks(callbacks: List[Callable], *args):
        """Trigger all registered callbacks."""
        for callback in callbacks:
            try:
                callback(*args)
            except Exception as e:
                logger.error(f"Error in callback: {e}")
    
    def get_files(self) -> Dict[str, WatchedFile]:
        """Get all tracked files."""
        return self._files.copy()
    
    def get_pending_files(self) -> List[WatchedFile]:
        """Get files pending scan."""
        return [f for f in self._files.values() if f.scan_status == "pending"]
    
    def update_file_status(self, relative_path: str, scan_status: str = None, fix_status: str = None):
        """Update file status after processing."""
        if relative_path in self._files:
            if scan_status:
                self._files[relative_path].scan_status = scan_status
            if fix_status:
                self._files[relative_path].fix_status = fix_status


def create_watcher_from_config(config_path: str) -> FileWatcher:
    """Create FileWatcher from YAML config file."""
    with open(config_path, 'r') as f:
        config_data = yaml.safe_load(f)
    
    watcher_config = config_data.get('watcher', {})
    
    config = WatcherConfig(
        watch_dir=Path(watcher_config.get('watch_dir', '/deploy/in')),
        poll_interval=watcher_config.get('poll_interval', 5),
        patterns=watcher_config.get('patterns', {}),
        ignore_patterns=watcher_config.get('ignore', [])
    )
    
    return FileWatcher(config)


if __name__ == "__main__":
    # Test the watcher
    logging.basicConfig(level=logging.INFO)
    
    config = WatcherConfig(
        watch_dir=Path("./test_deploy"),
        poll_interval=2
    )
    
    watcher = FileWatcher(config)
    
    def on_new(file: WatchedFile):
        print(f"New file: {file.path}")
    
    def on_batch(files: List[WatchedFile]):
        print(f"Batch ready: {len(files)} files")
        for f in files:
            print(f"  - {f.path.name} ({f.file_type.value})")
    
    watcher.on_new_file(on_new)
    watcher.on_batch_ready(on_batch)
    
    watcher.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        watcher.stop()
