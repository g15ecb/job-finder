---
name: job-finder-apply
description: Write a tailored CV for each chosen job and an informal cover letter of about 200 words when the listing asks for one, then push each job on its own git branch. Use when the user picks roles to apply to, asks for a tailored resume or cover letter for a posting, or a dismiss or apply decision needs recording. Never invent experience. Do not submit to the employer unless the user explicitly says to submit.
license: MIT
compatibility: Requires git and Python 3.9+. Push needs a remote and recorded consent. Does not submit applications.
metadata:
  version: "1.0.0"
---

# Job Finder Apply

One job, one branch. The default branch keeps the decision. The apply branch keeps the tailored files. Do not mix those commits, and do not submit the application to the employer as part of this skill.

The script is `scripts/workspace.py` in this skill. `--workspace` is the job-search repo. Application commits use the worktree path `prepare-apply` returns, not the default checkout.

If the user replied with table numbers or a company name, resolve it before deciding. The last table is in `.job-finder/last-presentation.json` even if the chat was compacted.

```bash
python3 scripts/workspace.py --workspace "$WS" resolve --numbers 1,4
```

## Dismiss

```bash
python3 scripts/workspace.py --workspace "$WS" decide \
  --id <id> --status dismissed --reason "location"
python3 scripts/workspace.py --workspace "$WS" commit \
  --message "job-finder: dismiss Northwind Staff Engineer" \
  --paths .job-finder/profile.json .job-finder/jobs.json .job-finder/STATUS.md
```

No branch. A dismissed job is not suggested again unless they ask to reopen it (`decide --reopen --status suggested`).

## Apply

Confirm the plan, then do each selected job fully before the next. `prepare-apply` dirties `jobs.json` on the default branch, and the next call refuses a dirty tree.

Read [references/tailor.md](references/tailor.md) before writing the CV. Read [references/cover-letter.md](references/cover-letter.md) only when the listing asks for a letter, a personal statement, or a short "why us" answer, including when that field is optional. No such field, no letter, unless the user asked for one.

Re-fetch the listing if `cover_letter_requested` is missing or the evidence quote is empty. If the page is gone, say so and write the CV from the saved fields. Do not invent a letter requirement.

```bash
python3 scripts/workspace.py --workspace "$WS" prepare-apply \
  --slug "<company>-<title>" --job-id <id>
```

That returns `worktree` and `branch`. In the worktree, write:

- `applications/<slug>/cv.md` from [assets/cv-template.md](assets/cv-template.md), using facts from `$WS/cv/base.md` only
- `applications/<slug>/listing.md` with the URL, fetch time, title, company, and the quotes you tailored against
- `applications/<slug>/cover-letter.md` only when a letter is required by the rule above

```bash
python3 scripts/workspace.py --workspace "$WT" word-count \
  --file applications/<slug>/cover-letter.md
```

`in_range` must be true (160–220 words) before you commit the letter. Rewrite the letter, not the threshold.

Commit on the worktree, not the default checkout:

```bash
python3 scripts/workspace.py --workspace "$WT" commit \
  --message "job-finder: tailor CV for Northwind Staff Engineer" \
  --paths applications/<slug>/cv.md applications/<slug>/listing.md
```

Add the cover letter path only if you wrote one.

Then commit the decision on the default checkout. `prepare-apply` already set `selected` and the branch name. After the worktree commit succeeds, mark it ready:

```bash
python3 scripts/workspace.py --workspace "$WS" decide \
  --id <id> --status ready --branch apply/<slug>
python3 scripts/workspace.py --workspace "$WS" commit \
  --message "job-finder: mark ready Northwind Staff Engineer" \
  --paths .job-finder/profile.json .job-finder/jobs.json .job-finder/STATUS.md
```

`ready` means the materials are on a branch. It does not mean the employer received them.

## Push

Show the origin URL once and ask before the first push. The branch contains the CV.

```bash
python3 scripts/workspace.py --workspace "$WS" acknowledge-remote --allow yes
python3 scripts/workspace.py --workspace "$WS" commit \
  --message "job-finder: record push consent" \
  --paths .job-finder/push-consent.json
python3 scripts/workspace.py --workspace "$WS" push --branch apply/<slug>
```

Push from the job-search repo, not the worktree path. The consent file lives in the main checkout, and `git push origin apply/<slug>` publishes that branch without checking it out.

Push the default branch too after consent, so the next search sees `ready` and `dismissed`. Never force-push. If push fails, report the local branch and the error. Do not retry with `--force`.

No origin: say the branch is local only.

## Submit

Do not open an application form, create an account, or click submit unless the user explicitly asks you to submit that specific job. If they do, show every answer you would send and wait for a yes. A tailored branch is not that yes.

When they later say they submitted it:

```bash
python3 scripts/workspace.py --workspace "$WS" decide --id <id> --status submitted
```

Commit that the same way as other decisions. `submitted` is also excluded from future suggestions.

## Gotchas

- Do not edit `cv/base.md` on the apply branch. The variant is `applications/<slug>/cv.md`.
- Do not copy an interest into Experience. If the listing cares about an interest, it can appear as a labeled interest line, or not at all.
- Do not change a metric, a date, a title, or an employer. Reorder and cut. Cutting a bullet is allowed. Adding one is not.
- If `prepare-apply` returns `wrong_branch` or `dirty_workspace`, fix that on the default checkout before creating another worktree. Do not stash unrelated work.
- If `commit` returns `gitignored`, stop. Do not force-add personal files past a gitignore.
