# job-finder

Skills that help an agent run a job search without asking the same questions twice, and without suggesting a role you already dismissed or applied to.

Install the set:

```bash
npx skills add OWNER/job-finder --all
```

Or name them:

```bash
npx skills add OWNER/job-finder --skill job-finder --skill job-finder-profile --skill job-finder-search --skill job-finder-apply
```

From a local checkout, before the repo is on GitHub:

```bash
npx skills add . --skill job-finder --skill job-finder-profile --skill job-finder-search --skill job-finder-apply
```

`npx skills` is the [skills.sh](https://skills.sh) CLI. It discovers `skills/<name>/SKILL.md`. Once the repo is public, installs show up on the leaderboard. Replace `OWNER` with the GitHub owner.

Any new skill in this repo stays on the `job-finder-` prefix.

## What you tell the agent

Give it a CV, what you want that the CV does not already show, a salary floor, and whether you will work in an office, hybrid, or remote. It records those answers in a private job-search git repo.

Later runs read that metadata. They do not re-read the CV unless the file changed, and they do not ask for salary or location again unless you change them.

A search uses four passes. One of them is required to look outside the titles you would have typed yourself. You get a short description and a table. You pick the rows. For each pick, the agent writes a tailored CV on its own `apply/<slug>` branch and pushes it. If the listing asks for a short cover letter, including an optional one, it writes about 200 words in plain language.

It does not submit the application to the employer unless you explicitly ask it to submit that one.

## Skills

| Skill | When it runs |
| --- | --- |
| `job-finder` | The search itself: profile, table, decision, push |
| `job-finder-profile` | First CV read, and later edits to salary, location, work mode, or interests |
| `job-finder-search` | Public listings, including the unconsidered avenue |
| `job-finder-apply` | Tailored CV, optional letter, one branch per job |

## Workspace

Run the skills in a separate private git repo, not in this package. This package gitignores `.job-finder/`, `cv/`, and `applications/` so a trial here is not published with the skills.

The agent creates:

```text
.job-finder/profile.json    CV index and saved answers
.job-finder/jobs.json       suggested, dismissed, ready, submitted
.job-finder/STATUS.md       generated summary
cv/base.md                  faithful CV, analyzed once
applications/<slug>/        only on apply/<slug> branches
```

Dismissed and applied roles are filtered out of the next search. Roles you saw and did not decide on come back under "still open", not as new results.

## Checks

```bash
python3 tests/test_workspace.py
```

The workspace script is copied into each skill so a single-skill install still has it. The test fails if the copies drift.
