---
name: job-finder-search
description: Search public job listings with several agents, including one that proposes career avenues outside the user's normal titles. Use when job-finder needs candidates or the user asks to search for jobs, find openings, or look again. Drop roles already dismissed, selected, or applied to. Return only listings whose pages were actually opened.
license: MIT
compatibility: Requires Python 3.9+ and network access to public job pages. No login, no CV upload.
metadata:
  version: "1.0.0"
---

# Job Finder Search

A single search collapses onto the titles already on the CV. Run four avenues, and keep the unconsidered one separate so the others do not eat it.

Read `.job-finder/profile.json` and the exclusion list. Do not open the CV. If `job-finder-profile` has not recorded `cv`, `salary`, `work_mode`, and `location`, stop and load that skill unless the user said to search with unknowns. Unknown salary means do not filter on salary. Do not invent a floor.

```bash
python3 scripts/workspace.py --workspace "$WS" excluded
```

Pass `excluded` into every avenue. It includes dismissed, selected, ready, submitted, passed-until-the-date, and already suggested roles. Suggested roles are not new. The presenter lists them as still open.

## Avenues

Load [references/agents.md](references/agents.md) and give each avenue its brief plus the profile JSON and the exclusion list.

1. `direct` — titles they would search themselves (`normal_flow_titles`), at the seniority and work mode they asked for
2. `adjacent` — a neighboring function the CV can already support
3. `interest` — driven by `interests_beyond_cv`, labeled as interest rather than proven work
4. `unconsidered` — an employer type, function, or shape of work they would not open a board and type. This one is required. It does not get to return "the same title, slightly more senior" and call it a surprise

Spawn all four in one turn when the host can run subagents. If it cannot, run them yourself and run `unconsidered` last so the earlier titles do not anchor it.

Each avenue: at most 8 queries, at most 8 opened pages, at most 5 returned listings. A page that does not load is not a result. A snippet is not a result. Do not log in, create an account, or upload the CV. Skip boards that only show the posting behind an account.

## After the avenues

Write a `{ "candidates": [ ... ] }` file. Drop anything the avenue did not fetch. Then:

```bash
python3 scripts/workspace.py --workspace "$WS" present --file candidates.json
```

Render `rows` with the table in `job-finder`. Do not renumber. Cap the table at 12. If more than 12 survived, keep company diversity and keep up to 3 unconsidered rows before filling the rest with direct matches.

If an unconsidered row survived, the short description above the table has to mention it. If that avenue found nothing credible, say so in one sentence. Do not pad it.

`still_open` goes under the table, labeled as not new.

Record what you searched, including queries that returned nothing:

```bash
python3 scripts/workspace.py --workspace "$WS" record-search --file search.json
```

`search.json` needs `queries` (list of `{avenue, q}`) and `opened_urls`. The script keeps the latest 20 runs. On the next search, read the newest file in `.job-finder/searches/` and do not repeat those queries unless the user asks for a fresh pass.

## Filters the agents apply before returning

- Work mode not in `accepts`, when the listing states a mode: drop. Unknown mode: keep, and set `work_mode` to `unknown`
- Listed salary maximum below the user's minimum, same period and currency: drop. Overlap, unknown salary, or a different currency: keep, and say so in `why`
- Office or hybrid outside their cities, and they will not relocate: drop. Remote outside `remote_countries`, when that list exists: drop
- Posted date older than 60 days, and the page does not still show the role as open: drop. No date: keep, and do not call it fresh
- Needs sponsorship when their status is `needs_sponsorship` and the listing says it will not sponsor: drop. `prefer_not_to_say`: do not filter on sponsorship

`cover_letter_requested` is true only with `cover_letter_evidence`, a short quote from the page. Optional counts as true. A page with no letter, personal statement, or "why us" field is false.

## Gotchas

- Do not suggest a company and title you remember from training data. If you cannot open a URL fetched in this run, it is not a candidate.
- Do not hide a weak fit by writing a confident `why`. `interest` and `unconsidered` rows should sound less certain than `direct` rows, because they are.
- Deduplicate by listing URL, not by company. Two roles at one company can both be real. Eight roles at one company should not fill the table.
- `present` marks rows `suggested` and updates `jobs.json` immediately. Commit that from `job-finder` before you wait for an answer. Suggested rows stay out of the next new-results table and appear as still open. That is the intended memory.
