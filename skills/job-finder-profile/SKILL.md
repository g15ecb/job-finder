---
name: job-finder-profile
description: Extract a CV once into job-search metadata and remember salary, location, work mode, and interests so later runs do not ask again. Use when the user provides a CV or resume, asks to analyze or update their profile, changes salary, remote hybrid or office preference, location, work authorization, or interests, or says to update job-finder metadata. Skip the raw CV when the saved hash still matches.
license: MIT
compatibility: Requires Python 3.9+ and git when committing the profile. Reads PDF or docx with whatever the host can already read.
metadata:
  version: "1.0.0"
---

# Job Finder Profile

Search should run on a short profile, not on a fresh reading of the CV. The raw file is for the first analysis and for a later hash check. Tailoring reads `cv/base.md`, which is a faithful copy, not a rewrite.

The script is `scripts/workspace.py` in this skill. Pass `--workspace` as the job-search repo, never the skill install directory. See `job-finder` for how that repo is chosen.

```bash
python3 scripts/workspace.py --workspace "$WS" status
python3 scripts/workspace.py --workspace "$WS" unanswered
```

## When they hand you a CV

Copy it to `cv/source/` under its original name. Then:

```bash
python3 scripts/workspace.py --workspace "$WS" needs-analysis --cv "$WS/cv/source/<file>"
```

`analyze: false` means the hash matches and `cv/base.md` exists. Do not open the CV. Use `.job-finder/profile.json`.

`analyze: true` means read it once. Use the host's PDF or docx skill when the file needs one. Read [references/extract.md](references/extract.md) before writing the profile, and [references/schema.md](references/schema.md) for the JSON shape.

Write `cv/base.md` as a transcription. Same employers, titles, dates, and metrics. No reordering for a job that has not been chosen yet.

Then:

```bash
python3 scripts/workspace.py --workspace "$WS" set-source --path "$WS/cv/source/<file>" --analyzed
python3 scripts/workspace.py --workspace "$WS" write-profile --file /tmp/profile-patch.json --mark-analyzed
```

`--mark-analyzed` is what stops the next run from reading the CV again. Forgetting it is the usual reason a later search opens the PDF.

## Questions

Ask only keys in `unanswered`. Ask them in one message. If this message already answers some, record those and ask the rest. Do not ask one question per turn.

- `cv`: path to the file, if there is no hash yet
- `interests`: what they want that the CV does not already show. `none` is an answer. Record it as `"interests_beyond_cv": []` so it is not asked again
- `salary`: currency, minimum, target, and `year`, `day`, or `hour`. If they refuse a floor, set `unspecified: true` and keep their words in `notes`. Do not invent a number
- `work_mode`: which of `office`, `hybrid`, and `remote` they accept, which they prefer, and `office_days_max` if they have one
- `location`: home city, whether they will relocate, office cities, and countries they will take a remote job in
- `work_authorization`: where they can work without new sponsorship, or `prefer_not_to_say`. Do not infer this from their city

Do not search while `cv`, `salary`, `work_mode`, or `location` are still missing, unless they say to search anyway. Interests and work authorization must still be recorded, even as none or prefer-not-to-say, so the next run does not ask.

`other` is for a constraint they volunteer (notice period, start date, contract versus permanent). Do not interview them for a form's worth of extras.

## Updates

A later "my minimum is 150k" or "I'll do two days in London" is this skill, not a new search. Patch only the changed block with `write-profile`. Lists replace. To make a question come back:

```bash
python3 scripts/workspace.py --workspace "$WS" clear-answer --key salary
```

Keys: `interests`, `salary`, `work_mode`, `location`, `work_authorization`, `cv`. Clearing `cv` does not delete `cv/base.md`. The next `needs-analysis` reads the file again only when the hash changes or the base file is gone. If they say the analysis is wrong, clear is not required: patch the bad field, and re-read the CV only for the fact you are correcting.

## Commit

Commit on the default branch after a real change. Do not commit an empty merge.

```bash
python3 scripts/workspace.py --workspace "$WS" commit \
  --message "job-finder: update salary" \
  --paths .job-finder/profile.json .job-finder/jobs.json .job-finder/STATUS.md cv/base.md
```

Add `cv/source/<file>` to `--paths` on the first analysis. Tell them this commit stores the CV and salary in the repo, and that you will not push until they accept the remote. Push rules live in `job-finder`.

If `commit` returns `gitignored`, this repo is ignoring the memory. Do not force-add. Ask them for a private job-search repo.

## Gotchas

- Do not store a national insurance number, social security number, passport number, password, or private key. The script rejects them. Leave them out even if the CV has them.
- `normal_flow_titles` are the searches they would type themselves. Keep that list narrow. The unconsidered search is supposed to leave it.
- A skill mentioned only as an interest is not a skill on the profile's experience. Put it in `interests_beyond_cv`.
- Null beats a guessed graduation year. Add the field name to `uncertain`.
