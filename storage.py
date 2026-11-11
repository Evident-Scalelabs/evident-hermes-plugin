"""Immutable, bounded artifacts under the host's documented plugin data directory."""
import contextlib
import json
import os
from pathlib import Path
import re
import uuid

ID = re.compile(r"[0-9a-f]{32}\Z")
FILES = re.compile(r"(?:(?:context|context-plan|context-comparison|context-claims(?:-followup)?|context-followups|context-answer-[0-3](?:-retry-1)?|context-source-(?:[0-9]|1[0-6])|plan|execution-plan|planning-[0-9]|control-followup-(?:[0-9]|1[0-9]|2[0-3])|result|explanation|review|scan|demo|model-output|step-(?:[0-9]|1[0-9]|2[0-3]))\.json|(?:view|report|reviewed-report)\.html)\Z")
PENDING = re.compile(r"\.pending-[0-9a-f]{32}\Z")


class Store:
    def __init__(self, root):
        self.root = Path(root)
        if not hasattr(os, "O_NOFOLLOW"):
            raise RuntimeError("This preview requires a POSIX host with O_NOFOLLOW")
        for part in (self.root, *self.root.parents):
            if part.is_symlink():
                raise ValueError("Symlinked artifact storage is not supported")
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)

    @contextlib.contextmanager
    def directory(self, run_id=None):
        root = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            if run_id is None:
                yield root
            else:
                if not isinstance(run_id, str) or not ID.fullmatch(run_id):
                    raise ValueError("Expected a plugin run ID")
                fd = os.open(run_id, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=root)
                try:
                    yield fd
                finally:
                    os.close(fd)
        finally:
            os.close(root)

    @contextlib.contextmanager
    def lease(self):
        import fcntl
        with self.directory() as root:
            fd = os.open(".capture.lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600, dir_fd=root)
            try:
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError as exc:
                    raise ValueError("A capture or cleanup is already active in this profile") from exc
                yield
            finally:
                os.close(fd)

    def create(self, plan):
        with self.directory() as root:
            if sum(bool(ID.fullmatch(name)) for name in os.listdir(root)) >= 50:
                raise ValueError("Retention limit reached (50 runs); delete selected plugin runs first")
            run_id = uuid.uuid4().hex
            os.mkdir(run_id, mode=0o700, dir_fd=root)
        self.write(run_id, "plan.json", plan)
        return run_id

    def write(self, run_id, name, value):
        self.write_bytes(run_id, name, json.dumps(value, ensure_ascii=True, indent=2).encode())

    def write_bytes(self, run_id, name, data):
        if not FILES.fullmatch(name):
            raise ValueError("Unknown artifact")
        if len(data) > (20_000_000 if name.endswith(".html") else 4_000_000):
            raise ValueError("Artifact exceeds storage bound")
        with self.directory(run_id) as directory:
            pending = ".pending-" + uuid.uuid4().hex
            fd = os.open(pending, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=directory)
            try:
                with os.fdopen(fd, "wb") as handle:
                    handle.write(data)
                    handle.flush()
                    os.fsync(handle.fileno())
                # Hard-link publication is atomic and refuses to overwrite an existing artifact.
                os.link(pending, name, src_dir_fd=directory, dst_dir_fd=directory, follow_symlinks=False)
            finally:
                os.unlink(pending, dir_fd=directory)

    def read(self, run_id, name):
        if not FILES.fullmatch(name):
            raise ValueError("Unknown artifact")
        with self.directory(run_id) as directory:
            fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
            import stat
            with os.fdopen(fd, "rb") as handle:
                info = os.fstat(handle.fileno())
                if not stat.S_ISREG(info.st_mode) or info.st_size > 4_000_000:
                    raise ValueError("Not a bounded regular artifact")
                return json.loads(handle.read(4_000_001))

    def inspect(self, run_id):
        plan = self.read(run_id, "plan.json")
        try:
            plan = self.read(run_id, "execution-plan.json")
        except FileNotFoundError:
            pass
        steps = []
        for index in range(24):
            try:
                steps.append(self.read(run_id, f"step-{index}.json"))
            except FileNotFoundError:
                break
        try:
            result = self.read(run_id, "result.json")
        except FileNotFoundError:
            result = {"state": "incomplete", "limitation": "No final receipt; retained steps are inspectable"}
        record = {"run_id": run_id, "plan": plan, "steps": steps, "result": result}
        try:
            record["explanation"] = self.read(run_id, "explanation.json")
        except FileNotFoundError:
            pass
        try:
            record["review"] = self.read(run_id, "review.json")
        except FileNotFoundError:
            pass
        try:
            record["scan"] = self.read(run_id, "scan.json")
        except FileNotFoundError:
            pass
        try:
            record["context"] = self.read(run_id, "context.json")
        except FileNotFoundError:
            pass
        try:
            record["demo"] = self.read(run_id, "demo.json")
        except FileNotFoundError:
            pass
        return record

    def delete(self, run_id):
        with self.lease(), self.directory(run_id) as directory:
            names = os.listdir(directory)
            if any(not (FILES.fullmatch(name) or PENDING.fullmatch(name)) for name in names):
                raise ValueError("Unexpected files; cleanup refused")
            for name in names:
                os.unlink(name, dir_fd=directory)
            with self.directory() as root:
                os.rmdir(run_id, dir_fd=root)
        return {"deleted_run": run_id, "limitation": "Host conversation, backups and remote logs are not deleted"}



# Compatibility for existing callers; presentation has one owner.
from .report import render
