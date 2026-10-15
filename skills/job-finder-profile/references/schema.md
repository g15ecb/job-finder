# Profile JSON

`write-profile` deep-merges this into `.job-finder/profile.json`. Lists replace. A present `interests_beyond_cv` marks interests answered unless the file also sets `interests_answered` to false.

Omit fields you are not changing. Do not send an empty object for a preference you have not asked about; that can wipe a saved answer on a later replace. A merge of `{}` does not delete nested keys. Use `clear-answer` for that.

```json
{
  "identity": {
    "name": "Ada Okonkwo",
    "email": "ada@example.com",
    "phone": "",
    "location": "London, UK",
    "links": ["https://example.com"]
  },
  "headline": "Staff engineer, payments ledgers",
  "summary": "Eight years on billing and ledger systems. Two employers.",
  "years_experience": 8,
  "current_title": "Staff Software Engineer",
  "seniority": "staff",
  "target_titles": ["Staff Software Engineer", "Senior Software Engineer"],
  "normal_flow_titles": ["Staff Software Engineer", "Senior Backend Engineer"],
  "skills": ["Go", "PostgreSQL", "payments"],
  "domains": ["payments", "billing"],
  "education": [
    {"school": "Example University", "credential": "BSc Computer Science", "year": "2016"}
  ],
  "experience": [
    {
      "company": "Northwind",
      "title": "Staff Software Engineer",
      "start": "2021",
      "end": "present",
      "highlights": ["Ledger migration named in the CV, not paraphrased into a new metric"]
    }
  ],
  "interests_beyond_cv": ["compiler tooling"],
  "preferences": {
    "salary": {
      "currency": "GBP",
      "minimum": 120000,
      "target": 145000,
      "period": "year",
      "notes": "",
      "unspecified": false
    },
    "work_mode": {
      "accepts": ["remote", "hybrid"],
      "preferred": "remote",
      "office_days_max": 2,
      "notes": ""
    },
    "location": {
      "home": "London, UK",
      "timezone": "Europe/London",
      "willing_to_relocate": false,
      "cities": ["London"],
      "countries": ["United Kingdom"],
      "remote_countries": ["United Kingdom"]
    },
    "work_authorization": {
      "status": "prefer_not_to_say",
      "notes": ""
    },
    "other": {}
  },
  "uncertain": [],
  "analysis_notes": []
}
```

`work_authorization.status` is one of `citizen`, `permanent_resident`, `visa`, `needs_sponsorship`, `prefer_not_to_say`.

`work_mode.accepts` uses `office`, `hybrid`, `remote`.

Salary `period` is `year`, `day`, or `hour`. Numbers are major units, not cents. Do not convert currency in the file. If you compare a listing in another currency later, say the rate you assumed and do not drop the job on a rough conversion.

`normal_flow_titles` is the list the unconsidered agent must leave. If the only surprise is the employer, the agent can still return a normal title, but it has to say the surprise is the employer.
