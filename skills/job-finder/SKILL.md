---
name: job-finder
description: Find jobs from a saved CV profile and prepare applications only for roles the user picks. Use when the user wants to find a job, search for roles, see openings, continue a job search, ask what to apply to, check application status, or says job-finder, even if they never say skill. Also use for another search, new listings, or where the search left off. Do not use for interview prep, offer negotiation, or resume writing with no target role. Do not submit an application to an employer unless the user explicitly says to submit that one.
license: MIT
compatibility: Requires git and Python 3.9+. Job search needs network access. Does not submit applications.
metadata:
  version: "1.0.0"
---

# Job Finder

Run the search. Do not collect a second copy of salary, location, or CV notes in the chat and hope you remember them next time. The workspace script is the memory.

This package is four skills, all prefixed `job-finder`. Load the phase you are in:

- `job-finder-profile` before reading a CV or asking about salary, location, work mode, or interests
- `job-finder-search` before looking for listings
- `job-finder-apply` after the user picks roles, or when they already named a posting to tailor

If the host can load skills, load those ids. Otherwise read the sibling `SKILL.md` under `skills/` or next to this install. If a sibling is missing, stop and give the install command. Do not invent a second metadata format.

```bash
npx skills add <owner>/job-finder --skill job-finder --skill job-finder-profile --skill job-finder-search --skill job-finder-apply
```

New skills in this package stay on the `job-finder-` prefix.

## Workspace

The workspace is the user's private job-search git repo. It is not the skill install directory and not a checkout whose job is to publish these skills.

Use the current directory only when `.job-finder/profile.json` is already there. Otherwise ask which directory to use, and create it only after they answer. Never write `.job-finder/` into a directory that contains `skills/job-finder/SKILL.md`, or into the directory that holds this skill's `scripts/workspace.py`, unless they explicitly say that directory is their job-search repo.

The script is `scripts/workspace.py` next to this file. Pass `--workspace` on every call. The shell's current directory is not a substitute.

```bash
python3 scripts/workspace.py --workspace "$WS" status
```

`status` is the first call on every run. It reports unanswered questions, the branch, the remote, and decision counts. Trust it over the conversation.

## Checklist

- [ ] Resolve `$WS` and say which directory you are using
- [ ] `status`. If it errors with `not_initialized`, run `init` there. Run `init --git` only after they agree this directory should become a git repo
- [ ] Load `job-finder-profile` and finish every missing answer it still needs before searching
- [ ] Load `job-finder-search`, then present from the script's JSON, not from a renumbered copy
- [ ] Commit the suggested rows before you wait, so a crashed chat still remembers the table
- [ ] Stop and ask which rows to apply to
- [ ] Load `job-finder-apply` only after they answer
- [ ] Commit decisions. Push only after push consent

Do not start a search while `unanswered` still lists `cv`, `salary`, `work_mode`, or `location`, unless they tell you to search with what you have. Record that those fields are unknown. Do not invent a salary floor.

## Present

`present` writes `.job-finder/last-presentation.json` and marks new rows as `suggested`. Render that JSON. Do not renumber it. A later reply of "2 and 5" is resolved with `resolve`, including after the chat is compacted.

```markdown
## This search

<2-4 sentences. Say how many listings were dropped because they were already dismissed, selected, or applied to. Name the unconsidered avenue if one survived.>

## Candidates

| # | Company | Role | Mode | Location | Salary | Avenue | Why | Letter | Link |
|---|---------|------|------|----------|--------|--------|-----|--------|------|

## Still open

<Omit when `still_open` is empty. These are not new. One line each.>

## Outside the usual search

<One sentence per unconsidered row, from `why_unconsidered`. Skip this section if there are none.>
```

The Letter column is yes only when `cover_letter_requested` is true.

`present` has already written `jobs.json`. Commit it before you wait:

```bash
python3 scripts/workspace.py --workspace "$WS" commit \
  --message "job-finder: suggest candidates" \
  --paths .job-finder/profile.json .job-finder/jobs.json .job-finder/STATUS.md .job-finder/last-presentation.json .job-finder/README.md .job-finder/.gitignore
```

Drop a path the script says is missing. Then ask, and wait:

> Which of these do you want to apply to? Numbers are fine. Say dismiss next to any you never want to see again. I will not submit anything to an employer.

Leaving a row unmentioned does not dismiss it. It stays `suggested` and shows up under Still open next time. Say that when you record the reply. Dismiss only rows they reject.

## Decisions

Map the reply with `resolve --numbers` or `resolve --query` before writing status. Then confirm the plan in one or two sentences: which branches, which cover letters, and that nothing will be submitted. Then follow `job-finder-apply`.

Commit metadata on the default branch after decisions, including a dismiss with no branch:

```bash
python3 scripts/workspace.py --workspace "$WS" commit \
  --message "job-finder: record decisions" \
  --paths .job-finder/profile.json .job-finder/jobs.json .job-finder/STATUS.md .job-finder/last-presentation.json
```

If the commit fails because git has no user.name, stop and tell them. Do not set their identity.

## Push

Pushing sends the CV, contact details, and salary to origin. Before the first push, show the remote URL and ask whether that remote should receive this data. Record the answer:

```bash
python3 scripts/workspace.py --workspace "$WS" acknowledge-remote --allow yes
python3 scripts/workspace.py --workspace "$WS" commit \
  --message "job-finder: record push consent" \
  --paths .job-finder/push-consent.json
python3 scripts/workspace.py --workspace "$WS" push --branch apply/<slug>
```

No remote means commit locally and say there is nothing to push. Never force-push. A failed push stays a local branch; do not claim it was pushed.

Also push the default branch after consent, so the next clone sees dismissals and applications. They asked for application branches to be pushed, and for decisions to survive the next search.

## Status

"Where am I?", "what did I dismiss?", and "what have I applied to?" are this skill. Read `status` and `.job-finder/STATUS.md`. Do not open the raw CV to answer them.

## Gotchas

- A job with no opened listing page is not a candidate. Search snippets and memory are not sources.
- Do not upload the CV, create a board account, or log in during search.
- Do not put every application on one branch. One job, one `apply/<slug>` branch.
- Do not commit unrelated dirty files. The script rejects paths outside `.job-finder/` and `cv/` on the default branch, and outside `applications/` on an apply branch.
- `ready` means the branch has materials. `submitted` means the user said they sent the application. Neither is a suggestion next time. Do not mark `submitted` yourself.
- Optional cover letter on the listing still gets a letter. No cover-letter field means no letter, unless they ask.
- Interests that are not on the CV stay interests. They are not experience.
