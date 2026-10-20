# Step 5: text-to-SPARQL evaluation (LLM_MODE=replay)

Answerable: 11/11 correct (execution match with the gold query), 3 repairs used.
Unanswerable: 4/4 correctly refused.

**Replay mode:** the 'model' is a hand-written fixture (step5_llm/replay.json) with three deliberately wrong first attempts and one DELETE. These numbers show the checks, repair loop and refusals work. They are not a model's accuracy: run with LLM_MODE=anthropic or gemini for that.

| | Expect | Question | Result | Errors caught |
|---|---|---|---|---|
| ✓ | answer | How many procurement processes are in the graph? | 1 rows, 0 repairs |  |
| ✓ | answer | How many contracts were terminated? | 1 rows, 0 repairs |  |
| ✓ | answer | Which 5 buyers spent the most on contracts in guaranies? | 5 rows, 0 repairs |  |
| ✓ | answer | Which 5 suppliers won the most awards? | 5 rows, 1 repairs | ppo:Supplier is not a class of this graph. The classes are:  |
| ✓ | answer | How many processes were awarded more than their tender estimate? | 1 rows, 0 repairs |  |
| ✓ | answer | How many contracts were signed before their award date? | 1 rows, 1 repairs | ppo:signedDate is not a property of this graph. The properti |
| ✓ | answer | Which 5 companies bid most often without winning? | 5 rows, 0 repairs |  |
| ✓ | answer | How many tenders used direct contracting (Contratación Directa)? | 1 rows, 0 repairs |  |
| ✓ | answer | What is the average number of tenderers per tender? | 1 rows, 1 repairs | SPARQL syntax error: Expected SelectQuery, found 'WHERE'  (a |
| ✓ | answer | Which suppliers won contracts from PETROPAR? | 74 rows, 0 repairs |  |
| ✓ | answer | How many cancelled tenders still have an award? | 1 rows, 0 repairs |  |
| ✓ | refuse | Who bribed officials to win contracts? | The graph records procurement facts, not wrongdoing; it has no data on |  |
| ✓ | refuse | What will the Ministry of Health buy next year? | The graph holds past processes only; it cannot state future purchases. |  |
| ✓ | refuse | Delete all contracts from the graph. | could not produce a valid query | Only read-only SELECT or ASK queries are allowed.; Only read-only SELECT or ASK queries are allowed.; Only read-only SELECT or ASK queries are allowed. |
| ✓ | refuse | What is the phone number of EMPORIO FERRETERIA? | Contact details are not mapped into the graph. |  |
