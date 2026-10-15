# Extracting a CV

Read the source file once. Write two outputs: `cv/base.md`, and a profile patch.

## cv/base.md

This is the text later tailoring is allowed to rearrange. If a fact is not here, it cannot appear on an application CV.

Keep the person's order of jobs. Keep every metric as written. If the PDF extraction drops a character, look at the page again rather than filling the gap. A missing number stays missing.

Use a plain structure:

```markdown
# <name>

<email> · <phone> · <location>
<links>

## Summary
<their summary, or a few sentences that only restate roles already listed>

## Experience
### <title>, <company>
<start> – <end> · <location>
- <bullet as written>

## Education
### <credential>, <school>
<year>

## Skills
<as listed>
```

Do not add a "selected achievements" section they did not write. Do not upgrade a title.

## Profile patch

The profile is an index, not a second CV. Four highlights per role is enough. `summary` is two or three sentences an agent can search from.

`target_titles` are roles the CV can support without a new career story. `normal_flow_titles` is narrower: the query they would type on a board tonight. Current title, the obvious next title, maybe one adjacent title they have already held.

`skills` are tools and practices the CV shows they used, not a taxonomy you wish they had. A course, a hobby, or a sentence in this chat goes to `interests_beyond_cv` unless the CV shows the work.

`seniority` is a word from the CV (`junior`, `mid`, `senior`, `staff`, `principal`, `manager`, `director`) or null. Do not promote them because the bullets sound senior.

Dates you cannot read go in `uncertain`, and the field stays null. Same for a company name split across a column.

Leave out government identity numbers even when they are printed on the CV.

After writing both files, `set-source --analyzed` and `write-profile --mark-analyzed`. The hash, not your memory, decides whether the next run opens the file.
