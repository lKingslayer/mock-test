from __future__ import annotations

from pathlib import Path

from app.domain.paths import extension
from runner.types import Uploaded


def percentile(values: list[float], p: float) -> float:
    """Compute the p-th percentile using linear interpolation."""
    if not values:
        return 0.0
    s = sorted(values)
    k = (len(s) - 1) * p
    f = int(k)
    c = min(f + 1, len(s) - 1)
    if f == c:
        return s[f]
    d0 = s[f] * (c - k)
    d1 = s[c] * (k - f)
    return d0 + d1


def validate_and_collect_fixtures(fixtures_dir: Path, expected: int = 10) -> list[Path]:
    """Return the list of fixture files, asserting an expected count."""
    from runner.types import SmokeError

    if not fixtures_dir.exists():
        raise SmokeError(f"fixtures directory not found: {fixtures_dir}")
    all_files = sorted([p for p in fixtures_dir.rglob("*") if p.is_file()])
    if len(all_files) != expected:
        raise SmokeError(f"expected exactly {expected} fixture files, found {len(all_files)}")
    return all_files


def summarize(
    uploaded: list[Uploaded], last_items: list[dict], terminal_at: dict[str, int]
) -> tuple[dict, int]:
    """Compute summary dict and an exit code from final states."""
    durations_ms: list[float] = []
    success = 0
    failure = 0
    per_ext: dict[str, dict[str, int]] = {}
    failures_detail: list[dict] = []

    items_by_id = {it["resource_id"]: it for it in (last_items or [])}
    for u in uploaded:
        ext = extension(u.path)
        per_ext.setdefault(ext, {"indexed": 0, "error": 0})
        term_ms = terminal_at.get(u.token)
        it = items_by_id.get(u.token, {})
        status = it.get("status")
        if term_ms is not None:
            durations_ms.append(term_ms - u.created_at_ms)
        if status == "indexed":
            success += 1
            per_ext[ext]["indexed"] += 1
        elif status == "error":
            failure += 1
            per_ext[ext]["error"] += 1
            failures_detail.append(
                {
                    "path": u.path,
                    "error_code": it.get("error_code"),
                    "error_message": it.get("error_message"),
                }
            )
        else:
            failures_detail.append(
                {"path": u.path, "error_code": "timeout", "error_message": "not terminal"}
            )

    avg_ms = (sum(durations_ms) / len(durations_ms)) if durations_ms else 0.0
    p95_ms = percentile(durations_ms, 0.95)
    max_ms = max(durations_ms) if durations_ms else 0.0
    summary = {
        "component": "runner",
        "event": "summary",
        "uploaded": len(uploaded),
        "indexed_count": success,
        "error_count": failure,
        "timings": {
            "avg_ms": round(avg_ms, 2),
            "p95_ms": round(p95_ms, 2),
            "max_ms": round(max_ms, 2),
        },
        "per_extension": per_ext,
        "failures": failures_detail,
    }
    all_terminal = (success + failure) == len(uploaded)
    exit_code = 0 if (all_terminal and success > 0) else 1
    return summary, exit_code


