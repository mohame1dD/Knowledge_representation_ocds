# Paraguay's Public Procurement as a Knowledge Graph

**Knowledge Representation, team project**
Topic: public procurement · Data: Paraguay DNCP, Open Contracting Data Standard (OCDS), 2019 to 2022
Repository: https://github.com/mohame1dD/Knowledge_representation_ocds

---

## Summary

We turned four years of Paraguay's public procurement data into a knowledge graph and built a
pipeline around it in five steps:

1. **Data and profiling:** download the data, measure it, and find the business rules it obeys.
2. **R2RML mapping:** load the tables into a database and transform them into RDF with a declarative
   mapping, then resolve which records describe the same organisation.
3. **Ontology:** state what the words in the graph mean (OWL 2), and check it with a reasoner.
4. **Checking:** answer competency questions with SPARQL, validate the data with SHACL, block bad data
   with a gate, and record provenance.
5. **LLM access layer:** let people ask questions in plain English; a language model writes SPARQL,
   and every query is checked before it runs.

| Headline | Value |
|---|---|
| Procurement processes | **63,178** (2019 to 2022) |
| Triples in the graph | **2,061,368**, built by the R2RML mapping |
| Business rules found / carried through the project | **23 / 6** |
| SHACL violations | **0** in 32 chunks |
| SHACL warnings | **5,338**, matching the profiling counts exactly |
| Ontology | 22 classes, 10 object properties, 19 datatype properties (PPO 1.1.0) |

All numbers in this report come from files the pipeline writes; each section names its source file.

---

## 1. Goals and competency questions

The graph must be able to answer six **competency questions** (written into the ontology header).
Every class and property exists because one of them needs it.

| # | Competency question | Answered by |
|---|---|---|
| CQ1 | Which suppliers won contracts from a given buyer, and for how much? | `q1_top_buyers.rq`, `q2_suppliers_of_buyer.rq` |
| CQ2 | Which processes awarded more than their tender estimate, and by how much? | `q3_over_budget.rq`, rule 11 |
| CQ3 | Which contracts were signed before their award date? | `q4_signed_before_award.rq`, rule 9 |
| CQ4 | Which contracts are running, closed or cancelled? | `q5_contract_status.rq`, rule 6e |
| CQ5 | Which suppliers might be the same organisation under two identifiers? | `q6_same_name_two_ids.rq`, rule 16 |
| CQ6 | Which companies bid in a tender but did not win? | `q7_losing_bidders.rq` |

---

## 2. The data

### 2.1 Source and licence

* **Publisher:** DNCP (Dirección Nacional de Contrataciones Públicas), Paraguay's national procurement agency.
* **Format:** OCDS, the Open Contracting Data Standard, used by many governments to publish procurement
  in the same structure.
* **Access:** the OCP Data Registry, publication 63, as one CSV bundle per year.
* **Licence:** CC BY 4.0. Credited in `data/LICENCE.txt` and in `output/provenance.ttl`.
* **Scope:** 2019, 2020, 2021 and 2022; 9 of the 70+ tables in each bundle.

### 2.2 What a procurement process is

One **procurement process** is one public purchase. OCDS splits it into five stages, each in its own tables:

| Stage | What happens | Tables |
|---|---|---|
| Planning | the buyer plans the purchase and its budget | `main.csv` (planning columns) |
| Tender | the buyer calls for offers; companies bid | `main.csv`, `tender_tenderers.csv`, `tender_lots.csv`, `tender_items.csv` |
| Award | the decision: who wins, for how much | `awards.csv`, `awards_suppliers.csv` |
| Contract | the signed agreement | `contracts.csv` |
| Implementation | delivery and payments | `contracts_implementation_transactions.csv` |

`parties.csv` lists every organisation involved in a process (buyer, bidders, winner) with its roles.

### 2.3 The tables (source: `step1_profiling/grain.txt`)

| Table | Rows | Processes covered | Rows per process |
|---|---|---|---|
| main | 63,178 | 63,178 | 1.00 |
| parties | 365,926 | 63,178 | 5.79 |
| awards | 52,512 | 38,962 | 1.35 |
| awards_suppliers | 52,620 | 38,962 | 1.35 |
| contracts | 50,092 | 36,660 | 1.37 |
| tender_tenderers | 99,660 | 37,371 | 2.67 |
| tender_lots | 195,419 | 44,224 | 4.42 |
| tender_items | 918,312 | 44,225 | 20.76 |
| contracts_implementation_transactions | 321,617 | 20,641 | 15.58 |

Processes per yearly file: 2019: 14,093 · 2020: 10,270 · 2021: 9,276 · 2022: 29,539.

### 2.4 Identifiers

* **`ocid`** identifies a whole process, for example `ocds-03ad3f-294066-2`. It is globally unique: the
  prefix `03ad3f` identifies DNCP as the publisher. Every row of every table carries the ocid of its process
  in `main_ocid`.
* **`id`** identifies one award, contract or party **inside** a process, for example the contract
  `LP-22011-15-112699`. OCDS only promises that it is unique within its process: an award id such as `1`
  appears in many processes.

Consequence: every join in the project uses the pair `(ocid, id)`, and every IRI of an award or contract
contains its ocid.

* **Organisations** are identified by DNCP party ids built from a scheme and a number, mostly the RUC tax
  number (`PY-RUC-80071004-5`), sometimes a DNCP code (`DNCP-SICP-CODE-20`).

### 2.5 A property of the files that shapes the project

The registry splits the yearly files by each process's **last update**, not its tender date. The "2021" file
contains tenders published as early as 2010, because something about them changed in 2021. Consequences:

* per-year counts mean "processes last updated that year", and are a lower bound for any tender year;
* dates must come from the tender itself (`datePublished`, `tenderPeriodStart`), never from the file year.
  The ontology's `ppo:bundleYear` carries this warning in its definition.

---

## 3. Architecture

```
 data/raw/<year>/*.csv
        │  Step 1  fetch_data.py, profiling.py, rule_checks.py
        ▼
 grain.txt, profiles/*.html, constraint_inventory.csv
        │  Step 2  load_db.py ─► data/procurement.db (tables + cleaning views)
        │          run_mapping.py: mapping.r2rml.ttl, run by Morph-KGC
        ▼
 output/graph/chunks/*.ttl, shared.ttl, graph.ttl      ◄── entity_resolution.py ─► sameas.ttl
        │
        ├── Step 3  reason.py: ppo.ttl + a sample ─► reasoner_report.txt ; Protégé file
        ├── Step 4  validate.py: shapes.ttl ─► triage ; gate.py ; provenance.py ; run_queries.py
        └── Step 5  make_void.py ─► void.ttl ─► schema_card.md ; ask.py, evaluate.py, serve.py
```

| Step | Folder | Tools | Main outputs |
|---|---|---|---|
| 1 Data + profiling | `data/`, `step1_profiling/` | pandas, ydata-profiling | `grain.txt`, `profiles/*.html`, `constraint_inventory.csv` |
| 2 R2RML mapping | `step2_mapping/` | SQLite, R2RML, Morph-KGC | `data/procurement.db`, `output/graph/*.ttl`, `sameas.ttl` |
| 3 Ontology | `step3_ontology/` | OWL 2 DL, HermiT (owlready2), Protégé | `ppo.ttl`, `reasoner_report.txt`, `ppo_with_sample.ttl` |
| 4 Checking | `step4_checking/` | SPARQL, SHACL (pyshacl), PROV-O | `queries/*.csv`, `triage.csv`, `triage_summary.md`, `provenance.ttl` |
| 5 LLM | `step5_llm/` | VoID, Gemini or Claude, rdflib | `void.ttl`, `schema_card.md`, `evaluation.md` |

All RDF in the project is written in **Turtle**. Four Turtle files hold our decisions and are written by
hand: `ppo.ttl` (OWL), `mapping.r2rml.ttl` (R2RML), `shapes.ttl` (SHACL) and `examples.ttl` (worked
queries). Every other file is generated and can be rebuilt with `python run_all.py`.

---

## 4. Step 1: profiling and the constraint inventory

### 4.1 Profiling

`profiling.py` loads each of the 9 tables for all four years, stacked into one table with a `year` column,
and answers the first question of profiling: **what does one row stand for (the grain)?** It then writes one
ydata-profiling report per table (`step1_profiling/profiles/*.html`; tables above 50,000 rows are sampled).

### 4.2 The 23 rules

`rule_checks.py` tests 23 business rules, sentences the data seems to obey, and counts how many rows break
each one, overall and per year (`constraint_inventory.csv`).

| # | Rule | Broken / total |
|---|---|---|
| 1 | Every contract's awardID matches an award in the same process | 0 / 50,090 |
| 2 | Every award supplier is a party with the role supplier | 0 / 52,620 |
| 3 | Every buyer is a party with the role buyer | 0 / 63,170 |
| 3b | Every award has at least one supplier | 0 / 52,512 |
| 4 | numberOfTenderers equals the number of tenderer rows | 0 / 37,371 |
| 5 | Every award has a contract | 2,670 / 52,512 |
| 6a | A complete tender has at least one award | 3,016 / 41,823 |
| 6b | A cancelled tender has no award | 155 / 2,179 |
| 6c | Planning or unsuccessful tenders never have an award | 0 / 19,170 |
| 6d | An active contract never sits on a cancelled award | 10 / 28,469 |
| 6e | A contract with status "terminated" sits on an active award | 3 / 21,584 |
| 7 | Tender period starts before it ends | 0 / 44,763 |
| 8 | An award is dated on or after the tender period ends | 40 / 50,790 |
| 9 | A contract is signed on or after its award date | 2,198 / 50,076 |
| 10 | Contract period starts before it ends | 0 / 34,226 |
| 11 | Total awarded value is at most the tender value | 3,140 / 38,726 |
| 12 | Contract value equals its award value | 251 / 50,090 |
| 13 | Each process uses a single currency | 0 / 46,132 |
| 14 | Award and contract amounts are non-negative | 0 / 102,604 |
| 15 | One supplier identifier always carries one name | 0 / 11,743 |
| 16 | One normalised supplier name always carries one identifier | 22 / 11,718 |
| 17 | Direct contracting means at most one tenderer | 14,738 / 24,515 |
| 18 | Each procurement method label appears in one spelling | 8 / 28 |

Rule 17 is the clearest "label versus reality" finding: "Contratación Directa" (direct contracting) had two or
more bidders in 60% of cases, so the method's name says nothing about competition.

### 4.3 The six selected rules

| Rule | 2019 | 2020 | 2021 | 2022 | Total | Kind |
|---|---|---|---|---|---|---|
| 1 Contract points to an award of its own process | 0 | 0 | 0 | 0 | 0 / 50,090 | always holds |
| 3b Every award has a supplier | 0 | 0 | 0 | 0 | 0 / 52,512 | always holds |
| 9 Contract signed on or after its award | 372 | 516 | 295 | 1,015 | 2,198 / 50,076 | real exceptions |
| 11 Total awarded at most the estimate | 601 | 405 | 524 | 1,610 | 3,140 / 38,726 | real exceptions |
| 6e "Terminated" contracts sit on active awards | 0 | 2 | 1 | 0 | 3 / 21,584 | label vs meaning |
| 16 One supplier name, one identifier | 14 | 1 | 2 | 5 | 22 / 11,718 | identity trap |

Why these six:

* **1 and 3b** never broke in four years, so they can be stated as part of the meaning (OWL axioms) and
  enforced as hard checks (SHACL Violations).
* **9 and 11** break thousands of times. As axioms they would make the graph contradict itself, so they are
  SHACL Warnings, and their exceptions are triaged.
* **6e** is a problem of meaning, not of dirty data. Read as English, "terminated" sounds like "failed". In
  OCDS it means the contract ran and has closed: 21,581 of 21,584 terminated contracts sit on an active award.
  The fix is a definition in the ontology.
* **16** is an identity problem: the same name with two identifiers may be one company or two people. It is
  decided by entity resolution.

Rule of thumb used throughout: **what must hold by meaning is an axiom; what we must check in the data is a shape.**

---

## 5. Step 2: from the database to RDF with R2RML

### 5.1 The database and its cleaning views

`load_db.py` loads the six tables the graph needs into SQLite (`data/procurement.db`), standing in for DNCP's
own database. The cleaning is done by **SQL views**, so the mapping itself stays purely declarative:

| View | Reads | Cleaning |
|---|---|---|
| `v_tender` | main | tender status code → PPO class IRI |
| `v_award` | awards | award status code → PPO class IRI |
| `v_contract` | contracts | contract status code → class; **"terminated" → `ppo:ClosedContract`** (rule 6e) |
| `v_method` | main | method labels trimmed, one label per method (rule 18) |
| `v_org` | parties | one row per organisation (latest year, then highest name) |
| `v_org_ref` | main, tenderers, suppliers | every organisation a process refers to |
| `v_supplier`, `v_tenderer` | awards_suppliers, tender_tenderers | who won, who bid |

Example row of `v_contract`:

```
ocid          ocds-03ad3f-294066-2
id            LP-22011-15-112699
status        active
status_class  https://ul.edu.lb/kr/ont/ppo#ActiveContract
amount        5623007594
```

### 5.2 IRI scheme

Every IRI is built from DNCP's own identifiers, under `https://ul.edu.lb/kr/id/py/`:

| Thing | IRI template |
|---|---|
| process | `process/{ocid}` |
| tender | `tender/{ocid}` |
| award | `award/{ocid}/{award id}` |
| contract | `contract/{ocid}/{contract id}` |
| organisation | `org/{party id}` (for example `org/PY-RUC-80071004-5`) |
| method | `method/{slug of the label}` |

Because names come from the source's identifiers, a rebuild produces the same IRIs, and an organisation keeps
one IRI across every process it takes part in.

### 5.3 The mapping

`mapping.r2rml.ttl` (W3C R2RML) contains 12 triples maps: Process, Tender, Method, Tenderer, Award,
ProcessAward, TenderAward, Supplier, Contract, ProcessContract, Organization and OrganizationRef. Each one
states which view to read, how to name each row's thing, what class it is, and which column becomes which
property:

```turtle
map:Contract a rr:TriplesMap ;
  rr:logicalTable [ rr:sqlQuery "SELECT * FROM v_contract" ] ;
  rr:subjectMap [ rr:template "https://ul.edu.lb/kr/id/py/contract/{ocid}/{id}" ;
                  rr:class ppo:Contract ] ;
  rr:predicateObjectMap [ rr:predicate ppo:amount ;
                          rr:objectMap [ rr:column "amount" ; rr:datatype xsd:decimal ] ] .
```

**Morph-KGC** executes the mapping against the database. `run_mapping.py` then writes the triples as Turtle,
with prefixes and with all facts about one subject grouped together. The example row above becomes:

```turtle
<https://ul.edu.lb/kr/id/py/contract/ocds-03ad3f-294066-2/LP-22011-15-112699>
    a ppo:ActiveContract, ppo:Contract ;
    ppo:amount "5623007594"^^xsd:decimal ;
    ppo:basedOnAward <https://ul.edu.lb/kr/id/py/award/ocds-03ad3f-294066-2/294066-las-cuevas-s-a-1> ;
    ppo:dateSigned "2015-09-29T12:00:00-04:00"^^xsd:dateTime ;
    ppo:statusCode "active" .
```

Output (`output/graph/`):

| File | Content |
|---|---|
| `chunks/part-0001.ttl` … `part-0032.ttl` | 2,000 whole processes each; every organisation a chunk refers to is typed in it, so each file can be validated on its own |
| `shared.ttl` | organisations (name, identifier, scheme, country) and procurement methods, described once |
| `graph.ttl` | all chunks and `shared.ttl` together: **2,061,368 triples** |

**Materialise or virtualise.** We materialise the graph rather than query the database through a virtual
layer such as Ontop: DNCP publishes periodic file exports rather than a live database, and the reasoner, SHACL
and the LLM layer all need real triples.

### 5.4 Entity resolution

`entity_resolution.py` decides which organisation records are the same organisation (rule 16, source
`output/step2/er_report.txt`). Profiling showed a larger problem behind rule 16: of **34,074** named
organisations, **19,466** are "notified suppliers" that carry a random, per-process id and no tax number, so the
same company appears under a new id in every process.

| Case | Example | Decision | Count |
|---|---|---|---|
| Same RUC except the check digit, same name | `3564077` and `3564077-4`, MARTIN DANIEL URBIETA SKAF | `owl:sameAs` | 1 |
| Same number, different names | `80044691` CONSORCIO NUTRISA and `80044691-7` BELTROM SA | rejected | 1 |
| Same name, different numbers | MIGUEL ACOSTA BENITEZ, two unrelated RUCs | never merged; flagged | 235 |
| Notified supplier, name matches exactly one identified organisation | | `ppo:candidateSameAs` | 5,864 (30%) |
| Notified supplier, name matches several | | left ambiguous | 8 |

The policy: never merge on a name alone. `owl:sameAs` merges two individuals and copies every fact across, so a
wrong merge would give one company another's contracts. When the only evidence is a name, we use our weaker
`ppo:candidateSameAs`, which links the records without merging them. The links are written to
`output/graph/sameas.ttl`.

---

## 6. Step 3: the ontology (PPO 1.1.0)

`step3_ontology/ppo.ttl` is the Paraguay Procurement Ontology, written in OWL 2 DL, in Turtle.

### 6.1 Classes and properties

| Group | Classes |
|---|---|
| Core (6) | ProcurementProcess, Tender, Award, Contract, Organization, ProcurementMethod |
| Roles, defined (3) | Buyer, Supplier, Tenderer |
| Tender statuses (5) | PlanningTender, ActiveTender, CompleteTender, UnsuccessfulTender, CancelledTender |
| Award statuses (4) | ActiveAward, CancelledAward, PendingAward, UnsuccessfulAward |
| Contract statuses (4) | ActiveContract, ClosedContract, CancelledContract, PendingContract |

Object properties (10): `hasTender`, `hasBuyer`, `hasAward`, `hasContract`, `resultsInAward`, `awardedTo`,
`basedOnAward`, `hasTenderer`, `usesMethod`, `candidateSameAs`. Datatype properties (19) hold values: amounts,
currency, dates, status codes, titles, identifiers.

```
ProcurementProcess ──hasTender──► Tender ──hasTenderer──► Organization
        │  └──hasBuyer──────────────────────────────────► Organization
        ├──hasAward──► Award ◄──resultsInAward── Tender
        │                │
        │                └──awardedTo──────────────────► Organization
        └──hasContract──► Contract ──basedOnAward──► Award
                          Tender ──usesMethod──► ProcurementMethod
```

### 6.2 Axioms

| Axiom | OWL construct | From |
|---|---|---|
| A Contract has exactly one `basedOnAward` that is an Award | qualified cardinality | rule 1 |
| Every Award is `awardedTo` some Organization | existential restriction | rule 3b |
| A PlanningTender or UnsuccessfulTender has no `resultsInAward` Award | complement of an existential | rule 6c |
| Tender, Award, Contract, Organization, … are pairwise disjoint; so are the statuses | `AllDisjointClasses` | model |
| Supplier ≡ Organization that some Award is `awardedTo` (Buyer, Tenderer likewise) | equivalent class with inverse property | rules 2, 3 |
| ClosedContract ≡ Contract with `statusCode` "terminated" (and each status likewise) | equivalent class with `hasValue` | rule 6e |

ClosedContract's definition states that the contract was signed, ran and came to a close, whether it finished
normally or early. There is deliberately no "FailedContract" class: the data cannot tell the two apart.

Rules 6a and 6b are deliberately **not** axioms: with 3,016 and 155 exceptions they would make the real data
inconsistent.

### 6.3 Reuse

We align to two existing ontologies with `rdfs:subClassOf` and `rdfs:subPropertyOf`, without importing them:

* **TBFY OCDS ontology** (TheyBuyForYou project): mirrors OCDS exactly; no longer maintained.
* **ePO 5.2.0** (EU eProcurement Ontology, Publications Office, October 2025): maintained, but built around EU
  notices; its core alone has 150 classes, while our competency questions need about 20.

| PPO | TBFY | ePO |
|---|---|---|
| ProcurementProcess | ContractingProcess | Procedure |
| Tender | Tender | **not aligned** |
| Award | Award | AwardOutcome |
| Contract | Contract | Contract |
| Organization | Organisation | (W3C `org:Organization`) |

`ppo:Tender` is deliberately not aligned to `epo:Tender`: in ePO a Tender is a company's **offer**, in OCDS the
tender is the buyer's **call for offers**. `reason.py` checks that all 14 aligned external terms exist in the
copies kept in `step3_ontology/external/`.

**Profile:** OWL 2 DL. The qualified cardinality (exactly one award) and the negated existentials (a planning
tender has no award) cannot be expressed in OWL 2 EL.

### 6.4 Reasoning (source: `output/step3/reasoner_report.txt`)

`reason.py` runs the HermiT reasoner (through owlready2, on Java) four times:

1. **Ontology alone:** consistent, no unsatisfiable classes.
2. **Ontology + 300 real processes** (8,424 triples, stored status classes removed first, 46 seconds):
   consistent. HermiT inferred, from the definitions alone, 139 Buyers, 188 Suppliers, 266 Tenderers,
   216 ActiveContracts, 214 CompleteTenders, 70 PlanningTenders and 9 UnsuccessfulTenders. None of these types
   are stored in the data.
3. **Planted mistake, an unsuccessful tender with an award:** the ontology becomes **inconsistent**, as the
   rule 6c axiom intends.
4. **Planted mistake, a contract with two different awards:** **no error**. Because `basedOnAward` is
   functional, OWL concludes the two awards are the same individual. Only after stating that they are different
   does it become inconsistent. This is OWL's open world and missing unique name assumption, and it is why rule 1
   is also a SHACL shape.

The reasoner checks the model on a sample; SHACL checks all the data. A DL reasoner over two million triples is
impractical on a laptop: 300 processes take under a minute, while 1,500 did not finish in seven minutes.

During development the reasoner also exposed an error in the ontology itself: `xsd:gYear` is a valid RDF datatype
but is not in the OWL 2 datatype map. `ppo:bundleYear` now uses `xsd:integer` (see `CHANGELOG.md`).

`tools/make_protege_file.py` writes `output/protege/ppo_with_sample.ttl`: the ontology plus 25 whole processes, to
open in Protégé and reason on by hand. After starting HermiT, inferred types such as Supplier appear in yellow.

---

## 7. Step 4: checking with SPARQL and SHACL

### 7.1 SPARQL competency queries (source: `output/step4/queries/`)

| Query | Finding |
|---|---|
| q1 top buyers | Ministerio de Obras Públicas y Comunicaciones (MOPC): 733 contracts, 9.83 trillion PYG; then PETROPAR (6.40 trillion) and the Ministry of Health (4.13 trillion, 3,021 contracts) |
| q2 suppliers of the top buyer | the largest buyer's suppliers and amounts |
| q3 over budget | the largest overruns, including placeholder estimates of 1 or 2 PYG |
| q4 signed before award | contracts dated before their award |
| q5 contract status | 28,469 active, 21,584 closed ("terminated"), 37 cancelled |
| q6 same name, two ids | candidates for entity resolution |
| q7 losing bidders | EMPORIO FERRETERIA S.R.L. bid without winning 579 times; OFFICE COMPU SA 334; JUAN RODRIGUEZ 306 |
| q8 methods | processes and average bidders per procurement method |

### 7.2 SHACL shapes (`step4_checking/shapes.ttl`)

| Shape | Target | Check | Rule | Severity |
|---|---|---|---|---|
| ContractShape | Contract | exactly one `basedOnAward`, and it is an Award | 1 | Violation |
| ContractShape | Contract | that award belongs to the contract's own process (SPARQL) | 1 | Violation |
| ContractShape | Contract | exactly one status class (`sh:xone`) | 6e | Violation |
| ClosedContractShape | ClosedContract | carries the code "terminated" | 6e | Violation |
| AwardShape | Award | at least one `awardedTo`, an Organization | 3b | Violation |
| ProcessShape | ProcurementProcess | exactly one tender | model | Violation |
| Rule9Shape | Contract | signed on or after the award date (SPARQL) | 9 | Warning |
| Rule11Shape | ProcurementProcess | sum of award amounts at most the estimate (SPARQL with SUM) | 11 | Warning |

Rules 9 and 11 compare dates and add up amounts, which OWL cannot do, so they are SPARQL-based constraints. In
SHACL the severity is a property of the shape, so each warning rule has its own shape.

`validate.py` checks the 32 chunks one by one. Every selected rule only looks inside one process, and each chunk
holds whole processes with every organisation they refer to, so this gives the same results as validating the
whole graph at once, with a fraction of the memory.

### 7.3 Results and triage (source: `output/step4/triage_summary.md`)

**0 violations. 5,338 warnings: 2,198 for rule 9 and 3,140 for rule 11, exactly the counts of Step 1.** Two
independent checks, one on the CSV tables and one on the graph, agree.

Each warning is sorted into a category with a decision (`triage.csv`):

| Rule | Category | Decision | Count |
|---|---|---|---|
| 9 | signed the same day (DNCP stores the signing date at 12:00) | accept: not a real exception | 192 |
| 9 | signed within a month before the award | review: the award date may be its publication date | 1,225 |
| 9 | signed more than a month before the award | flag: probable data error | 781 |
| 11 | overrun of at most 10% | accept: plausible price change | 2,022 |
| 11 | overrun of 10 to 50% | review | 849 |
| 11 | overrun over 50% | flag: red flag for investigation | 235 |
| 11 | estimate under 1,000 PYG | data error: the estimate is a placeholder | 34 |

### 7.4 The gate and provenance

* **The gate** (`tools/gate.py`) fails on any Violation not listed, with a reason, in
  `step4_checking/known_issues.csv`, and prints every accepted one. It runs in `run_all.py` before the graph is
  published to a SPARQL endpoint, in the git pre-commit hook (`hooks/pre-commit`) and on GitHub
  (`.github/workflows/gate.yml`). `tools/gate_demo.py` removes one `basedOnAward` and one `awardedTo` from a chunk;
  the gate reports rules 1 and 3b and exits with an error.
* **Provenance** (`output/provenance.ttl`, W3C PROV-O) records the source dataset and licence, every input CSV with
  its SHA-256 checksum and line count, the mapping used, the build time and git commit, and the ontology version
  IRI the graph conforms to (`https://ul.edu.lb/kr/ont/ppo/1.1.0`).

---

## 8. Step 5: the LLM access layer

The goal: answer questions in plain English without trusting the language model blindly. The design follows the
Session 7 lab.

### 8.1 Grounding the model in what is really there

* `make_void.py` describes the graph as **VoID** (`output/step5/void.ttl`, 550 triples describing 2,061,368): every
  class with its number of instances, and every property with the class it goes from and the class or datatype it
  goes to, in the layout of SIB's void-generator.
* `schema_card.py` turns the VoID into one plain line per class and per property, plus a few rules a count cannot
  express (status classes are subclasses; "terminated" means closed; names are `rdfs:label`):

```
ppo:ProcurementProcess (63,178 things)
ppo:Award (52,512 things)
ppo:Contract (50,090 things)
ppo:ClosedContract (21,584 things)  (a kind of ppo:Contract)
ppo:Award ppo:awardedTo ppo:Organization
ppo:Contract ppo:basedOnAward ppo:Award
```

We describe the graph with VoID rather than the ontology because the ontology says what **could** be true, while
VoID says what **is** there. `ppo:Supplier` is a class of the ontology but has no stored instances (it is inferred),
so it does not appear in the schema, and a query using it would return nothing.

* `examples.ttl` holds 7 worked question and query pairs, stored as `sh:SPARQLExecutable` (the vocabulary SIB uses
  to publish examples). For each question, the 3 that share the most words with it go into the prompt.

### 8.2 Checking every query (`ask.py`)

1. **Generate:** the model receives the schema, the 3 examples and the question, and returns one SPARQL query or
   `REFUSE: reason`.
2. **Check:** the query must parse, be read-only (SELECT or ASK), and use only `ppo:` classes and properties that
   occur in `void.ttl`; a `LIMIT` is added to long lists.
3. **Run** on the graph (local file or SPARQL endpoint).
4. **Repair:** any failure goes back to the model with the error, listing the real classes or properties, up to two
   times.
5. **Refuse** when the model refuses, or when the repairs fail.

Calls to the model retry on timeouts, rate limits and temporary server errors, with increasing pauses.
`serve.py` exposes the same pipeline over HTTP with the TEXT2SPARQL contract:
`GET /?question=…&dataset=…` returns JSON with the dataset, the question and the query, plus the status and the
first rows of the answer.

### 8.3 Evaluation (`evaluate.py`, `output/step5/evaluation.md`)

The test set (`tests.jsonl`) has 15 questions: 11 answerable, each with a gold query, and 4 that must be refused
(bribery, a prediction about the future, a request to delete data, and a phone number). A question is correct when
the result rows match the gold query's rows, or when the system refuses an unanswerable question.

**Replay mode** (a hand-written stand-in for the model, with three deliberately wrong first attempts and one DELETE):
**11/11 answered, 3 repairs, 4/4 refused.** This measures the checks and the repair loop, not a model: the unknown
property, the class with no instances and the syntax error were each caught and repaired, and the DELETE was blocked.

**Gemini:** in our run, Gemini answered 6 of the questions before the free tier's quota stopped further requests;
5 of the 6 were correct, including the meaning trap "How many contracts were terminated?", which it correctly
answered by counting `ppo:ClosedContract`. The one wrong answer ("Which 5 suppliers won the most awards?") was a valid
query whose result differs from the gold query: an error of meaning that no syntactic check can catch. Questions
the quota prevented are failures of access, not of the model: `evaluation.md` marks them "the model did not answer",
and they should not be read as wrong answers. The full score is obtained by rerunning `evaluate.py` once the quota
resets.

---

## 9. Rule traceability

| Rule | Step 1: broken / total | Step 2 | Step 3 | Step 4 result |
|---|---|---|---|---|
| 1 | 0 / 50,090 | IRIs include the ocid | Contract has exactly 1 Award | 0 violations |
| 3b | 0 / 52,512 | | Award awardedTo some Organization | 0 violations |
| 9 | 2,198 / 50,076 | | (OWL cannot compare dates) | 2,198 warnings, triaged |
| 11 | 3,140 / 38,726 | | (OWL cannot sum) | 3,140 warnings, triaged |
| 6e | 3 / 21,584 | view: "terminated" → ClosedContract | ClosedContract defined by its code | 0 violations; LLM reads it as closed |
| 16 | 22 / 11,718 | entity resolution: 1 merged, 235 flagged, 5,864 weak links | `candidateSameAs` | |

---

## 10. Discussion

### 10.1 Design decisions

| Decision | Alternative | Why |
|---|---|---|
| Declarative R2RML mapping | a hand-written converter | readable, standard, runs on any R2RML engine; moving to PostgreSQL changes one line of `mapping.ini` |
| Cleaning in SQL views | cleaning inside the mapping | keeps the mapping a plain column-to-property description |
| Materialised graph | virtual graph (Ontop) | the source is a file export; the reasoner, SHACL and the LLM layer need triples |
| Align to TBFY and ePO | import them | ePO core alone is 150 classes; aligning keeps the ontology small but connected |
| Axiom only for rules without exceptions | axioms for every rule | one exception would make the whole graph inconsistent |
| `candidateSameAs` for name-only matches | `owl:sameAs` everywhere | a wrong `sameAs` copies facts between companies |
| VoID for the LLM schema | the ontology | the model needs what exists, with counts, not what could exist |
| Validation by chunk | the whole graph at once | same result for process-local rules, far less memory |

### 10.2 Limitations

* **The reasoner runs on a sample.** HermiT confirms the model is right; SHACL is what checks all the data.
* **Entity resolution has no gold standard.** Its decisions are policies; the only check is consistency with
  same-process evidence. A small hand-labelled sample would allow measuring precision.
* **Per-year counts depend on the registry's split by last update.**
* **The LLM evaluation is limited by the free tier's quota**, and replay mode only tests the pipeline.

### 10.3 Open problem: time

The graph stores each contract's latest status, not when it changed. A question such as "How many contracts were
active on 1 June 2021?" cannot be answered, and because the files are split by last update, a later download can
silently move a process to another year. Modelling status changes as dated events, rather than classes, would make
both visible.

---

## 11. Reproducing the results

Requirements: Python 3.11 or newer, Java 11 or newer (for HermiT).

```bash
./setup.sh                    # Windows PowerShell: .\setup.ps1   (creates .venv, installs requirements)
source .venv/bin/activate     # Windows: .venv\Scripts\activate.bat
python run_all.py             # all five steps, in order; --from N restarts at step N
```

Settings live in `.env` (copied from `.env.example`): `YEARS`, `SHACL_BATCH`, `REASONER_SAMPLE`, `FUSEKI_URL`,
`LLM_MODE` (`replay`, `gemini` or `anthropic`), the model key and `LLM_DELAY`. Each script can also be run on its
own; the order is listed in `README.md`.

### Where each result comes from

| Result | File |
|---|---|
| Tables and grain | `step1_profiling/grain.txt` |
| The 23 rules | `step1_profiling/constraint_inventory.csv` |
| The graph | `output/graph/graph.ttl` (+ `chunks/`, `shared.ttl`, `sameas.ttl`) |
| Entity resolution | `output/step2/er_report.txt`, `er_candidates.csv` |
| Reasoning | `output/step3/reasoner_report.txt` |
| Query results | `output/step4/queries/*.csv` |
| SHACL | `output/step4/triage_summary.md`, `triage.csv`, `validation_results.csv` |
| Provenance | `output/provenance.ttl` |
| VoID and schema | `output/step5/void.ttl`, `output/step5/schema_card.md` |
| LLM evaluation | `output/step5/evaluation.md` |

Data: Paraguay DNCP via the OCP Data Registry (publication 63), CC BY 4.0.
