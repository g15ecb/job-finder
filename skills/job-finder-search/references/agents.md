# Search avenue briefs

Give each subagent the profile JSON, the exclusion list, today's date, and one brief. Tell it to return a single JSON object and no markdown. If it cannot open a page, it omits that lead.

Shared return shape:

```json
{
  "avenue": "direct",
  "notes": "what you tried and what you refused to include",
  "candidates": [
    {
      "avenue": "direct",
      "company": "Northwind",
      "title": "Staff Software Engineer",
      "url": "https://boards.example/jobs/123",
      "location": "London, UK",
      "work_mode": "hybrid",
      "salary_text": "£140,000–£160,000",
      "salary_min": 140000,
      "salary_max": 160000,
      "salary_currency": "GBP",
      "salary_period": "year",
      "cover_letter_requested": true,
      "cover_letter_evidence": "Optional cover letter, 200 words",
      "posted_at": "2026-09-30",
      "why": "Ledger migration matches the staff role's payments scope.",
      "why_unconsidered": "",
      "credible_because": "Current title and domain match the listing.",
      "source_query": "staff software engineer payments London hybrid",
      "fetched_at": "2026-10-14T15:00:00Z"
    }
  ]
}
```

`work_mode` is `remote`, `hybrid`, `office`, or `unknown`. Salary numbers are null when the page does not state them. Do not estimate a salary into `salary_min`.

`why` is one sentence a person can scan in a table. No "exciting opportunity".

## direct

Search `normal_flow_titles`, then `target_titles` if the first pass is thin. Constrain by preferred work mode and home city or remote countries. Open the posting, not a aggregator card, when the posting URL is on the card.

You are done when you have a few listings you opened, or the obvious queries are exhausted. Do not wander into a career change. That is another agent's job.

## adjacent

Look one function over, and only where the CV already shows the work. Examples of a move, not a menu to apply in full: staff engineer to player-coach, backend to solutions or field engineering, research to applied engineering, IC to a lead role that still writes. Skip a move that needs a credential or a job they have not held.

`credible_because` has to name the CV fact, not the interest. If you cannot name one, drop the lead.

## interest

Use `interests_beyond_cv`. The honest `why` says the hook is an interest, not a job they have done. Do not search their current title again and sprinkle the interest word into `why`.

If interests are empty or `none`, return no candidates and say so in `notes`.

## unconsidered

This avenue exists because the other three reconstruct the search they already know how to run.

Do not return a more senior version of `normal_flow_titles` and call it unconsidered. A normal title is allowed only when the surprise is the employer or the shape of the work, and `why_unconsidered` says that in the first sentence.

Pick from moves the profile makes credible. Do not run the whole list:

- Employer type they do not already have: startup if their history is large companies, or the reverse; public sector; non-profit; devtools; a lab; a company outside their domain
- Shape of work: founding engineer, contract, advisory, teaching, developer relations, solutions, the first specialist hire. Only if seniority and salary still fit
- Domain shift that reuses a skill they have used, not a hobby you wish they had

Drop a lead that needs a license, a degree, or years in a function the profile does not show. Drop anything under the salary floor when the listing states a comparable maximum. A surprising job they cannot afford is not a kindness.

`why_unconsidered` is required. `credible_because` is required. If either sentence is vague, drop the lead.

Return two or three when they are real. Return zero rather than a padded one. Say which moves you considered and rejected.
