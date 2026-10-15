#!/usr/bin/env python3
"""Behavioral checks for the job-finder workspace script."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "job-finder" / "scripts" / "workspace.py"
COPIES = [
    ROOT / "skills" / "job-finder-profile" / "scripts" / "workspace.py",
    ROOT / "skills" / "job-finder-search" / "scripts" / "workspace.py",
    ROOT / "skills" / "job-finder-apply" / "scripts" / "workspace.py",
]
SKILLS = [
    "job-finder",
    "job-finder-profile",
    "job-finder-search",
    "job-finder-apply",
]


def run(workspace: Path, *args: str, check: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python3", str(SCRIPT), "--workspace", str(workspace), *args],
        capture_output=True,
        text=True,
        check=check,
    )


def payload(result: subprocess.CompletedProcess[str]) -> dict:
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(f"not JSON (exit {result.returncode}): {result.stdout}\n{result.stderr}") from exc


class SkillPackageTest(unittest.TestCase):
    def test_script_copies_match(self) -> None:
        digest = hashlib.sha256(SCRIPT.read_bytes()).hexdigest()
        for copy in COPIES:
            self.assertTrue(copy.is_file(), copy)
            self.assertEqual(hashlib.sha256(copy.read_bytes()).hexdigest(), digest, copy)

    def test_frontmatter(self) -> None:
        for name in SKILLS:
            text = (ROOT / "skills" / name / "SKILL.md").read_text(encoding="utf-8")
            self.assertTrue(text.startswith("---\n"), name)
            front, _body = text.split("---\n", 2)[1:]
            fields = {}
            for line in front.splitlines():
                if not line.strip() or line.startswith(" "):
                    continue
                key, value = line.split(":", 1)
                fields[key] = value.strip().strip('"')
            self.assertEqual(fields["name"], name)
            self.assertGreater(len(fields["description"]), 40, name)
            self.assertLessEqual(len(fields["description"]), 1024, name)
            self.assertIn("job-finder", name)


class WorkspaceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.ws = Path(self.tmp.name) / "search"
        self.ws.mkdir()
        subprocess.run(["git", "init", "-b", "main", str(self.ws)], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(self.ws), "config", "user.email", "test@example.com"], check=True)
        subprocess.run(["git", "-C", str(self.ws), "config", "user.name", "Test User"], check=True)
        result = run(self.ws, "init")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.addCleanup(self._cleanup_worktrees)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _cleanup_worktrees(self) -> None:
        worktrees = self.ws.parent / f"{self.ws.name}.worktrees"
        if worktrees.exists():
            subprocess.run(["git", "-C", str(self.ws), "worktree", "prune"], capture_output=True)
            shutil.rmtree(worktrees, ignore_errors=True)

    def test_unanswered_until_profile_is_saved(self) -> None:
        missing = payload(run(self.ws, "unanswered"))["missing"]
        self.assertIn("salary", missing)
        self.assertIn("cv", missing)
        patch = self.ws / "patch.json"
        patch.write_text(
            json.dumps(
                {
                    "identity": {"name": "Ada Okonkwo"},
                    "current_title": "Staff Software Engineer",
                    "normal_flow_titles": ["Staff Software Engineer"],
                    "interests_beyond_cv": ["compilers"],
                    "preferences": {
                        "salary": {"currency": "GBP", "minimum": 120000, "target": 140000, "period": "year"},
                        "work_mode": {"accepts": ["remote"], "preferred": "remote"},
                        "location": {"home": "London", "willing_to_relocate": False, "cities": ["London"]},
                        "work_authorization": {"status": "prefer_not_to_say"},
                    },
                }
            ),
            encoding="utf-8",
        )
        saved = payload(run(self.ws, "write-profile", "--file", str(patch)))
        self.assertTrue(saved["ok"])
        self.assertEqual(saved["unanswered"], ["cv"])

    def test_cv_is_not_reread_when_hash_matches(self) -> None:
        cv = self.ws / "cv" / "source" / "cv.md"
        cv.parent.mkdir(parents=True, exist_ok=True)
        cv.write_text("# Ada\n\nEngineer\n", encoding="utf-8")
        (self.ws / "cv" / "base.md").write_text("# Ada\n", encoding="utf-8")
        first = payload(run(self.ws, "needs-analysis", "--cv", str(cv)))
        self.assertTrue(first["analyze"])
        run(self.ws, "set-source", "--path", str(cv), "--analyzed", check=True)
        second = payload(run(self.ws, "needs-analysis", "--cv", str(cv)))
        self.assertFalse(second["analyze"])
        self.assertEqual(second["reason"], "unchanged")
        cv.write_text("# Ada\n\nChanged\n", encoding="utf-8")
        third = payload(run(self.ws, "needs-analysis", "--cv", str(cv)))
        self.assertTrue(third["analyze"])
        self.assertEqual(third["reason"], "hash_changed")

    def test_secrets_are_rejected(self) -> None:
        patch = self.ws / "secret.json"
        patch.write_text(json.dumps({"identity": {"ssn": "123-45-6789"}}), encoding="utf-8")
        result = run(self.ws, "write-profile", "--file", str(patch))
        self.assertEqual(result.returncode, 1)
        self.assertEqual(payload(result)["error"], "secret_rejected")

    def test_clear_answer_makes_the_question_return(self) -> None:
        patch = self.ws / "patch.json"
        patch.write_text(
            json.dumps({"preferences": {"salary": {"minimum": 100000, "currency": "USD", "period": "year"}}}),
            encoding="utf-8",
        )
        run(self.ws, "write-profile", "--file", str(patch), check=True)
        self.assertNotIn("salary", payload(run(self.ws, "unanswered"))["missing"])
        cleared = payload(run(self.ws, "clear-answer", "--key", "salary"))
        self.assertIn("salary", cleared["unanswered"])

    def test_dismissed_jobs_are_not_presented_again(self) -> None:
        candidates = self.ws / "candidates.json"
        candidates.write_text(
            json.dumps(
                {
                    "candidates": [
                        {
                            "company": "Northwind",
                            "title": "Staff Engineer",
                            "url": "https://jobs.example/n?utm_source=board",
                            "location": "London",
                            "work_mode": "remote",
                            "avenue": "direct",
                            "why": "Matches the current title.",
                        },
                        {
                            "company": "Contoso",
                            "title": "Compiler Engineer",
                            "url": "https://jobs.example/c",
                            "location": "Remote",
                            "work_mode": "remote",
                            "avenue": "unconsidered",
                            "why": "Interest, not a prior title.",
                            "why_unconsidered": "The surprise is the function, not another staff title.",
                        },
                    ]
                }
            ),
            encoding="utf-8",
        )
        presented = payload(run(self.ws, "present", "--file", str(candidates)))
        self.assertEqual([row["n"] for row in presented["rows"]], [1, 2])
        northwind = presented["rows"][0]["id"]
        again = payload(run(self.ws, "present", "--file", str(candidates)))
        self.assertEqual(again["rows"], [])
        self.assertEqual(len(again["still_open"]), 2)
        run(self.ws, "decide", "--id", northwind, "--status", "dismissed", "--reason", "location", check=True)
        tracking = self.ws / "tracking.json"
        tracking.write_text(
            json.dumps(
                {
                    "candidates": [
                        {
                            "company": "Northwind",
                            "title": "Staff Engineer",
                            "url": "https://jobs.example/n?utm_source=other",
                            "location": "London",
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        filtered = payload(run(self.ws, "filter", "--file", str(tracking)))
        self.assertEqual(filtered["keep"], [])
        self.assertEqual(filtered["dropped"][0]["reason"], "dismissed")
        resolved = payload(run(self.ws, "resolve", "--numbers", "2"))
        self.assertEqual(resolved["matches"][0]["company"], "Contoso")

    def test_commit_rejects_unrelated_paths_and_push_needs_consent(self) -> None:
        note = self.ws / ".job-finder" / "profile.json"
        self.assertTrue(note.is_file())
        bad = run(self.ws, "commit", "--message", "nope", "--paths", "README.md")
        self.assertEqual(payload(bad)["error"], "path_rejected")
        good = run(
            self.ws,
            "commit",
            "--message", "job-finder: record profile",
            "--paths",
            ".job-finder/profile.json",
            ".job-finder/jobs.json",
            ".job-finder/STATUS.md",
        )
        self.assertTrue(payload(good)["committed"], good.stderr + good.stdout)
        pushed = run(self.ws, "push", "--branch", "main")
        self.assertFalse(payload(pushed)["pushed"])
        self.assertEqual(payload(pushed)["reason"], "no_remote")

    def test_prepare_apply_uses_a_separate_branch(self) -> None:
        candidates = self.ws / "candidates.json"
        candidates.write_text(
            json.dumps(
                {
                    "candidates": [
                        {
                            "company": "Northwind",
                            "title": "Staff Engineer",
                            "url": "https://jobs.example/apply",
                            "avenue": "direct",
                            "why": "Direct match.",
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        presented = payload(run(self.ws, "present", "--file", str(candidates)))
        job_id = presented["rows"][0]["id"]
        run(
            self.ws,
            "commit",
            "--message", "job-finder: suggest candidates",
            "--paths",
            ".job-finder/jobs.json",
            ".job-finder/profile.json",
            ".job-finder/STATUS.md",
            ".job-finder/README.md",
            ".job-finder/last-presentation.json",
            ".job-finder/.gitignore",
            check=True,
        )
        prepared = payload(run(self.ws, "prepare-apply", "--slug", "Northwind Staff Engineer", "--job-id", job_id))
        self.assertTrue(prepared["ok"], prepared)
        self.assertEqual(prepared["branch"], "apply/northwind-staff-engineer")
        self.assertTrue(Path(prepared["worktree"]).is_dir())
        branch = subprocess.run(
            ["git", "-C", str(self.ws), "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertEqual(branch.stdout.strip(), "main")
        letter = Path(prepared["worktree"]) / "applications" / "northwind-staff-engineer" / "cover-letter.md"
        letter.parent.mkdir(parents=True, exist_ok=True)
        letter.write_text(("word " * 180).strip() + "\n", encoding="utf-8")
        counted = payload(run(self.ws, "word-count", "--file", str(letter)))
        self.assertTrue(counted["in_range"])
        self.assertEqual(counted["words"], 180)
        # Consent is stored on the main checkout. Push from the worktree must see it.
        subprocess.run(
            ["git", "-C", str(self.ws), "remote", "add", "origin", "git@example.com:private/job-search.git"],
            check=True,
        )
        missing = run(Path(prepared["worktree"]), "push", "--branch", prepared["branch"])
        self.assertEqual(payload(missing)["error"], "consent_required")
        acknowledged = payload(run(self.ws, "acknowledge-remote", "--allow", "yes"))
        self.assertTrue(acknowledged["consent"]["allows_personal_data"])
        seen = payload(run(Path(prepared["worktree"]), "push", "--dry-run", "--branch", prepared["branch"]))
        self.assertTrue(seen["ok"], seen)
        self.assertEqual(seen["remote"], "git@example.com:private/job-search.git")


if __name__ == "__main__":
    unittest.main()
