"""Attest the immutable source files that own proof-stage timer boundaries."""

import hashlib
from pathlib import Path
import re


def digest(source: Path, paths: list[str]) -> str:
    if not paths or len(set(paths)) != len(paths):
        raise ValueError("timer file list must be nonempty and unique")
    result = hashlib.sha256()
    for name in sorted(paths):
        path = Path(name)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError(f"unsafe timer path: {name}")
        content = (source / path).read_bytes()
        result.update(name.encode() + b"\0" + len(content).to_bytes(8, "little") + content)
    return result.hexdigest()


def check_protected(config: dict) -> None:
    for backend, item in config["backends"].items():
        editable = item["editablePaths"]
        protected = set(item["protectedPaths"])
        for path in item["timerFiles"]:
            if any(path == prefix or path.startswith(prefix + "/") for prefix in editable) and path not in protected:
                raise ValueError(f"{backend} timer owner remains editable: {path}")


def attest(source: Path, config: dict, backend: str) -> str:
    """Reject a changed timer owner before a backend can produce evidence."""
    check_protected(config)
    try:
        item = config["backends"][backend]
    except KeyError as error:
        raise ValueError(f"unknown backend: {backend}") from error
    expected = item.get("timerDigest")
    if not isinstance(expected, str) or re.fullmatch(r"[0-9a-f]{64}", expected) is None:
        raise ValueError(f"invalid {backend} timer digest")
    actual = digest(source, item["timerFiles"])
    if actual != expected:
        raise ValueError(f"{backend} timer owner changed: {actual} != {expected}")
    return actual
