#!/usr/bin/env python3
"""Job-finder workspace metadata.

Stdlib only. JSON on stdout, diagnostics on stderr. Exit 0 on success,
1 on an expected failure, 2 on usage errors.

Keep this file identical in every job-finder* skill that ships it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

VERSION = 1
PASS_DAYS = 30
STATUSES = (
    "suggested",
    "passed",
    "dismissed",
    "selected",
    "ready",
    "submitted",
)
TERMINAL = {"dismissed", "selected", "ready", "submitted"}
SECRET_KEYS = {
    "password",
    "passwd",
    "secret",
    "api_key",
    "apikey",
    "token",
    "ssn",
    "social_security",
    "national_insurance",
    "tax_id",
    "private_key",
}
SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
PRIVATE_KEY_RE = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")
DROP_QUERY_PREFIXES = ("utm_",)
DROP_QUERY_KEYS = {"fbclid", "gclid", "gh_src", "mc_cid", "mc_eid", "ref", "source"}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def emit(payload: dict, code: int = 0) -> None:
    payload.setdefault("ok", code == 0)
    json.dump(payload, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    raise SystemExit(code)


def fail(error: str, message: str, code: int = 1, **extra) -> None:
    emit({"ok": False, "error": error, "message": message, **extra}, code)


def workspace_paths(root: Path) -> dict[str, Path]:
    meta = root / ".job-finder"
    return {
        "root": root,
        "meta": meta,
        "profile": meta / "profile.json",
        "jobs": meta / "jobs.json",
        "status": meta / "STATUS.md",
        "consent": meta / "push-consent.json",
        "presentation": meta / "last-presentation.json",
        "searches": meta / "searches",
        "lock": meta / ".lock",
        "readme": meta / "README.md",
        "cv_source": root / "cv" / "source",
        "cv_base": root / "cv" / "base.md",
        "applications": root / "applications",
    }


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def read_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail("invalid_json", f"{path} is not valid JSON: {exc}")


def write_json(path: Path, payload) -> None:
    atomic_write(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


class Lock:
    def __init__(self, path: Path):
        self.path = path
        self.handle = None

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.handle = self.path.open("a+")
        try:
            import fcntl

            fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX)
        except ImportError:
            pass
        return self

    def __exit__(self, *_args):
        if self.handle:
            try:
                import fcntl

                fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
            except ImportError:
                pass
            self.handle.close()


def empty_profile() -> dict:
    return {
        "version": VERSION,
        "updated_at": None,
        "source_cv": {},
        "identity": {},
        "headline": "",
        "summary": "",
        "years_experience": None,
        "current_title": "",
        "seniority": "",
        "target_titles": [],
        "normal_flow_titles": [],
        "skills": [],
        "domains": [],
        "education": [],
        "experience": [],
        "interests_beyond_cv": [],
        "interests_answered": False,
        "preferences": {
            "salary": {},
            "work_mode": {},
            "location": {},
            "work_authorization": {},
            "other": {},
        },
        "uncertain": [],
        "analysis_notes": [],
    }


def empty_jobs() -> dict:
    return {"version": VERSION, "updated_at": None, "jobs": []}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def scan_secrets(value, path: str = "$") -> list[str]:
    found = []
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).lower() in SECRET_KEYS:
                found.append(f"{path}.{key} is a secret field and cannot be stored")
            found.extend(scan_secrets(item, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found.extend(scan_secrets(item, f"{path}[{index}]"))
    elif isinstance(value, str):
        if SSN_RE.search(value):
            found.append(f"{path} looks like a social security number")
        if PRIVATE_KEY_RE.search(value):
            found.append(f"{path} contains a private key")
    return found


def deep_merge(base, patch):
    if isinstance(base, dict) and isinstance(patch, dict):
        merged = dict(base)
        for key, value in patch.items():
            if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
                merged[key] = deep_merge(merged[key], value)
            else:
                merged[key] = value
        return merged
    return patch


def slugify(text: str, limit: int = 50) -> str:
    normalized = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", normalized.lower()).strip("-")
    slug = re.sub(r"-{2,}", "-", slug)
    return (slug[:limit].strip("-")) or "job"


def normalize_url(url: str | None) -> str:
    if not url:
        return ""
    try:
        parts = urlsplit(url.strip())
    except ValueError:
        return url.strip().lower()
    if not parts.scheme or not parts.netloc:
        return url.strip().lower()
    query = []
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        lower = key.lower()
        if lower in DROP_QUERY_KEYS or lower.startswith(DROP_QUERY_PREFIXES):
            continue
        query.append((key, value))
    path = parts.path.rstrip("/") or ""
    return urlunsplit(
        (
            parts.scheme.lower(),
            parts.netloc.lower(),
            path,
            urlencode(query),
            "",
        )
    )


def norm_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "").strip().lower())


def job_id(job: dict) -> str:
    url = normalize_url(job.get("url"))
    company = norm_text(job.get("company"))
    title = norm_text(job.get("title"))
    raw = url or f"{company}|{title}|{norm_text(job.get('location'))}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def git(root: Path, *args: str, check: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        check=check,
    )


def is_git(root: Path) -> bool:
    result = git(root, "rev-parse", "--is-inside-work-tree")
    return result.returncode == 0 and result.stdout.strip() == "true"


def current_branch(root: Path) -> str | None:
    if not is_git(root):
        return None
    result = git(root, "rev-parse", "--abbrev-ref", "HEAD")
    if result.returncode != 0:
        return None
    name = result.stdout.strip()
    return None if name == "HEAD" else name


def default_branch(root: Path) -> str | None:
    if not is_git(root):
        return None
    symbolic = git(root, "symbolic-ref", "--short", "refs/remotes/origin/HEAD")
    if symbolic.returncode == 0 and "/" in symbolic.stdout:
        return symbolic.stdout.strip().split("/", 1)[1]
    for name in ("main", "master"):
        if git(root, "show-ref", "--verify", "--quiet", f"refs/heads/{name}").returncode == 0:
            return name
    return current_branch(root)


def main_worktree(root: Path) -> Path:
    """Consent and other repo-level metadata live in the main checkout, not a linked worktree."""
    if not is_git(root):
        return root
    result = git(root, "rev-parse", "--git-common-dir")
    if result.returncode != 0:
        return root
    common = Path(result.stdout.strip())
    if not common.is_absolute():
        common = (root / common).resolve()
    if common.name == ".git":
        return common.parent
    return root


def origin_url(root: Path) -> str | None:
    if not is_git(root):
        return None
    result = git(root, "remote", "get-url", "origin")
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def load_state(paths: dict[str, Path]) -> tuple[dict, dict]:
    profile = read_json(paths["profile"], empty_profile())
    jobs = read_json(paths["jobs"], empty_jobs())
    if not isinstance(profile, dict) or not isinstance(jobs, dict):
        fail("invalid_json", "profile.json and jobs.json must be objects")
    jobs.setdefault("jobs", [])
    profile.setdefault("preferences", {})
    return profile, jobs


def save_state(paths: dict[str, Path], profile: dict, jobs: dict) -> None:
    profile["version"] = VERSION
    profile["updated_at"] = utc_now()
    jobs["version"] = VERSION
    jobs["updated_at"] = profile["updated_at"]
    write_json(paths["profile"], profile)
    write_json(paths["jobs"], jobs)
    atomic_write(paths["status"], render_status(profile, jobs))


def preference(profile: dict, key: str) -> dict:
    prefs = profile.setdefault("preferences", {})
    block = prefs.get(key) or {}
    return block if isinstance(block, dict) else {}


def unanswered(profile: dict) -> list[str]:
    missing = []
    if not (profile.get("source_cv") or {}).get("sha256"):
        missing.append("cv")
    if not profile.get("interests_answered"):
        missing.append("interests")
    salary = preference(profile, "salary")
    if not _salary_answered(salary):
        missing.append("salary")
    mode = preference(profile, "work_mode")
    if not mode.get("accepts"):
        missing.append("work_mode")
    location = preference(profile, "location")
    if not _location_answered(location):
        missing.append("location")
    auth = preference(profile, "work_authorization")
    if not auth.get("status"):
        missing.append("work_authorization")
    return missing


def _salary_answered(salary: dict) -> bool:
    if salary.get("unspecified") is True or salary.get("declined") is True:
        return True
    return salary.get("minimum") is not None or salary.get("target") is not None


def _location_answered(location: dict) -> bool:
    if location.get("answered") is True:
        return True
    return bool(location.get("home") or location.get("cities") or location.get("countries") or "willing_to_relocate" in location)


def mark_answered(profile: dict) -> None:
    prefs = profile.setdefault("preferences", {})
    now = utc_now()
    salary = prefs.get("salary") or {}
    if isinstance(salary, dict) and _salary_answered(salary) and not salary.get("answered_at"):
        salary["answered_at"] = now
        prefs["salary"] = salary
    mode = prefs.get("work_mode") or {}
    if isinstance(mode, dict) and mode.get("accepts") and not mode.get("answered_at"):
        mode["answered_at"] = now
        prefs["work_mode"] = mode
    location = prefs.get("location") or {}
    if isinstance(location, dict) and _location_answered(location) and not location.get("answered_at"):
        location["answered_at"] = now
        location["answered"] = True
        prefs["location"] = location
    auth = prefs.get("work_authorization") or {}
    if isinstance(auth, dict) and auth.get("status") and not auth.get("answered_at"):
        auth["answered_at"] = now
        prefs["work_authorization"] = auth


def job_index(jobs: dict) -> dict[str, dict]:
    return {item["id"]: item for item in jobs.get("jobs", []) if item.get("id")}


def still_blocked(job: dict, now: datetime | None = None) -> str | None:
    status = job.get("status")
    if status in TERMINAL:
        return status
    if status == "passed":
        until = parse_time(job.get("passed_until"))
        current = now or datetime.now(timezone.utc)
        if until and until > current:
            return "passed"
    if status == "suggested":
        return "suggested"
    return None


def annotate(job: dict) -> dict:
    item = dict(job)
    item["id"] = item.get("id") or job_id(item)
    item["url_normalized"] = normalize_url(item.get("url"))
    return item


def render_status(profile: dict, jobs: dict) -> str:
    counts: dict[str, int] = {status: 0 for status in STATUSES}
    for job in jobs.get("jobs", []):
        counts[job.get("status", "unknown")] = counts.get(job.get("status", "unknown"), 0) + 1
    identity = profile.get("identity") or {}
    lines = [
        "# Job-finder status",
        "",
        "Generated by scripts/workspace.py. Do not edit by hand.",
        "",
        f"- Updated: {profile.get('updated_at') or 'never'}",
        f"- Name: {identity.get('name') or 'unknown'}",
        f"- Current title: {profile.get('current_title') or 'unknown'}",
        f"- CV analyzed: {(profile.get('source_cv') or {}).get('analyzed_at') or 'no'}",
        f"- Unanswered: {', '.join(unanswered(profile)) or 'none'}",
        "",
        "## Decisions",
        "",
    ]
    for status in STATUSES:
        lines.append(f"- {status}: {counts.get(status, 0)}")
    lines.extend(["", "## Recent jobs", ""])
    recent = sorted(jobs.get("jobs", []), key=lambda item: item.get("status_at") or "", reverse=True)[:15]
    if not recent:
        lines.append("No jobs recorded yet.")
    else:
        lines.append("| Status | Company | Role | When |")
        lines.append("| --- | --- | --- | --- |")
        for job in recent:
            lines.append(
                f"| {job.get('status', '')} | {job.get('company', '')} | {job.get('title', '')} | {job.get('status_at', '')} |"
            )
    lines.append("")
    return "\n".join(lines)


def cmd_init(args) -> None:
    root = Path(args.workspace).expanduser().resolve()
    paths = workspace_paths(root)
    paths["meta"].mkdir(parents=True, exist_ok=True)
    paths["cv_source"].mkdir(parents=True, exist_ok=True)
    paths["applications"].mkdir(parents=True, exist_ok=True)
    paths["searches"].mkdir(parents=True, exist_ok=True)
    if not paths["profile"].exists():
        write_json(paths["profile"], empty_profile())
    if not paths["jobs"].exists():
        write_json(paths["jobs"], empty_jobs())
    gitignore = paths["meta"] / ".gitignore"
    if not gitignore.exists():
        atomic_write(gitignore, ".lock\n*.tmp\n")
    if not paths["readme"].exists():
        atomic_write(
            paths["readme"],
            "\n".join(
                [
                    "# Job-finder workspace",
                    "",
                    "This directory is the memory for a job search. The agent reads and writes it",
                    "through `scripts/workspace.py` so salary, location, and apply/dismiss decisions",
                    "are not asked or suggested twice.",
                    "",
                    "- `profile.json` is the CV analysis and preferences. Search uses this, not the raw CV.",
                    "- `jobs.json` is every role already suggested, dismissed, or applied to.",
                    "- `STATUS.md` is a generated summary.",
                    "- `push-consent.json` records whether personal data may be pushed to the current remote.",
                    "- `../cv/base.md` is the canonical CV. Tailored copies live on `apply/<slug>` branches.",
                    "",
                    "Commit these files in a private repository. They contain contact details and salary.",
                    "",
                ]
            ),
        )
    atomic_write(paths["status"], render_status(*load_state(paths)))
    git_ready = is_git(root)
    if args.git and not git_ready:
        result = subprocess.run(["git", "init", str(root)], capture_output=True, text=True)
        if result.returncode != 0:
            fail("git_init_failed", result.stderr.strip() or "git init failed")
        git_ready = True
    emit({"ok": True, "workspace": str(root), "git": git_ready, "created": True})


def cmd_status(args) -> None:
    root = Path(args.workspace).expanduser().resolve()
    paths = workspace_paths(root)
    if not paths["profile"].exists():
        fail("not_initialized", f"No {paths['profile']}. Run init in the job-search repo, not the skill package.")
    profile, jobs = load_state(paths)
    counts: dict[str, int] = {}
    for job in jobs.get("jobs", []):
        status = job.get("status", "unknown")
        counts[status] = counts.get(status, 0) + 1
    emit(
        {
            "ok": True,
            "workspace": str(root),
            "git": is_git(root),
            "branch": current_branch(root),
            "default_branch": default_branch(root),
            "remote": origin_url(root),
            "unanswered": unanswered(profile),
            "cv_analyzed_at": (profile.get("source_cv") or {}).get("analyzed_at"),
            "cv_sha256": (profile.get("source_cv") or {}).get("sha256"),
            "counts": counts,
            "push_consent": read_json(workspace_paths(main_worktree(root))["consent"], None),
        }
    )


def cmd_unanswered(args) -> None:
    root = Path(args.workspace).expanduser().resolve()
    paths = workspace_paths(root)
    profile, _jobs = load_state(paths)
    missing = unanswered(profile)
    emit({"ok": True, "missing": missing, "answered": [key for key in ("cv", "interests", "salary", "work_mode", "location", "work_authorization") if key not in missing]})


def cmd_cv_hash(args) -> None:
    path = Path(args.path).expanduser().resolve()
    if not path.is_file():
        fail("cv_not_found", f"No CV file at {path}")
    emit({"ok": True, "path": str(path), "sha256": sha256_file(path), "bytes": path.stat().st_size})


def cmd_needs_analysis(args) -> None:
    root = Path(args.workspace).expanduser().resolve()
    paths = workspace_paths(root)
    profile, _jobs = load_state(paths)
    cv = Path(args.cv).expanduser().resolve()
    if not cv.is_file():
        fail("cv_not_found", f"No CV file at {cv}")
    digest = sha256_file(cv)
    recorded = (profile.get("source_cv") or {}).get("sha256")
    base_exists = paths["cv_base"].is_file()
    analyze = recorded != digest or not base_exists or not recorded
    reason = "hash_changed" if recorded and recorded != digest else "missing_analysis" if analyze else "unchanged"
    emit(
        {
            "ok": True,
            "analyze": analyze,
            "reason": reason,
            "sha256": digest,
            "recorded_sha256": recorded,
            "base_md": str(paths["cv_base"]),
            "base_md_exists": base_exists,
        }
    )


def cmd_set_source(args) -> None:
    root = Path(args.workspace).expanduser().resolve()
    paths = workspace_paths(root)
    cv = Path(args.path).expanduser().resolve()
    if not cv.is_file():
        fail("cv_not_found", f"No CV file at {cv}")
    with Lock(paths["lock"]):
        profile, jobs = load_state(paths)
        source = profile.setdefault("source_cv", {})
        source["path"] = str(cv)
        source["sha256"] = sha256_file(cv)
        source["bytes"] = cv.stat().st_size
        if args.analyzed:
            source["analyzed_at"] = utc_now()
        save_state(paths, profile, jobs)
    emit({"ok": True, "source_cv": profile["source_cv"]})


def cmd_write_profile(args) -> None:
    root = Path(args.workspace).expanduser().resolve()
    paths = workspace_paths(root)
    incoming = read_json(Path(args.file).expanduser().resolve(), None)
    if not isinstance(incoming, dict):
        fail("invalid_profile", "--file must be a JSON object")
    secrets = scan_secrets(incoming)
    if secrets:
        fail("secret_rejected", "Refusing to store secrets in job-search metadata.", secrets=secrets)
    with Lock(paths["lock"]):
        current, jobs = load_state(paths)
        if args.replace:
            profile = deep_merge(empty_profile(), incoming)
            source = current.get("source_cv") or {}
            if source.get("sha256") and not (profile.get("source_cv") or {}).get("sha256"):
                profile["source_cv"] = source
        else:
            profile = deep_merge(current, incoming)
        if "interests_beyond_cv" in incoming and "interests_answered" not in incoming:
            profile["interests_answered"] = True
        mark_answered(profile)
        if args.mark_analyzed:
            profile.setdefault("source_cv", {})["analyzed_at"] = utc_now()
        save_state(paths, profile, jobs)
    emit({"ok": True, "unanswered": unanswered(profile), "updated_at": profile["updated_at"]})


def cmd_clear_answer(args) -> None:
    root = Path(args.workspace).expanduser().resolve()
    paths = workspace_paths(root)
    allowed = {"interests", "salary", "work_mode", "location", "work_authorization", "cv"}
    if args.key not in allowed:
        fail("bad_key", f"--key must be one of: {', '.join(sorted(allowed))}")
    with Lock(paths["lock"]):
        profile, jobs = load_state(paths)
        if args.key == "interests":
            profile["interests_answered"] = False
        elif args.key == "cv":
            profile["source_cv"] = {}
        else:
            profile.setdefault("preferences", {})[args.key] = {}
        save_state(paths, profile, jobs)
    emit({"ok": True, "cleared": args.key, "unanswered": unanswered(profile)})


def cmd_excluded(args) -> None:
    root = Path(args.workspace).expanduser().resolve()
    paths = workspace_paths(root)
    _profile, jobs = load_state(paths)
    rows = []
    for job in jobs.get("jobs", []):
        reason = still_blocked(job)
        if not reason:
            continue
        rows.append(
            {
                "id": job.get("id"),
                "company": job.get("company"),
                "title": job.get("title"),
                "url": job.get("url"),
                "status": job.get("status"),
                "reason": reason,
            }
        )
    emit({"ok": True, "excluded": rows, "count": len(rows)})


def split_candidates(jobs: dict, incoming: list[dict]) -> tuple[list[dict], list[dict]]:
    known = job_index(jobs)
    known_urls = {normalize_url(job.get("url")): job for job in jobs.get("jobs", []) if job.get("url")}
    keep = []
    dropped = []
    seen = set()
    for raw in incoming:
        if not isinstance(raw, dict):
            dropped.append({"reason": "not_an_object"})
            continue
        item = annotate(raw)
        if not item.get("url") or not item.get("title") or not item.get("company"):
            dropped.append({**item, "reason": "missing_company_title_or_url"})
            continue
        if item["id"] in seen:
            dropped.append({**item, "reason": "duplicate_in_batch"})
            continue
        seen.add(item["id"])
        existing = known.get(item["id"]) or known_urls.get(item["url_normalized"])
        if existing:
            reason = still_blocked(existing)
            if reason:
                dropped.append({**item, "id": existing["id"], "reason": reason, "status": existing.get("status")})
                continue
        keep.append(item)
    return keep, dropped


def cmd_filter(args) -> None:
    root = Path(args.workspace).expanduser().resolve()
    paths = workspace_paths(root)
    _profile, jobs = load_state(paths)
    payload = read_json(Path(args.file).expanduser().resolve(), {})
    candidates = payload.get("candidates", payload if isinstance(payload, list) else None)
    if not isinstance(candidates, list):
        fail("invalid_candidates", "Expected a list or an object with a candidates list")
    keep, dropped = split_candidates(jobs, candidates)
    emit({"ok": True, "keep": keep, "dropped": dropped})


def upsert_job(jobs: dict, item: dict, status: str | None = None) -> dict:
    index = job_index(jobs)
    existing = index.get(item["id"])
    now = utc_now()
    if existing:
        for key in ("company", "title", "url", "location", "work_mode", "salary_text", "avenue", "why", "cover_letter_requested", "cover_letter_evidence"):
            if item.get(key) not in (None, ""):
                existing[key] = item.get(key)
        existing["last_seen"] = now
        if status and existing.get("status") not in TERMINAL:
            existing["status"] = status
            existing["status_at"] = now
        return existing
    created = {
        "id": item["id"],
        "company": item.get("company"),
        "title": item.get("title"),
        "url": item.get("url"),
        "url_normalized": item.get("url_normalized"),
        "location": item.get("location"),
        "work_mode": item.get("work_mode") or "unknown",
        "salary_text": item.get("salary_text") or "",
        "avenue": item.get("avenue") or "",
        "why": item.get("why") or "",
        "cover_letter_requested": bool(item.get("cover_letter_requested")),
        "cover_letter_evidence": item.get("cover_letter_evidence") or "",
        "status": status or "suggested",
        "status_at": now,
        "first_seen": now,
        "last_seen": now,
        "reason": "",
        "branch": "",
    }
    jobs.setdefault("jobs", []).append(created)
    return created


def cmd_present(args) -> None:
    root = Path(args.workspace).expanduser().resolve()
    paths = workspace_paths(root)
    payload = read_json(Path(args.file).expanduser().resolve(), {})
    candidates = payload.get("candidates", payload if isinstance(payload, list) else None)
    if not isinstance(candidates, list):
        fail("invalid_candidates", "Expected a list or an object with a candidates list")
    with Lock(paths["lock"]):
        profile, jobs = load_state(paths)
        keep, dropped = split_candidates(jobs, candidates)
        rows = []
        for number, item in enumerate(keep, start=1):
            saved = upsert_job(jobs, item, status="suggested")
            rows.append(
                {
                    "n": number,
                    "id": saved["id"],
                    "company": saved.get("company"),
                    "title": saved.get("title"),
                    "location": saved.get("location"),
                    "work_mode": saved.get("work_mode"),
                    "salary_text": saved.get("salary_text"),
                    "avenue": saved.get("avenue"),
                    "why": saved.get("why"),
                    "why_unconsidered": item.get("why_unconsidered") or "",
                    "cover_letter_requested": saved.get("cover_letter_requested"),
                    "url": saved.get("url"),
                }
            )
        presented_ids = {row["id"] for row in rows}
        still_open = [
            {
                "id": job.get("id"),
                "company": job.get("company"),
                "title": job.get("title"),
                "url": job.get("url"),
                "first_seen": job.get("first_seen"),
            }
            for job in jobs.get("jobs", [])
            if job.get("status") == "suggested" and job.get("id") not in presented_ids
        ]
        if rows or not paths["presentation"].exists():
            write_json(
                paths["presentation"],
                {"presented_at": utc_now(), "rows": rows},
            )
        save_state(paths, profile, jobs)
    emit({"ok": True, "rows": rows, "dropped": dropped, "still_open": still_open})


def cmd_resolve(args) -> None:
    root = Path(args.workspace).expanduser().resolve()
    paths = workspace_paths(root)
    presentation = read_json(paths["presentation"], None)
    if not presentation:
        fail("nothing_presented", "No last-presentation.json. Present candidates before resolving a reply.")
    rows = presentation.get("rows") or []
    matched = []
    if args.numbers:
        wanted = {int(part) for part in args.numbers.split(",") if part.strip()}
        matched = [row for row in rows if row.get("n") in wanted]
        missing = sorted(wanted - {row.get("n") for row in matched})
        if missing:
            fail("unknown_number", f"These row numbers were not in the last table: {missing}")
    elif args.query:
        needle = args.query.lower()
        matched = [
            row
            for row in rows
            if needle in (row.get("company") or "").lower()
            or needle in (row.get("title") or "").lower()
            or needle in (row.get("url") or "").lower()
        ]
        if not matched:
            fail("no_match", f"No presented row matches {args.query!r}")
    else:
        fail("usage", "Pass --numbers or --query", code=2)
    emit({"ok": True, "matches": matched, "presented_at": presentation.get("presented_at")})


def apply_decision(job: dict, status: str, reason: str, branch: str) -> None:
    if status not in STATUSES:
        fail("bad_status", f"Status must be one of: {', '.join(STATUSES)}")
    now = utc_now()
    job["status"] = status
    job["status_at"] = now
    if reason:
        job["reason"] = reason
    if branch:
        job["branch"] = branch
    if status == "passed":
        job["passed_until"] = (datetime.now(timezone.utc) + timedelta(days=PASS_DAYS)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    else:
        job.pop("passed_until", None)


def cmd_decide(args) -> None:
    root = Path(args.workspace).expanduser().resolve()
    paths = workspace_paths(root)
    decisions = []
    if args.file:
        payload = read_json(Path(args.file).expanduser().resolve(), {})
        decisions = payload.get("decisions", payload if isinstance(payload, list) else None)
        if not isinstance(decisions, list):
            fail("invalid_decisions", "Expected a list or an object with a decisions list")
    else:
        if not args.id or not args.status:
            fail("usage", "Pass --id and --status, or --file", code=2)
        decisions = [
            {
                "id": args.id,
                "status": args.status,
                "reason": args.reason or "",
                "branch": args.branch or "",
                "reopen": args.reopen,
            }
        ]
    with Lock(paths["lock"]):
        profile, jobs = load_state(paths)
        index = job_index(jobs)
        updated = []
        for decision in decisions:
            identifier = decision.get("id")
            status = decision.get("status")
            if identifier not in index:
                fail("unknown_job", f"No recorded job with id {identifier}")
            if status not in STATUSES:
                fail("bad_status", f"Status must be one of: {', '.join(STATUSES)}")
            job = index[identifier]
            if job.get("status") == "dismissed" and status != "dismissed" and not decision.get("reopen"):
                fail(
                    "dismissed_job",
                    f"{job.get('company')} {job.get('title')} was dismissed. Pass reopen=true to bring it back.",
                )
            apply_decision(job, status, decision.get("reason") or "", decision.get("branch") or "")
            updated.append({"id": identifier, "status": status, "company": job.get("company"), "title": job.get("title")})
        save_state(paths, profile, jobs)
    emit({"ok": True, "updated": updated})


def cmd_prepare_apply(args) -> None:
    root = Path(args.workspace).expanduser().resolve()
    paths = workspace_paths(root)
    if not is_git(root):
        fail("not_a_git_repo", "The job-search workspace is not a git repo. Ask before running init --git.")
    base = args.base or default_branch(root)
    if not base:
        fail("no_base", "Could not determine a base branch.")
    branch_now = current_branch(root)
    if branch_now and branch_now != base:
        fail(
            "wrong_branch",
            f"Checkout is {branch_now}, not {base}. Metadata commits belong on the default branch.",
            branch=branch_now,
            default_branch=base,
        )
    dirty = git(root, "status", "--porcelain", "--", ".job-finder", "cv", "applications")
    dirty_lines = [line for line in dirty.stdout.splitlines() if line.strip()]
    if dirty_lines:
        fail(
            "dirty_workspace",
            "Commit job-finder metadata on the default branch before creating an application branch.",
            dirty=dirty_lines,
        )
    slug = slugify(args.slug)
    branch = f"apply/{slug}"
    worktree = root.parent / f"{root.name}.worktrees" / slug
    created = False
    with Lock(paths["lock"]):
        profile, jobs = load_state(paths)
        index = job_index(jobs)
        job = index.get(args.job_id)
        if not job:
            fail("unknown_job", f"No recorded job with id {args.job_id}")
        if job.get("branch"):
            branch = job["branch"]
            leaf = branch.split("/", 1)[1] if "/" in branch else slugify(branch)
            worktree = root.parent / f"{root.name}.worktrees" / leaf
        else:
            suffix = 2
            while git(root, "show-ref", "--verify", "--quiet", f"refs/heads/{branch}").returncode == 0:
                branch = f"apply/{slug}-{suffix}"
                worktree = root.parent / f"{root.name}.worktrees" / f"{slug}-{suffix}"
                suffix += 1
        exists = git(root, "show-ref", "--verify", "--quiet", f"refs/heads/{branch}").returncode == 0
        if exists:
            if not worktree.exists():
                added = git(root, "worktree", "add", str(worktree), branch)
                if added.returncode != 0:
                    fail("worktree_failed", added.stderr.strip() or added.stdout.strip())
        else:
            worktree.parent.mkdir(parents=True, exist_ok=True)
            added = git(root, "worktree", "add", "-b", branch, str(worktree), base)
            if added.returncode != 0:
                fail("worktree_failed", added.stderr.strip() or added.stdout.strip())
            created = True
        job["branch"] = branch
        if job.get("status") not in {"ready", "submitted"}:
            apply_decision(job, "selected", job.get("reason") or "", branch)
        save_state(paths, profile, jobs)
    emit(
        {
            "ok": True,
            "created": created,
            "branch": branch,
            "worktree": str(worktree),
            "base": base,
            "job_id": args.job_id,
        }
    )


def allowed_path(branch: str | None, default: str | None, rel: str) -> str | None:
    if rel.startswith("/") or ".." in Path(rel).parts:
        return "path escapes the workspace"
    on_apply = bool(branch and branch.startswith("apply/"))
    if on_apply:
        if not rel.startswith("applications/"):
            return "application branches may only commit applications/ files"
        return None
    if branch and default and branch != default:
        return f"refusing to commit job-finder metadata on {branch}; checkout {default}"
    allowed = rel.startswith(".job-finder/") or rel.startswith("cv/") or rel in {".job-finder", "cv"}
    if not allowed:
        return "default-branch commits may only include .job-finder/ and cv/"
    if rel.startswith("applications/"):
        return "application files belong on an apply/ branch, not the default branch"
    return None


def cmd_commit(args) -> None:
    root = Path(args.workspace).expanduser().resolve()
    if not is_git(root):
        fail("not_a_git_repo", "Not a git repo. Ask the user before init --git.")
    branch = current_branch(root)
    default = default_branch(root)
    paths = list(args.paths)
    if not paths:
        fail("usage", "Pass at least one --paths entry", code=2)
    problems = []
    for rel in paths:
        reason = allowed_path(branch, default, rel)
        if reason:
            problems.append(f"{rel}: {reason}")
    if problems:
        fail("path_rejected", "Refusing to commit outside the job-finder paths for this branch.", problems=problems)
    missing = [rel for rel in paths if not (root / rel).exists()]
    paths = [rel for rel in paths if (root / rel).exists()]
    if not paths:
        fail("nothing_to_commit", "None of the given paths exist.", missing=missing)
    ignored = []
    for rel in paths:
        check = git(root, "check-ignore", "--", rel)
        if check.returncode == 0:
            ignored.append(rel)
    if ignored:
        fail(
            "gitignored",
            "Refusing to force-add gitignored job-finder files. Use a private job-search repo that does not ignore them.",
            ignored=ignored,
        )
    if args.dry_run:
        emit({"ok": True, "dry_run": True, "branch": branch, "paths": paths, "skipped_missing": missing, "message": args.message})
    add = git(root, "add", "--", *paths)
    if add.returncode != 0:
        fail("git_add_failed", add.stderr.strip() or add.stdout.strip())
    staged = git(root, "diff", "--cached", "--name-only", "--", *paths)
    if not staged.stdout.strip():
        emit({"ok": True, "committed": False, "reason": "clean", "branch": branch, "skipped_missing": missing})
    commit = git(root, "commit", "-m", args.message, "--", *paths)
    if commit.returncode != 0:
        fail("git_commit_failed", commit.stderr.strip() or commit.stdout.strip())
    sha = git(root, "rev-parse", "--short", "HEAD")
    emit({"ok": True, "committed": True, "branch": branch, "sha": sha.stdout.strip(), "paths": paths, "skipped_missing": missing})


def cmd_acknowledge_remote(args) -> None:
    root = Path(args.workspace).expanduser().resolve()
    remote = origin_url(root)
    if not remote:
        fail("no_remote", "No origin remote to acknowledge.")
    allow = args.allow == "yes"
    payload = {"remote": remote, "allows_personal_data": allow, "acknowledged_at": utc_now()}
    write_json(workspace_paths(main_worktree(root))["consent"], payload)
    emit({"ok": True, "consent": payload})


def cmd_push(args) -> None:
    root = Path(args.workspace).expanduser().resolve()
    if not is_git(root):
        fail("not_a_git_repo", "Not a git repo.")
    branch = args.branch or current_branch(root)
    if not branch or branch == "HEAD":
        fail("no_branch", "Pass --branch. Detached HEAD cannot be pushed by this script.")
    if branch.startswith("-") or ".." in branch:
        fail("bad_branch", "Refusing that branch name.")
    remote = origin_url(root)
    if not remote:
        emit({"ok": True, "pushed": False, "reason": "no_remote", "branch": branch})
    consent = read_json(workspace_paths(main_worktree(root))["consent"], None) or {}
    if not consent.get("allows_personal_data") or consent.get("remote") != remote:
        fail(
            "consent_required",
            f"Pushing sends the CV, contact details, and salary to {remote}. Ask the user, then acknowledge-remote --allow yes.",
            remote=remote,
        )
    if args.dry_run:
        emit({"ok": True, "dry_run": True, "pushed": False, "branch": branch, "remote": remote})
    result = git(root, "push", "-u", "origin", branch)
    if result.returncode != 0:
        fail("push_failed", result.stderr.strip() or result.stdout.strip(), branch=branch, remote=remote)
    emit({"ok": True, "pushed": True, "branch": branch, "remote": remote})


def cmd_record_search(args) -> None:
    root = Path(args.workspace).expanduser().resolve()
    paths = workspace_paths(root)
    payload = read_json(Path(args.file).expanduser().resolve(), None)
    if not isinstance(payload, dict):
        fail("invalid_search", "--file must be a JSON object")
    paths["searches"].mkdir(parents=True, exist_ok=True)
    stamp = utc_now().replace(":", "-")
    dest = paths["searches"] / f"{stamp}.json"
    payload["recorded_at"] = utc_now()
    write_json(dest, payload)
    old = sorted(paths["searches"].glob("*.json"))
    for stale in old[:-20]:
        stale.unlink()
    emit({"ok": True, "path": str(dest), "kept": min(len(old), 20)})


def cmd_word_count(args) -> None:
    path = Path(args.file).expanduser().resolve()
    if not path.is_file():
        fail("file_not_found", f"No file at {path}")
    words = re.findall(r"\b[\w']+\b", path.read_text(encoding="utf-8"))
    count = len(words)
    low = args.min
    high = args.max
    emit({"ok": True, "words": count, "in_range": low <= count <= high, "min": low, "max": high, "path": str(path)})


def cmd_paths(args) -> None:
    root = Path(args.workspace).expanduser().resolve()
    paths = workspace_paths(root)
    emit({"ok": True, "paths": {key: str(value) for key, value in paths.items()}})


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Read and update job-finder workspace metadata. Prints JSON to stdout."
    )
    parser.add_argument("--workspace", default=".", help="Job-search repo. Never the skill package unless the user said so.")
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="Create .job-finder metadata if missing")
    init.add_argument("--git", action="store_true", help="git init only when the user agreed")
    init.set_defaults(func=cmd_init)

    status = sub.add_parser("status", help="Show workspace, unanswered questions, and decision counts")
    status.set_defaults(func=cmd_status)

    unanswered = sub.add_parser("unanswered", help="List preference questions that have no saved answer")
    unanswered.set_defaults(func=cmd_unanswered)

    cv_hash = sub.add_parser("cv-hash", help="SHA-256 a CV file")
    cv_hash.add_argument("--path", required=True)
    cv_hash.set_defaults(func=cmd_cv_hash)

    needs = sub.add_parser("needs-analysis", help="Whether the CV must be read again")
    needs.add_argument("--cv", required=True)
    needs.set_defaults(func=cmd_needs_analysis)

    source = sub.add_parser("set-source", help="Record the CV path and hash")
    source.add_argument("--path", required=True)
    source.add_argument("--analyzed", action="store_true")
    source.set_defaults(func=cmd_set_source)

    write = sub.add_parser("write-profile", help="Merge profile JSON and refresh answered flags")
    write.add_argument("--file", required=True)
    write.add_argument("--replace", action="store_true")
    write.add_argument("--mark-analyzed", action="store_true")
    write.set_defaults(func=cmd_write_profile)

    clear = sub.add_parser("clear-answer", help="Forget one saved answer so it will be asked again")
    clear.add_argument("--key", required=True)
    clear.set_defaults(func=cmd_clear_answer)

    excluded = sub.add_parser("excluded", help="Jobs search agents must not suggest again")
    excluded.set_defaults(func=cmd_excluded)

    filt = sub.add_parser("filter", help="Drop candidates already dismissed, applied, or awaiting a decision")
    filt.add_argument("--file", required=True)
    filt.set_defaults(func=cmd_filter)

    present = sub.add_parser("present", help="Number new candidates and remember them as suggested")
    present.add_argument("--file", required=True)
    present.set_defaults(func=cmd_present)

    resolve = sub.add_parser("resolve", help="Map a later reply back to the last presented table")
    resolve.add_argument("--numbers")
    resolve.add_argument("--query")
    resolve.set_defaults(func=cmd_resolve)

    decide = sub.add_parser("decide", help="Record apply, dismiss, ready, or submitted")
    decide.add_argument("--file")
    decide.add_argument("--id")
    decide.add_argument("--status")
    decide.add_argument("--reason", default="")
    decide.add_argument("--branch", default="")
    decide.add_argument("--reopen", action="store_true")
    decide.set_defaults(func=cmd_decide)

    prepare = sub.add_parser("prepare-apply", help="Create apply/<slug> in a worktree")
    prepare.add_argument("--slug", required=True)
    prepare.add_argument("--job-id", required=True)
    prepare.add_argument("--base")
    prepare.set_defaults(func=cmd_prepare_apply)

    commit = sub.add_parser("commit", help="Commit only job-finder paths")
    commit.add_argument("--message", required=True)
    commit.add_argument("--paths", nargs="+", required=True)
    commit.add_argument("--dry-run", action="store_true")
    commit.set_defaults(func=cmd_commit)

    ack = sub.add_parser("acknowledge-remote", help="Record push consent for the current origin")
    ack.add_argument("--allow", required=True, choices=("yes", "no"))
    ack.set_defaults(func=cmd_acknowledge_remote)

    push = sub.add_parser("push", help="Push one branch. Never force-pushes.")
    push.add_argument("--branch")
    push.add_argument("--dry-run", action="store_true")
    push.set_defaults(func=cmd_push)

    search = sub.add_parser("record-search", help="Save a search run and keep the latest 20")
    search.add_argument("--file", required=True)
    search.set_defaults(func=cmd_record_search)

    words = sub.add_parser("word-count", help="Check a cover letter is about 200 words")
    words.add_argument("--file", required=True)
    words.add_argument("--min", type=int, default=160)
    words.add_argument("--max", type=int, default=220)
    words.set_defaults(func=cmd_word_count)

    paths = sub.add_parser("paths", help="Print workspace paths")
    paths.set_defaults(func=cmd_paths)
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.func(args)
    except SystemExit:
        raise
    except subprocess.CalledProcessError as exc:
        fail("command_failed", exc.stderr.strip() or str(exc))
    except OSError as exc:
        fail("os_error", str(exc))


if __name__ == "__main__":
    main()
