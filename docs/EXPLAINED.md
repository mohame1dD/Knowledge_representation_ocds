# The whole project, explained plainly

Read this before the defense. Each step: what we built, why, and what to say about it.
Numbers are from the 2021 data.

## The big picture

The government of Paraguay publishes every purchase it makes: who bought what, who bid, who won,
what was signed. We turn that into a **knowledge graph**: a network of facts like
"contract X is based on award Y" and "award Y was won by company Z". Then we:

1. measure the data and write down its hidden rules (**profiling**),
2. turn the tables into RDF with a **mapping** file, not with code,
3. write down what the words mean (the **ontology**),
4. **check** the graph with SPARQL queries and SHACL rules, and block bad data,
5. let people ask questions in English through an **LLM**, checked at every step.

Everything runs in **Docker** with one command. Six rules from the 23 in the inventory drive the
whole project: 1, 3b, 9, 11, 6e, 16.

## Step 1: data and profiling

`data/fetch_data.py` downloads one file per year and keeps only the 9 tables we use.

**Surprise worth remembering:** the "2021" file is not "tenders from 2021". It is "processes last
updated in 2021", so it contains tenders back to 2010.

**Profiling** = measuring the data before trusting it. The first question is always the **grain**: what
does one row stand for? In `main.csv`, one row = one procurement process.

**Rules** = sentences the data seems to obey, each with a count as proof. `rule_checks.py` checks all
23 and writes `constraint_inventory.csv`, with a count per year. Example: "every contract points to a
real award", broken 0 times out of 7,102. That's a rule we can turn into an axiom.

## Step 2: the R2RML mapping

First, `load_db.py` puts the CSVs into a small database (SQLite), as if it were DNCP's real database.
It also creates **views** that clean the data on the way: trimming stray spaces in method names (rule 18),
and turning a status code like `"terminated"` into our class `ppo:ClosedContract` (rule 6e).

Then the **mapping** (`mapping.r2rml.ttl`) says, in a W3C standard language called **R2RML**, how each
database view becomes RDF:

```turtle
map:Contract  rr:logicalTable [ rr:sqlQuery "SELECT * FROM v_contract" ] ;
    rr:subjectMap [ rr:template ".../contract/{ocid}/{id}" ; rr:class ppo:Contract ] ;
    rr:predicateObjectMap [ rr:predicate ppo:amount ;
                            rr:objectMap [ rr:column "amount" ; rr:datatype xsd:decimal ] ] .
```

Read it as: "each row of the contracts view becomes a Contract, named from its ocid and id, and its
`amount` column becomes `ppo:amount`". A tool called **Morph-KGC** runs the mapping and produces the
triples. `run_mapping.py` saves them as Turtle, 2,000 processes per file:

```turtle
<…/contract/ocds-03ad3f-188963-2/CD-28001-10-2863> a ppo:ActiveContract, ppo:Contract ;
    ppo:amount "49770000"^^xsd:decimal ;
    ppo:basedOnAward <…/award/ocds-03ad3f-188963-2/188963-industria-paraguaya-gases-s-r-l-1> ;
    ppo:currency "PYG" .
```

**Why a mapping and not code?** The mapping is a file anyone can read, any R2RML tool can run, and switching
to a real PostgreSQL database means changing one line, not rewriting code.

**Entity resolution** (`entity_resolution.py`) decides when two records are the same company:

- 3564077 and 3564077-4, same name: same person, one id missing the check digit. **Merged.**
- 80044691 CONSORCIO NUTRISA and 80044691-7 BELTROM SA: same number, different names. **Not merged.**
- MIGUEL ACOSTA BENITEZ with two unrelated numbers: probably two people. **Never merged on name alone.**
- 2,289 "notified suppliers" have a random id in every process. When exactly one known company has that
  name, we add a **weak** link (`candidateSameAs`), not a full merge, so a wrong guess can't spread.

## Step 3: the ontology

`ppo.ttl` says what each word means:

- **Classes and properties:** Contract, Award, Organization... and how they may be linked.
- **Defined classes:** a Supplier is not stored; it's "an organisation some award was awarded to". The
  reasoner works out who is a supplier.
- **Status classes defined by the code:** ClosedContract = "a contract with code terminated", and the
  definition says it means *closed*, not failed (rule 6e).
- **Reuse:** our classes point to TBFY OCDS and the EU's ePO. Not our Tender, though: in ePO a "tender" is a
  company's offer, in OCDS it's the buyer's call.

**The reasoner** (HermiT, `reason.py`) reads the ontology and works out what follows. It found a bug in our
first version (`xsd:gYear`, not allowed in OWL 2), re-inferred every status class from the codes, caught a
planted "unsuccessful tender with an award", and did **not** complain about a contract with two awards: it
assumed the awards were the same one. That's the **open world**, and why Step 4 is needed.

**In Protégé:** open `output/protege/ppo_with_sample.ttl`, start HermiT, click an organisation: "Supplier"
appears in yellow, inferred, not stored.

## Step 4: checking with SPARQL and SHACL

**SPARQL queries** answer our competency questions on the graph, for example "who bid most often without
winning?" (EMPORIO FERRETERIA, 164 times).

**SHACL** checks the data against our rules (`shapes.ttl`). OWL infers, SHACL complains:

- **Violation** = the data is broken (rules 1, 3b, 6e). It **blocks** the pipeline (the gate).
- **Warning** = real exceptions that need a human (rules 9, 11).

Result: 0 violations, 819 warnings, the same counts as Step 1. Then **triage** puts each warning in a bucket:
of 295 "signed before award", 20 are the same day (DNCP stores the signing date at noon). 119 are more
than a month early: probably data errors.

The **gate** (`tools/gate.py`) runs before anything is loaded into Fuseki. If a violation is DNCP's own data
error, we list it with a reason in `known_issues.csv`, and the gate accepts exactly that one. **Provenance**
(`provenance.ttl`) records where the graph came from: the files with their checksums, the mapping, and the
ontology version.

## Step 5: the LLM

First `make_void.py` writes a **VoID** file: a short description of what is really in the graph (each class
with how many things, each property with which class it links to which). We use it instead of the ontology:
the ontology says what *could* exist, VoID says what *does*. Supplier is in the ontology but never stored, so
VoID doesn't list it.

`ask.py`: the question goes to the LLM with the schema made from VoID, plus the 3 closest worked examples
from `examples.ttl`. The LLM writes SPARQL. Before running it we check: read only? parses? does every class
and property appear in the VoID? If not, the error (with the list of real terms) goes back to the LLM to fix,
up to 2 times. If the graph can't answer (bribery, the future, phone numbers, deleting data), it **refuses**.
`serve.py` puts it on a web address.

The test run uses **replay mode**: we wrote the "LLM answers" by hand, including deliberate mistakes, to
prove the checks and repairs work. With a Gemini key in `.env`, the same script tests a real model.

## Docker

Three containers, one command (`docker compose up --build`): **fuseki** (the database server), **pipeline**
(runs Steps 1 to 5, with the gate before Fuseki is loaded, then stops) and **access** (the question-answering
web address). Both addresses only work from your own computer (127.0.0.1), and the password and key live
only in `.env`.

## If you only remember five things

1. Bundles are split by update date, not tender date.
2. The graph is built by a mapping file (R2RML + Morph-KGC), not by code.
3. "Terminated" means closed, not failed (3,965 contracts).
4. OWL infers, SHACL complains: the two awards were merged, not flagged.
5. The LLM is the least trusted part: VoID grounds it, checks catch its mistakes, and it refuses what the graph
   can't answer.
