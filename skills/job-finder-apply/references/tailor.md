# Tailoring the CV

`cv/base.md` is the source of facts. The file you write is a variant for one listing. A reviewer should be able to point every employer, title, date, and number in the variant back at the base file.

## What you may change

- The summary, so it faces this listing. Two or three sentences. Only claims the base CV already makes.
- The order of skills. Drop a skill from the variant if it wastes the page. It stays in the base file.
- The order of bullets inside a role. Lead with the overlap.
- Wording of a bullet, when the new wording is the same fact in shorter words. "Led the ledger migration" stays "led the ledger migration" if that is what they wrote. Do not turn it into a metric they did not write.
- Which older bullets you include. Recent roles stay. A short early role can collapse to title, company, and dates.

## What you may not change

- Employers, titles, dates, locations, credentials
- Numbers: team size, latency, revenue, years
- Tools they did not list, unless `cv/base.md` shows the work in different words you can point at
- Interests promoted into employment

If the listing asks for something the CV does not show, leave it out of the CV. Mention the gap in `listing.md` under "Not claimed", so the user can see you noticed. Do not paper over it in the summary.

## listing.md

```markdown
# <title>, <company>

- URL: <url>
- Fetched: <iso time>
- Work mode: <mode>
- Location: <location>
- Salary: <text or unknown>
- Cover letter: <yes, with the evidence quote | no>

## Overlap
- <requirement from the page> — <where that fact is in cv/base.md>

## Not claimed
- <requirement the CV does not support>
```

If you cannot quote the requirement, you did not tailor against it. Fetch the page again or say the listing was too thin to tailor tightly, and keep the variant close to the base CV.

## Check before commit

Read the variant and the base file side by side. Every number in the variant must appear in the base file. Every company heading must appear there too. If you find a fact you cannot point at, delete it.
