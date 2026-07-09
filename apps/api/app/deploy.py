"""
Deployment logic: safe unzip, validation, root-directory detection, move.
"""

from __future__ import annotations

import os
import shutil
import zipfile
from pathlib import Path

from . import config


class DeployError(Exception):
    """Raised when validation or deployment fails with a user-facing message."""

    def __init__(self, message: str, code: str = "VALIDATION_ERROR", status: int = 422):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status = status


def _is_within_directory(directory: Path, target: Path) -> bool:
    """Check that *target* resolves inside *directory* (prevents path traversal)."""
    abs_dir = directory.resolve()
    abs_target = target.resolve()
    try:
        abs_target.relative_to(abs_dir)
        return True
    except ValueError:
        return False


def _is_blocked(filename: str) -> bool:
    ext = Path(filename).suffix.lower()
    return ext in config.BLOCKED_EXTENSIONS


def safe_unzip(
    zip_path: Path,
    dest_dir: Path,
) -> tuple[int, int]:
    """
    Safely extract *zip_path* into *dest_dir*.

    Enforces:
      - No path traversal (../, absolute paths, symlinks)
      - No blocked extensions
      - Per-file size limit
      - Total file count limit
      - Total uncompressed size limit

    Returns (file_count, total_size_bytes).
    Raises DeployError on any violation.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)

    file_count = 0
    total_size = 0

    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            members = zf.infolist()
            if len(members) > config.MAX_FILE_COUNT:
                raise DeployError(
                    f"Zip contains {len(members)} entries, "
                    f"exceeds limit of {config.MAX_FILE_COUNT}",
                    code="QUOTA_EXCEEDED",
                    status=413,
                )

            for member in members:
                # Skip directories (we create them implicitly via extracting files)
                if member.is_dir():
                    continue

                # --- path traversal checks ---
                member_path = Path(member.filename)
                target_path = dest_dir / member_path

                if not _is_within_directory(dest_dir, target_path):
                    raise DeployError(
                        f"Unsafe path in zip: {member.filename}",
                        code="VALIDATION_ERROR",
                    )

                # Reject absolute paths
                if os.path.isabs(member.filename) or member.filename.startswith("\\"):
                    raise DeployError(
                        f"Absolute path in zip: {member.filename}",
                        code="VALIDATION_ERROR",
                    )

                # Reject symlinks (member.external_attr high bits = unix mode)
                unix_mode = (member.external_attr >> 16) & 0o170000
                if unix_mode == 0o120000:  # S_IFLNK
                    raise DeployError(
                        f"Symlink in zip not allowed: {member.filename}",
                        code="VALIDATION_ERROR",
                    )

                # --- blocked extensions ---
                if _is_blocked(member.filename):
                    raise DeployError(
                        f"Blocked file type: {member.filename}",
                        code="VALIDATION_ERROR",
                    )

                # --- per-file size ---
                if member.file_size > config.MAX_FILE_SIZE:
                    raise DeployError(
                        f"File too large ({member.file_size} bytes): {member.filename}",
                        code="QUOTA_EXCEEDED",
                        status=413,
                    )

                # --- running total ---
                file_count += 1
                total_size += member.file_size

                if file_count > config.MAX_FILE_COUNT:
                    raise DeployError(
                        f"File count exceeds limit of {config.MAX_FILE_COUNT}",
                        code="QUOTA_EXCEEDED",
                        status=413,
                    )

                if total_size > config.MAX_TOTAL_SIZE:
                    raise DeployError(
                        f"Total uncompressed size exceeds limit "
                        f"of {config.MAX_TOTAL_SIZE} bytes",
                        code="QUOTA_EXCEEDED",
                        status=413,
                    )

                # Extract one file
                zf.extract(member, dest_dir)

    except zipfile.BadZipFile:
        raise DeployError("Invalid or corrupted zip file", code="VALIDATION_ERROR")
    except DeployError:
        raise
    except Exception as exc:
        raise DeployError(f"Failed to extract zip: {exc}", code="INTERNAL", status=500)

    return file_count, total_size


def find_deploy_root(extracted_dir: Path, max_depth: int = 3) -> Path:
    """
    Find the directory containing index.html.

    Strategy:
      1. If *extracted_dir* itself has index.html → return it.
      2. Search subdirectories up to *max_depth* levels deep.
         If multiple candidates, pick the one with the most files.
      3. If none found → raise DeployError.

    Common case: a zip whose top-level is a single folder (e.g. ``dist/``)
    containing ``index.html``.
    """
    # Case 1: root has index.html
    if (extracted_dir / "index.html").is_file():
        return extracted_dir

    # Case 2: search subdirectories
    candidates: list[tuple[Path, int]] = []

    for root, dirs, files in os.walk(extracted_dir):
        root_path = Path(root)
        rel_depth = len(root_path.relative_to(extracted_dir).parts)
        if rel_depth > max_depth:
            # Don't descend further
            dirs.clear()
            continue

        if "index.html" in files:
            file_count = sum(1 for f in files if not f.startswith("."))
            candidates.append((root_path, file_count))

    if not candidates:
        raise DeployError(
            "No index.html found in the uploaded zip. "
            "Ensure your build output contains an index.html.",
            code="NO_INDEX_HTML",
        )

    # Pick the candidate with the most files
    candidates.sort(key=lambda c: c[1], reverse=True)
    return candidates[0][0]


def rewrite_html_paths(deploy_root: Path) -> None:
    """
    Rewrite absolute asset paths in HTML files to relative paths.

    When a site is deployed under /s/{deployId}/, absolute paths like
    /assets/index.js break because the browser requests them from the
    server root instead of the deployment subpath.

    This function scans all .html files in *deploy_root* and rewrites:
      - src="/..."       →  src="./..."        (or src="..." )
      - href="/..."       →  href="./..."
      - srcset="/..."     →  srcset="./..."
      - Action="/..."     →  action="./..."

    It only rewrites paths that start with a single leading slash (not //).
    Protocol-relative URLs (//cdn.example.com/...) and full URLs
    (https://...) are left untouched.
    """
    import re

    # Pattern: attribute="value" where value starts with / but not //
    # Captures: (attr)=(")(/path)(")
    attr_pattern = re.compile(
        r'\b(src|href|srcset|action)\s*=\s*(["\'])(/(?!/)[^"\']*)\2',
        re.IGNORECASE,
    )

    # Also handle <base href="/"> which would break relative paths
    base_pattern = re.compile(
        r'<base\s+href=["\']/(?!/)[^"\']*["\']',
        re.IGNORECASE,
    )

    for root, _, files in os.walk(deploy_root):
        for fname in files:
            if not fname.endswith(".html"):
                continue
            fpath = Path(root) / fname
            try:
                content = fpath.read_text(encoding="utf-8")
                original = content

                # Remove <base href="/"> tags — they break relative paths
                # in a subpath deployment
                content = base_pattern.sub("", content)

                # Rewrite absolute paths to relative
                # /assets/foo.js → ./assets/foo.js
                def _replace(match: re.Match) -> str:
                    attr = match.group(1)
                    quote = match.group(2)
                    path = match.group(3)
                    # Skip if it's a data: or other non-path
                    if path.startswith("/data:"):
                        return match.group(0)
                    return f'{attr}={quote}.{path}{quote}'

                content = attr_pattern.sub(_replace, content)

                if content != original:
                    fpath.write_text(content, encoding="utf-8")
            except Exception:
                # If we can't read/write an HTML file, skip it
                # (might be binary or permission issue)
                pass


def move_to_deployments(src_root: Path, deploy_id: str) -> Path:
    """
    Move *src_root* contents to /data/deployments/{deploy_id}/.
    Returns the final deployment directory path.
    """
    final_dir = config.DEPLOYMENTS_DIR / deploy_id
    config.DEPLOYMENTS_DIR.mkdir(parents=True, exist_ok=True)

    if final_dir.exists():
        shutil.rmtree(final_dir)

    # Move the entire src_root directory to final_dir
    shutil.move(str(src_root), str(final_dir))
    return final_dir


def count_files_and_size(directory: Path) -> tuple[int, int]:
    """Count files and total size in a directory (after move, for accuracy)."""
    count = 0
    size = 0
    for root, _, files in os.walk(directory):
        for f in files:
            fp = Path(root) / f
            if fp.is_file():
                count += 1
                size += fp.stat().st_size
    return count, size


def cleanup_tmp(deploy_id: str) -> None:
    """Remove temporary zip and extraction directory."""
    tmp_zip = config.TMP_DIR / f"{deploy_id}.zip"
    tmp_extract = config.TMP_DIR / deploy_id
    for p in (tmp_zip, tmp_extract):
        try:
            if p.is_file():
                p.unlink()
            elif p.is_dir():
                shutil.rmtree(p)
        except Exception:
            pass  # best-effort cleanup


def remove_deployment_files(deploy_id: str) -> bool:
    """Delete the deployment directory from disk. Returns True if removed."""
    deploy_dir = config.DEPLOYMENTS_DIR / deploy_id
    if deploy_dir.exists():
        shutil.rmtree(deploy_dir)
        return True
    return False


async def safe_write_files(
    files: list[tuple[bytes, str]],
    dest_dir: Path,
) -> tuple[int, int]:
    """
    Safely write multiple uploaded files into *dest_dir*, preserving their
    relative paths.

    This is the folder-upload counterpart to ``safe_unzip``. It applies the
    same security checks:
      - No path traversal (../, absolute paths)
      - No blocked extensions
      - Per-file size limit
      - Total file count limit
      - Total uncompressed size limit

    Args:
        files: list of (content_bytes, relative_path) tuples.
        dest_dir: destination directory to write into.

    Returns (file_count, total_size_bytes).
    Raises DeployError on any violation.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)

    file_count = 0
    total_size = 0

    if len(files) > config.MAX_FILE_COUNT:
        raise DeployError(
            f"Folder contains {len(files)} files, "
            f"exceeds limit of {config.MAX_FILE_COUNT}",
            code="QUOTA_EXCEEDED",
            status=413,
        )

    for content, relative_path in files:
        # --- path sanitization ---
        # Normalize and reject dangerous patterns
        if os.path.isabs(relative_path) or relative_path.startswith("\\"):
            raise DeployError(
                f"Absolute path not allowed: {relative_path}",
                code="VALIDATION_ERROR",
            )

        # Reject path traversal
        if ".." in Path(relative_path).parts:
            raise DeployError(
                f"Path traversal not allowed: {relative_path}",
                code="VALIDATION_ERROR",
            )

        member_path = Path(relative_path)
        target_path = dest_dir / member_path

        if not _is_within_directory(dest_dir, target_path):
            raise DeployError(
                f"Unsafe path: {relative_path}",
                code="VALIDATION_ERROR",
            )

        # --- blocked extensions ---
        if _is_blocked(relative_path):
            raise DeployError(
                f"Blocked file type: {relative_path}",
                code="VALIDATION_ERROR",
            )

        # --- per-file size ---
        file_size = len(content)
        if file_size > config.MAX_FILE_SIZE:
            raise DeployError(
                f"File too large ({file_size} bytes): {relative_path}",
                code="QUOTA_EXCEEDED",
                status=413,
            )

        # --- running totals ---
        file_count += 1
        total_size += file_size

        if total_size > config.MAX_TOTAL_SIZE:
            raise DeployError(
                f"Total size exceeds limit of {config.MAX_TOTAL_SIZE} bytes",
                code="QUOTA_EXCEEDED",
                status=413,
            )

        # Write the file, creating parent directories
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(content)

    return file_count, total_size
