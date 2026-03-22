#!/usr/bin/env python3
"""Flush completed files from one or more cache roots to one or more LTFS targets.

The script is designed for timer-driven execution. It persists scan state so a
file is considered "completed" only after it remains stable across scans and is
older than the configured minimum age.

For multi-drive setups the script routes each file to a healthy LTFS target and
records that placement so later updates keep using the same tape branch. The
single logical mount exposed to clients should be built on top of the cache and
the LTFS targets; this worker must write to the real LTFS branches instead of
that logical union mount.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import logging
import os
import shutil
import stat
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple


LOGGER = logging.getLogger("ltfs-cache-flush")


@dataclass(frozen=True)
class FileCandidate:
    source_root: Path
    source_path: Path
    relative_path: Path
    size: int
    mtime_ns: int
    stable_since: float


@dataclass
class TargetRoot:
    root: Path
    name: str
    total_bytes: int
    free_bytes: int


@dataclass
class FlushMetrics:
    start_time: float
    run_duration_seconds: float = 0.0
    bytes_flushed: int = 0
    files_flushed: int = 0
    failures: int = 0
    candidates: int = 0
    candidate_bytes: int = 0
    current_usage_percent: float = 0.0
    urgent_mode: int = 0
    healthy_targets: int = 0


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--buffer-root",
        action="append",
        dest="buffer_roots",
        required=True,
        help="Cache root to scan. Repeat for multiple roots.",
    )
    parser.add_argument(
        "--primary-buffer-root",
        required=True,
        help="Cache root used to evaluate filesystem pressure.",
    )
    parser.add_argument(
        "--target-root",
        action="append",
        dest="target_roots",
        required=True,
        help="Mounted LTFS target branch. Repeat for multiple tape branches.",
    )
    parser.add_argument(
        "--state-file",
        default="/var/lib/ltfs-cache-flush/state.json",
        help="Persistent scan state file.",
    )
    parser.add_argument(
        "--placement-file",
        default="/var/lib/ltfs-cache-flush/placements.json",
        help="Persistent placement map for archived files.",
    )
    parser.add_argument(
        "--catalog-file",
        default="/var/lib/ltfs-cache-flush/catalog.jsonl",
        help="Append-only placement catalog for audits.",
    )
    parser.add_argument(
        "--metrics-file",
        default="/var/lib/prometheus/node-exporter/ltfs_cache_flush.prom",
        help="Prometheus textfile collector output.",
    )
    parser.add_argument(
        "--metrics-state-file",
        default="/var/lib/ltfs-cache-flush/metrics-state.json",
        help="Persistent counters backing the Prometheus export.",
    )
    parser.add_argument(
        "--lock-file",
        default="/run/ltfs-cache-flush.lock",
        help="Lock file that prevents overlapping runs.",
    )
    parser.add_argument(
        "--min-age-seconds",
        type=int,
        default=15,
        help="Minimum age before a file can be flushed.",
    )
    parser.add_argument(
        "--min-stable-seconds",
        type=int,
        default=30,
        help="How long the file must stay unchanged across scans.",
    )
    parser.add_argument(
        "--high-watermark-percent",
        type=float,
        default=85.0,
        help="Enter urgent mode when the primary buffer filesystem reaches this usage.",
    )
    parser.add_argument(
        "--low-watermark-percent",
        type=float,
        default=70.0,
        help="When in urgent mode, keep flushing until usage falls below this level.",
    )
    parser.add_argument(
        "--min-target-total-bytes",
        type=int,
        default=1099511627776,
        help="Minimum reported target capacity required before flush is allowed.",
    )
    parser.add_argument(
        "--min-target-free-bytes",
        type=int,
        default=0,
        help="Reserve this much free space on each target before placing files.",
    )
    parser.add_argument(
        "--placement-policy",
        default="most-free",
        choices=["most-free", "path-hash"],
        help="How new files are distributed across healthy LTFS targets.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    return parser.parse_args(argv)


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def ensure_lock(lock_file: Path):
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    handle = open(lock_file, "w", encoding="utf-8")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        LOGGER.info("another flush run is still active; exiting")
        sys.exit(0)
    return handle


def load_json_mapping(path: Path) -> Dict[str, dict]:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        LOGGER.warning("failed to load json mapping %s: %s", path, exc)
        return {}
    return data if isinstance(data, dict) else {}


def save_json_mapping(path: Path, data: Dict[str, dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix=path.name + ".", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, sort_keys=True)
        os.replace(tmp_path, path)
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def append_catalog_entry(
    catalog_file: Path,
    candidate: FileCandidate,
    target: TargetRoot,
    action: str,
) -> None:
    catalog_file.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "action": action,
        "archived_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "relative_path": candidate.relative_path.as_posix(),
        "size": candidate.size,
        "mtime_ns": candidate.mtime_ns,
        "source_root": str(candidate.source_root),
        "target_name": target.name,
        "target_root": str(target.root),
    }
    with catalog_file.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, sort_keys=True) + "\n")


def save_prometheus_textfile(
    metrics_file: Path,
    counters: Dict[str, float],
    metrics: FlushMetrics,
) -> None:
    metrics_file.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix=metrics_file.name + ".", dir=str(metrics_file.parent))
    lines = [
        "# HELP homelab_ltfs_flush_runs_total Completed ltfs-cache-flush runs.",
        "# TYPE homelab_ltfs_flush_runs_total counter",
        f"homelab_ltfs_flush_runs_total {int(counters.get('runs_total', 0))}",
        "# HELP homelab_ltfs_flush_bytes_total Total bytes flushed to LTFS.",
        "# TYPE homelab_ltfs_flush_bytes_total counter",
        f"homelab_ltfs_flush_bytes_total {int(counters.get('bytes_total', 0))}",
        "# HELP homelab_ltfs_flush_files_total Total files flushed to LTFS.",
        "# TYPE homelab_ltfs_flush_files_total counter",
        f"homelab_ltfs_flush_files_total {int(counters.get('files_total', 0))}",
        "# HELP homelab_ltfs_flush_failures_total Total ltfs-cache-flush candidate failures.",
        "# TYPE homelab_ltfs_flush_failures_total counter",
        f"homelab_ltfs_flush_failures_total {int(counters.get('failures_total', 0))}",
        "# HELP homelab_ltfs_flush_last_run_duration_seconds Duration of the last ltfs-cache-flush run.",
        "# TYPE homelab_ltfs_flush_last_run_duration_seconds gauge",
        f"homelab_ltfs_flush_last_run_duration_seconds {metrics.run_duration_seconds:.6f}",
        "# HELP homelab_ltfs_flush_last_run_bytes Bytes flushed in the last ltfs-cache-flush run.",
        "# TYPE homelab_ltfs_flush_last_run_bytes gauge",
        f"homelab_ltfs_flush_last_run_bytes {metrics.bytes_flushed}",
        "# HELP homelab_ltfs_flush_last_run_files Files flushed in the last ltfs-cache-flush run.",
        "# TYPE homelab_ltfs_flush_last_run_files gauge",
        f"homelab_ltfs_flush_last_run_files {metrics.files_flushed}",
        "# HELP homelab_ltfs_flush_last_run_failures Candidate failures in the last ltfs-cache-flush run.",
        "# TYPE homelab_ltfs_flush_last_run_failures gauge",
        f"homelab_ltfs_flush_last_run_failures {metrics.failures}",
        "# HELP homelab_ltfs_flush_candidates Number of candidates discovered in the last scan.",
        "# TYPE homelab_ltfs_flush_candidates gauge",
        f"homelab_ltfs_flush_candidates {metrics.candidates}",
        "# HELP homelab_ltfs_flush_candidate_bytes Bytes represented by the candidates discovered in the last scan.",
        "# TYPE homelab_ltfs_flush_candidate_bytes gauge",
        f"homelab_ltfs_flush_candidate_bytes {metrics.candidate_bytes}",
        "# HELP homelab_ltfs_flush_buffer_usage_percent Primary buffer usage percent at the end of the run.",
        "# TYPE homelab_ltfs_flush_buffer_usage_percent gauge",
        f"homelab_ltfs_flush_buffer_usage_percent {metrics.current_usage_percent:.6f}",
        "# HELP homelab_ltfs_flush_urgent_mode Whether the last run entered urgent mode.",
        "# TYPE homelab_ltfs_flush_urgent_mode gauge",
        f"homelab_ltfs_flush_urgent_mode {metrics.urgent_mode}",
        "# HELP homelab_ltfs_flush_healthy_targets Healthy LTFS targets visible to the last run.",
        "# TYPE homelab_ltfs_flush_healthy_targets gauge",
        f"homelab_ltfs_flush_healthy_targets {metrics.healthy_targets}",
        "# HELP homelab_ltfs_flush_last_run_end_timestamp_seconds Unix timestamp when the last run finished.",
        "# TYPE homelab_ltfs_flush_last_run_end_timestamp_seconds gauge",
        f"homelab_ltfs_flush_last_run_end_timestamp_seconds {metrics.start_time + metrics.run_duration_seconds:.6f}",
    ]
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
        os.replace(tmp_path, metrics_file)
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def update_metrics(
    metrics_file: Path,
    metrics_state_file: Path,
    metrics: FlushMetrics,
) -> None:
    counters = load_json_mapping(metrics_state_file)
    counters["runs_total"] = int(counters.get("runs_total", 0)) + 1
    counters["bytes_total"] = int(counters.get("bytes_total", 0)) + metrics.bytes_flushed
    counters["files_total"] = int(counters.get("files_total", 0)) + metrics.files_flushed
    counters["failures_total"] = int(counters.get("failures_total", 0)) + metrics.failures
    save_json_mapping(metrics_state_file, counters)
    save_prometheus_textfile(metrics_file, counters, metrics)


def iter_files(root: Path) -> Iterable[Path]:
    if not root.is_dir():
        return
    for current_root, dirnames, filenames in os.walk(root):
        dirnames.sort()
        filenames.sort()
        current_path = Path(current_root)
        for filename in filenames:
            yield current_path / filename


def scan_files(
    buffer_roots: List[Path],
    old_state: Dict[str, dict],
    now: float,
    min_age_seconds: int,
    min_stable_seconds: int,
) -> Tuple[List[FileCandidate], Dict[str, dict]]:
    candidates: List[FileCandidate] = []
    new_state: Dict[str, dict] = {}

    for root in buffer_roots:
        if not root.exists():
            LOGGER.warning("buffer root %s does not exist; skipping", root)
            continue

        for source_path in iter_files(root):
            try:
                st = source_path.stat()
            except FileNotFoundError:
                continue
            except OSError as exc:
                LOGGER.warning("cannot stat %s: %s", source_path, exc)
                continue

            if not stat.S_ISREG(st.st_mode):
                continue

            relative_path = source_path.relative_to(root)
            key = str(source_path)
            previous = old_state.get(key, {})
            seen_at = previous.get("seen_at", now)
            stable_since = previous.get("stable_since")

            unchanged = (
                previous.get("size") == st.st_size
                and previous.get("mtime_ns") == st.st_mtime_ns
            )
            if unchanged:
                stable_since = stable_since or seen_at
            else:
                seen_at = now
                stable_since = None

            new_state[key] = {
                "size": st.st_size,
                "mtime_ns": st.st_mtime_ns,
                "seen_at": seen_at,
                "stable_since": stable_since,
            }

            age_seconds = now - st.st_mtime
            stable_seconds = 0 if stable_since is None else now - stable_since
            if stable_since is None:
                continue
            if age_seconds < min_age_seconds:
                continue
            if stable_seconds < min_stable_seconds:
                continue

            candidates.append(
                FileCandidate(
                    source_root=root,
                    source_path=source_path,
                    relative_path=relative_path,
                    size=st.st_size,
                    mtime_ns=st.st_mtime_ns,
                    stable_since=stable_since,
                )
            )

    candidates.sort(key=lambda item: (item.stable_since, str(item.relative_path)))
    return candidates, new_state


def usage_percent(path: Path) -> float:
    usage = shutil.disk_usage(path)
    if usage.total == 0:
        return 0.0
    return usage.used / usage.total * 100.0


def target_path_for(candidate: FileCandidate, target_root: Path) -> Path:
    return target_root / candidate.relative_path


def safe_remove_empty_dirs(path: Path, stop_at: Path) -> None:
    current = path
    while current != stop_at and current.is_dir():
        try:
            current.rmdir()
        except OSError:
            break
        current = current.parent


def copy_file(source_path: Path, destination_path: Path) -> None:
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = destination_path.with_name(destination_path.name + ".ltfs-partial")
    if temp_path.exists():
        temp_path.unlink()

    with source_path.open("rb") as src, temp_path.open("wb") as dst:
        shutil.copyfileobj(src, dst, length=8 * 1024 * 1024)
        dst.flush()
        os.fsync(dst.fileno())
    shutil.copystat(source_path, temp_path, follow_symlinks=False)
    os.replace(temp_path, destination_path)


def collect_healthy_targets(args: argparse.Namespace) -> List[TargetRoot]:
    healthy_targets: List[TargetRoot] = []
    for target_arg in args.target_roots:
        target_root = Path(target_arg)
        try:
            is_dir = target_root.is_dir()
        except OSError as exc:
            LOGGER.warning("target root is temporarily inaccessible: %s (%s)", target_root, exc)
            continue
        if not is_dir:
            LOGGER.warning("target root does not exist: %s", target_root)
            continue
        try:
            is_mount = target_root.is_mount()
        except OSError as exc:
            LOGGER.warning("target root mount check failed: %s (%s)", target_root, exc)
            continue
        if not is_mount:
            LOGGER.warning("target root is not mounted: %s", target_root)
            continue

        try:
            usage = shutil.disk_usage(target_root)
        except OSError as exc:
            LOGGER.warning("target root usage probe failed: %s (%s)", target_root, exc)
            continue
        if usage.total < args.min_target_total_bytes:
            LOGGER.warning(
                "target root does not look LTFS-ready; reported total=%s bytes is below threshold=%s bytes: %s",
                usage.total,
                args.min_target_total_bytes,
                target_root,
            )
            continue
        if usage.free < args.min_target_free_bytes:
            LOGGER.warning(
                "target root is below free-space reserve; free=%s bytes reserve=%s bytes: %s",
                usage.free,
                args.min_target_free_bytes,
                target_root,
            )
            continue

        healthy_targets.append(
            TargetRoot(
                root=target_root,
                name=target_root.name,
                total_bytes=usage.total,
                free_bytes=usage.free,
            )
        )

    healthy_targets.sort(key=lambda item: item.name)
    return healthy_targets


def placement_key(candidate: FileCandidate) -> str:
    return candidate.relative_path.as_posix()


def find_existing_targets(
    candidate: FileCandidate, healthy_targets: List[TargetRoot]
) -> List[TargetRoot]:
    existing_targets: List[TargetRoot] = []
    for target in healthy_targets:
        try:
            target_exists = target_path_for(candidate, target.root).exists()
        except OSError as exc:
            LOGGER.warning(
                "skipping target existence check after target access error for %s on %s: %s",
                candidate.relative_path,
                target.root,
                exc,
            )
            continue
        if target_exists:
            existing_targets.append(target)
    return existing_targets


def choose_target(
    candidate: FileCandidate,
    healthy_targets: List[TargetRoot],
    placement_policy: str,
) -> TargetRoot:
    if placement_policy == "path-hash":
        ordered_targets = sorted(healthy_targets, key=lambda item: item.name)
        digest = hashlib.sha256(candidate.relative_path.as_posix().encode("utf-8")).digest()
        return ordered_targets[int.from_bytes(digest[:8], "big") % len(ordered_targets)]
    return max(healthy_targets, key=lambda item: (item.free_bytes, item.name))


def eligible_target_for_copy(
    candidate: FileCandidate,
    preferred_target: Optional[TargetRoot],
    healthy_targets: List[TargetRoot],
    args: argparse.Namespace,
) -> Optional[TargetRoot]:
    eligible = [
        target
        for target in healthy_targets
        if target.free_bytes >= candidate.size + args.min_target_free_bytes
    ]
    if not eligible:
        return None
    if preferred_target is not None:
        for target in eligible:
            if target.root == preferred_target.root:
                return target
    return choose_target(candidate, eligible, args.placement_policy)


def flush_candidate(candidate: FileCandidate, target: TargetRoot) -> bool:
    destination_path = target_path_for(candidate, target.root)
    if not candidate.source_path.exists():
        return False

    try:
        if destination_path.exists() and destination_path.is_file():
            destination_stat = destination_path.stat()
            source_stat = candidate.source_path.stat()
            if (
                destination_stat.st_size == source_stat.st_size
                and int(destination_stat.st_mtime) == int(source_stat.st_mtime)
            ):
                candidate.source_path.unlink()
                safe_remove_empty_dirs(candidate.source_path.parent, candidate.source_root)
                LOGGER.info(
                    "removed duplicate source after destination match: %s",
                    candidate.source_path,
                )
                return True
            LOGGER.info("updating existing archived file: %s", destination_path)
    except OSError as exc:
        LOGGER.warning("failed to inspect existing destination %s: %s", destination_path, exc)

    LOGGER.info("flushing %s -> %s", candidate.source_path, destination_path)
    try:
        copy_file(candidate.source_path, destination_path)
    except OSError as exc:
        LOGGER.error("copy failed for %s: %s", candidate.source_path, exc)
        return False

    try:
        destination_size = destination_path.stat().st_size
    except OSError as exc:
        LOGGER.error("failed to stat copied file %s: %s", destination_path, exc)
        return False

    if destination_size != candidate.size:
        LOGGER.error(
            "destination size mismatch for %s: expected=%s actual=%s",
            destination_path,
            candidate.size,
            destination_size,
        )
        return False

    try:
        candidate.source_path.unlink()
        safe_remove_empty_dirs(candidate.source_path.parent, candidate.source_root)
    except OSError as exc:
        LOGGER.error("failed to remove source %s after copy: %s", candidate.source_path, exc)
        return False

    target.free_bytes = max(0, target.free_bytes - candidate.size)
    return True


def run_once(args: argparse.Namespace) -> int:
    state_file = Path(args.state_file)
    placement_file = Path(args.placement_file)
    catalog_file = Path(args.catalog_file)
    metrics_file = Path(args.metrics_file)
    metrics_state_file = Path(args.metrics_state_file)
    lock_handle = ensure_lock(Path(args.lock_file))
    metrics = FlushMetrics(start_time=time.time())
    try:
        buffer_roots = [Path(item) for item in args.buffer_roots]
        primary_buffer_root = Path(args.primary_buffer_root)
        if not primary_buffer_root.is_dir():
            LOGGER.error("primary buffer root does not exist: %s", primary_buffer_root)
            metrics.run_duration_seconds = time.time() - metrics.start_time
            return 2

        healthy_targets = collect_healthy_targets(args)
        metrics.healthy_targets = len(healthy_targets)
        if not healthy_targets:
            LOGGER.warning("no healthy LTFS targets available; keeping files in cache")
            metrics.current_usage_percent = usage_percent(primary_buffer_root)
            metrics.run_duration_seconds = time.time() - metrics.start_time
            return 0

        target_names = ",".join(target.name for target in healthy_targets)
        current_usage = usage_percent(primary_buffer_root)
        urgent = current_usage >= args.high_watermark_percent
        metrics.current_usage_percent = current_usage
        metrics.urgent_mode = 1 if urgent else 0
        LOGGER.info(
            "scan start: usage=%.2f%% urgent=%s primary=%s targets=%s",
            current_usage,
            urgent,
            primary_buffer_root,
            target_names,
        )

        now = time.time()
        old_state = load_json_mapping(state_file)
        placements = load_json_mapping(placement_file)
        candidates, new_state = scan_files(
            buffer_roots,
            old_state,
            now,
            args.min_age_seconds,
            args.min_stable_seconds,
        )
        metrics.candidates = len(candidates)
        metrics.candidate_bytes = sum(candidate.size for candidate in candidates)

        if not candidates:
            save_json_mapping(state_file, new_state)
            LOGGER.info("no completed files eligible for flush")
            metrics.current_usage_percent = usage_percent(primary_buffer_root)
            metrics.run_duration_seconds = time.time() - metrics.start_time
            return 0

        target_by_root = {str(target.root): target for target in healthy_targets}
        flushed = 0
        failures = 0

        for candidate in candidates:
            relative_key = placement_key(candidate)
            placement = placements.get(relative_key, {})
            preferred_target = target_by_root.get(placement.get("target_root", ""))
            existing_targets = find_existing_targets(candidate, healthy_targets)

            if len(existing_targets) > 1:
                LOGGER.error(
                    "path already exists on multiple LTFS targets; refusing to route %s",
                    candidate.relative_path,
                )
                failures += 1
                continue

            if preferred_target is None and placement.get("target_root"):
                LOGGER.warning(
                    "placement for %s points to unavailable target %s; leaving file in cache",
                    candidate.relative_path,
                    placement.get("target_root"),
                )
                failures += 1
                continue

            if existing_targets:
                target = existing_targets[0]
            else:
                target = eligible_target_for_copy(
                    candidate,
                    preferred_target,
                    healthy_targets,
                    args,
                )
                if target is None:
                    LOGGER.warning(
                        "no target has enough free space for %s (%s bytes)",
                        candidate.relative_path,
                        candidate.size,
                    )
                    failures += 1
                    continue

            if flush_candidate(candidate, target):
                flushed += 1
                metrics.bytes_flushed += candidate.size
                metrics.files_flushed += 1
                new_state.pop(str(candidate.source_path), None)
                placements[relative_key] = {
                    "target_name": target.name,
                    "target_root": str(target.root),
                    "size": candidate.size,
                    "mtime_ns": candidate.mtime_ns,
                    "archived_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                }
                append_catalog_entry(catalog_file, candidate, target, "archived")
                if urgent:
                    current_usage = usage_percent(primary_buffer_root)
                    metrics.current_usage_percent = current_usage
                    LOGGER.info("post-flush usage=%.2f%%", current_usage)
                    if current_usage <= args.low_watermark_percent:
                        LOGGER.info(
                            "usage dropped below low watermark %.2f%%; ending urgent cycle",
                            args.low_watermark_percent,
                        )
                        break
            else:
                failures += 1

        save_json_mapping(state_file, new_state)
        save_json_mapping(placement_file, placements)
        metrics.failures = failures
        metrics.current_usage_percent = usage_percent(primary_buffer_root)
        metrics.run_duration_seconds = time.time() - metrics.start_time
        LOGGER.info(
            "flush end: flushed=%s failed=%s candidates=%s",
            flushed,
            failures,
            len(candidates),
        )
        return 1 if failures else 0
    finally:
        metrics.run_duration_seconds = metrics.run_duration_seconds or (time.time() - metrics.start_time)
        try:
            update_metrics(metrics_file, metrics_state_file, metrics)
        except OSError as exc:
            LOGGER.warning("failed to export prometheus metrics: %s", exc)
        lock_handle.close()


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    configure_logging(args.log_level)
    return run_once(args)


if __name__ == "__main__":
    sys.exit(main())
