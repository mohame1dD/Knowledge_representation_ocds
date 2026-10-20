"""Step 2c: entity resolution for organisations (rule 16 and what it led to).

    python step2_mapping/entity_resolution.py

Three kinds of candidate pairs, three decisions:

  C1 Same RUC number except the check digit (3564077 vs 3564077-4)
     -> owl:sameAs ONLY if the names also agree (similarity >= 0.85).
        Same number with a different name (CONSORCIO NUTRISA vs BELTROM SA) is rejected:
        a consortium can be registered under a member's number.
  C2 Same normalised name, two different registered numbers (MIGUEL ACOSTA BENITEZ)
     -> never merged. Two people can share a name. Flagged for a human.
  C3 A 'notifiedSupplier' party with a hashed, per-process id and no identifier
     (2,288 in 2021) whose normalised name matches identified organisations
     -> ppo:candidateSameAs if exactly ONE identified organisation has that name,
        else left ambiguous. Name is the only evidence, so it is never owl:sameAs.

Checking C3 without hand labels ("silver" labels): if the same process also lists an
identified organisation with that name (as buyer, tenderer or supplier), that is
independent evidence of who the notified company is. We measure how often the
global unique-name rule picks that same organisation.

Output: output/graph/sameas.ttl, output/step2/er_candidates.csv, output/step2/er_report.txt
"""
import difflib
import re
import sys
import unicodedata
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import rdf as R  # noqa: E402
from common.config import OUT  # noqa: E402
from common.data import load  # noqa: E402

DEST = OUT / "step2"
DEST.mkdir(parents=True, exist_ok=True)
(OUT / "graph").mkdir(parents=True, exist_ok=True)


def norm(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"\b(s\.?a\.?|s\.?r\.?l\.?|sociedad anonima)\b", "", s)   # legal-form noise
    return re.sub(r"[^a-z0-9]", "", s)


def sim(a, b):
    return difflib.SequenceMatcher(None, norm(a), norm(b)).ratio()


parties = load("parties", ["main_ocid", "id", "name", "roles", "identifier_id", "identifier_scheme"])
parties = parties.dropna(subset=["id", "name"])
orgs = parties.sort_values("name").drop_duplicates("id", keep="last").copy()
orgs["nn"] = orgs["name"].map(norm)
orgs["hashed"] = orgs["identifier_id"].isna() & orgs["roles"].str.contains("notifiedSupplier", na=False)
ident = orgs[~orgs["hashed"] & orgs["identifier_id"].notna()]
rows = []

# ------------------------------------------------------------------ C1
ruc = ident[ident["identifier_scheme"] == "PY-RUC"].copy()
ruc["base"] = ruc["identifier_id"].str.replace(r"-\d$", "", regex=True)
c1 = ruc.merge(ruc, on="base").query("id_x < id_y")
for r in c1.itertuples():
    s = sim(r.name_x, r.name_y)
    ok = s >= 0.85
    rows.append({"kind": "C1 check digit", "a": r.id_x, "b": r.id_y, "name_a": r.name_x, "name_b": r.name_y,
                 "name_sim": round(s, 2), "decision": "owl:sameAs" if ok else "rejected: same number, different name"})

# ------------------------------------------------------------------ C2
c2 = ident.merge(ident, on="nn").query("id_x < id_y")
c2 = c2[~c2.apply(lambda r: re.sub(r"-\d$", "", str(r.identifier_id_x)) ==
                  re.sub(r"-\d$", "", str(r.identifier_id_y)), axis=1)] if len(c2) else c2
for r in c2.itertuples():
    rows.append({"kind": "C2 same name, different number", "a": r.id_x, "b": r.id_y, "name_a": r.name_x,
                 "name_b": r.name_y, "name_sim": 1.0, "decision": "not merged: flag for human review"})

# ------------------------------------------------------------------ C3
hashed = orgs[orgs["hashed"]]
by_name = ident.groupby("nn")["id"].unique()
proc_of = parties.groupby("id")["main_ocid"].first()
same_proc = parties[parties["identifier_id"].notna()].assign(nn=lambda d: d["name"].map(norm))
same_proc = same_proc.groupby(["main_ocid", "nn"])["id"].first()

agree = disagree = silver_n = 0
for r in hashed.itertuples():
    cands = by_name.get(r.nn)
    if cands is None:
        continue
    pick = cands[0] if len(cands) == 1 else None
    silver = same_proc.get((proc_of.get(r.id), r.nn))
    if pick is not None and silver is not None:
        silver_n += 1
        agree += pick == silver
        disagree += pick != silver
    rows.append({"kind": "C3 notified supplier, name only", "a": r.id, "b": pick or " | ".join(cands[:5]),
                 "name_a": r.name, "name_b": r.name, "name_sim": 1.0,
                 "decision": "ppo:candidateSameAs" if pick is not None else f"ambiguous: {len(cands)} candidates",
                 "silver": silver or ""})

cand = pd.DataFrame(rows)
cand.to_csv(DEST / "er_candidates.csv", index=False)

# the links as Turtle (plain text, like the rest of Step 2)
lines = ["@prefix owl: <http://www.w3.org/2002/07/owl#> .", "@prefix ppo: <https://ul.edu.lb/kr/ont/ppo#> .", ""]
for r in cand.itertuples():
    pred = {"owl:sameAs": "owl:sameAs", "ppo:candidateSameAs": "ppo:candidateSameAs"}.get(r.decision)
    if pred:
        lines.append(f"{R.org(r.a)} {pred} {R.org(r.b)} .")
(OUT / "graph" / "sameas.ttl").write_text("\n".join(lines) + "\n", encoding="utf-8")

n_c3 = len(hashed)
matched = (cand["decision"] == "ppo:candidateSameAs").sum()
report = [
    "Entity resolution report",
    f"Organisations: {len(orgs):,} ({len(hashed):,} notified suppliers with hashed ids, no identifier)", "",
    cand.groupby(["kind", "decision"]).size().to_string(), "",
    f"C3 coverage: {matched:,} of {n_c3:,} hashed parties linked to exactly one identified organisation "
    f"({matched / max(n_c3, 1):.0%}).",
    f"C3 check against same-process evidence: {silver_n:,} links could be checked; the unique-name rule "
    f"picked the same organisation in {agree:,} ({agree / max(silver_n, 1):.1%}), a different one in {disagree:,}.",
    "",
    "Caveat: the same-process check also matches on name, so it confirms the rule is consistent "
    "with local evidence; it is not an independent hand-labelled gold set.", "",
    f"A naive 'merge on normalised name' would also merge the {len(c2)} C2 pairs, which hold different "
    "registered numbers. Some may be one consortium registered twice, but some are clearly different "
    "people (MIGUEL ACOSTA BENITEZ: 3974560-0 and 3201376-0), so none are merged without more evidence.",
    "C1 pairs:",
    *[f"  {r.a} / {r.b}: {r.name_a!r} vs {r.name_b!r} sim {r.name_sim} -> {r.decision}"
      for r in cand[cand['kind'].str.startswith('C1')].itertuples()],
]
(DEST / "er_report.txt").write_text("\n".join(report) + "\n", encoding="utf-8")
print("\n".join(report))
