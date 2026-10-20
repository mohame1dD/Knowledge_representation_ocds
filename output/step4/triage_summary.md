# SHACL triage summary

Chunks validated: 32. Results: 5338. Violations: 0.

| Rule | Severity | Category | Decision | Count |
|---|---|---|---|---|
| 11 | Warning | small overrun (at most 10%) | accept: plausible price change | 2022 |
| 11 | Warning | overrun 10 to 50% | review | 849 |
| 11 | Warning | overrun over 50% | flag: red flag for investigation | 235 |
| 11 | Warning | placeholder estimate (under 1,000 PYG) | data error: estimate unusable | 34 |
| 9 | Warning | signed within a month before award | review: likely award date = publication date | 1225 |
| 9 | Warning | signed more than a month before award | flag: probable data error | 781 |
| 9 | Warning | same-day signing (dateSigned stored at 12:00) | accept: not a real exception | 192 |
