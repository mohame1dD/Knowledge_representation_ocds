"""Step 1c: check every business rule in the constraint inventory, per year.

    python step1_profiling/rule_checks.py

Your friend's 16 checks (1 to 16), plus the 7 rules he wrote from his crosstabs
(6a to 6e, 17, 18). Each rule gives: how many rows break it, out of how many,
for each year and in total. Results go to constraint_inventory.csv, and the
rows that break the 6 SELECTED rules go to output/step1/ for triage.

Key point: in OCDS an `id` inside a child table is only promised unique inside
one process, so every join uses the pair (main_ocid, id).
"""
import re
import sys
import unicodedata
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common.config import OUT, YEARS  # noqa: E402
from common.data import dt, load, num  # noqa: E402

HERE = Path(__file__).resolve().parent
EX = OUT / "step1"
EX.mkdir(parents=True, exist_ok=True)
SELECTED = {"1", "3b", "9", "11", "6e", "16"}

main = load("main")
parties = load("parties")
awards = load("awards")
suppliers = load("awards_suppliers")
contracts = load("contracts")
tenderers = load("tender_tenderers")
year_of = main.set_index("ocid")["year"]

roles = parties["roles"].fillna("").str.lower()
results = []


def record(rid, rule, cols, frame, broken, pattern, formalise, notes="", example_cols=None):
    """frame: the checked rows (must carry an ocid column `p`); broken: boolean Series."""
    frame = frame.assign(_b=broken.values, _y=frame["p"].map(year_of).fillna("?").values)
    row = {"id": rid, "rule": rule, "tables_and_columns": cols,
           "broken": int(frame["_b"].sum()), "total": len(frame)}
    for y in map(str, YEARS):
        f = frame[frame["_y"] == y]
        row[f"y{y}"] = f"{int(f['_b'].sum())}/{len(f)}"
    row["pattern"] = pattern or ("always holds" if row["broken"] == 0 else "holds with exceptions")
    row["formalise_as"] = formalise
    row["selected"] = "yes" if rid in SELECTED else ""
    row["notes"] = notes
    results.append(row)
    print(f"[{rid:>3}] {row['broken']:>6} / {row['total']:<7} {rule}")
    if rid in SELECTED and row["broken"]:
        cols_out = ["p"] + (example_cols or [])
        frame.loc[frame["_b"], cols_out].rename(columns={"p": "ocid"}).to_csv(
            EX / f"broken_rule_{rid}.csv", index=False)


def keys(df, col, pcol="main_ocid"):
    return pd.Series(list(zip(df[pcol], df[col])), index=df.index)


award_keys = set(keys(awards, "id"))
supplier_party = set(keys(parties[roles.str.contains("supplier")], "id"))
buyer_party = set(keys(parties[roles.str.contains("buyer")], "id"))

# ---------------------------------------------------------------- referential
c = contracts[contracts["awardID"].notna()].assign(p=lambda d: d["main_ocid"])
record("1", "Every contract's awardID matches an award in the same process",
       "contracts.awardID -> awards.id", c, ~keys(c, "awardID").isin(award_keys),
       None, "OWL: basedOnAward functional, Contract exactly 1 Award + SHACL sh:class",
       "Join on (main_ocid, id)", ["id", "awardID"])

s = suppliers.assign(p=suppliers["main_ocid"])
record("2", "Every award supplier is a party with the role supplier",
       "awards_suppliers.id -> parties.id (roles)", s, ~keys(s, "id").isin(supplier_party),
       None, "OWL: Supplier as defined class")

m = main[main["buyer_id"].notna()].assign(p=lambda d: d["ocid"])
record("3", "Every buyer is a party with the role buyer",
       "main.buyer_id -> parties.id (roles)", m,
       ~pd.Series(list(zip(m["ocid"], m["buyer_id"])), index=m.index).isin(buyer_party),
       None, "OWL: Buyer as defined class",
       f"{main['buyer_id'].isna().sum()} processes have no buyer_id at all")

has_sup = set(keys(suppliers, "awards_id"))
a = awards.assign(p=awards["main_ocid"])
record("3b", "Every award has at least one supplier",
       "awards.id -> awards_suppliers.awards_id", a, ~keys(a, "id").isin(has_sup),
       None, "OWL: Award subClassOf awardedTo some Organization + SHACL sh:minCount 1",
       "Open world (OWL) vs closed world (SHACL) example", ["id", "status"])

# ------------------------------------------------------------- counts / method
counted = tenderers.groupby("main_ocid").size()
n_ten = num(main["tender_numberOfTenderers"])
mm = main[n_ten.notna()].assign(p=lambda d: d["ocid"])
record("4", "tender_numberOfTenderers equals the number of tender_tenderers rows",
       "main.tender_numberOfTenderers vs count(tender_tenderers)", mm,
       num(mm["tender_numberOfTenderers"]) != mm["ocid"].map(counted).fillna(0),
       None, "SHACL/SPARQL count check (counting is not an OWL strength)")

# ------------------------------------------------------------------ coverage
contract_award = set(keys(c, "awardID"))
record("5", "Every award has a contract", "awards.id vs contracts.awardID",
       a, ~keys(a, "id").isin(contract_award), None, "SHACL warning + data-quality finding",
       "Cancelled, pending or missing data? see award status")

# ------------------------------------------------------------------ statuses
has_award = main["ocid"].isin(awards["main_ocid"])
mt = main.assign(p=main["ocid"], has_award=has_award)
st = mt["tender_status"]
f = mt[st == "complete"]
record("6a", "A complete tender has at least one award", "main.tender_status vs awards",
       f, ~f["has_award"], None, "SHACL warning")
f = mt[st == "cancelled"]
record("6b", "A cancelled tender has no award", "main.tender_status vs awards",
       f, f["has_award"], None, "SHACL warning")
f = mt[st.isin(["planning", "unsuccessful"])]
record("6c", "Tenders with status planning or unsuccessful never have an award",
       "main.tender_status vs awards", f, f["has_award"], None,
       "OWL: PlanningTender, UnsuccessfulTender subClassOf not (resultsInAward some Award)")

aw = awards[["main_ocid", "id", "date", "status", "value_amount", "value_currency"]].rename(
    columns={"id": "aid", "date": "award_date", "status": "award_status",
             "value_amount": "award_value", "value_currency": "award_currency"})
j = contracts.merge(aw, left_on=["main_ocid", "awardID"], right_on=["main_ocid", "aid"])
j = j.assign(p=j["main_ocid"])
f = j[j["status"] == "active"]
record("6d", "An active contract never sits on a cancelled award",
       "contracts.status vs awards.status", f, f["award_status"] == "cancelled",
       None, "OWL: disjoint ActiveContract / on CancelledAward")
f = j[j["status"] == "terminated"]
record("6e", "A contract with status 'terminated' sits on an active award",
       "contracts.status vs awards.status", f, f["award_status"] != "active",
       "label vs meaning",
       "OWL: ClosedContract (code 'terminated' = ran and ended, NOT failed); SHACL: exactly one status class",
       "Read as English, 'terminated' sounds like failure. In OCDS it means closed. "
       "Broken here = terminated contracts whose award is NOT active", ["id", "award_status"])

# --------------------------------------------------------------------- dates
ts, te = dt(main["tender_tenderPeriod_startDate"]), dt(main["tender_tenderPeriod_endDate"])
ok = ts.notna() & te.notna()
f = main[ok].assign(p=lambda d: d["ocid"])
record("7", "Tender period starts before it ends", "main.tender_tenderPeriod_*",
       f, ts[ok] > te[ok], None, "SHACL sh:lessThanOrEquals")

ae = awards.merge(main[["ocid", "tender_tenderPeriod_endDate"]], left_on="main_ocid", right_on="ocid")
ad, te2 = dt(ae["date"]), dt(ae["tender_tenderPeriod_endDate"])
ok = ad.notna() & te2.notna()
f = ae[ok].assign(p=lambda d: d["main_ocid"])
record("8", "An award is dated on or after the tender period ends",
       "awards.date vs main.tender_tenderPeriod_endDate", f, ad[ok] < te2[ok], None,
       "SHACL SPARQL warning")

sd, jd = dt(j["dateSigned"]), dt(j["award_date"])
ok = sd.notna() & jd.notna()
f = j[ok].assign(gap_days=((jd - sd).dt.total_seconds() / 86400).round(2)[ok])
record("9", "A contract is signed on or after its award date",
       "contracts.dateSigned vs awards.date", f, sd[ok] < jd[ok], None,
       "SHACL SPARQL constraint, severity Warning (triage the gaps)",
       "Many gaps are under a day: dateSigned is stored at 12:00, award date with a real time",
       ["id", "dateSigned", "award_date", "gap_days"])

ps, pe = dt(contracts["period_startDate"]), dt(contracts["period_endDate"])
ok = ps.notna() & pe.notna()
f = contracts[ok].assign(p=lambda d: d["main_ocid"])
record("10", "Contract period starts before it ends", "contracts.period_*",
       f, ps[ok] > pe[ok], None, "SHACL sh:lessThanOrEquals")

# --------------------------------------------------------------------- values
av = awards.assign(v=num(awards["value_amount"])).groupby("main_ocid")["v"].sum()
tv = num(main.set_index("ocid")["tender_value_amount"])
both = pd.concat([av.rename("awarded"), tv.rename("estimate")], axis=1, join="inner").dropna()
both = both.reset_index().rename(columns={"index": "p"})
both["over_pct"] = ((both["awarded"] / both["estimate"].replace(0, float("nan")) - 1) * 100).round(1)
record("11", "Total awarded value is at most the tender value",
       "sum(awards.value_amount) vs main.tender_value_amount", both,
       both["awarded"] > both["estimate"], None,
       "SHACL SPARQL constraint (needs SUM), severity Warning",
       "Currency ruled out by rule 13", ["estimate", "awarded", "over_pct"])

cv, avv = num(j["value_amount"]), num(j["award_value"])
ok = cv.notna() & avv.notna()
f = j[ok]
record("12", "Contract value equals its award value", "contracts.value_amount vs awards.value_amount",
       f, (cv[ok] - avv[ok]).abs() > 0.5, None, "SHACL SPARQL check",
       "Every contract has exactly 1 award; DNCP copies the value across")

cur = pd.concat([
    main[["ocid", "tender_value_currency"]].set_axis(["p", "c"], axis=1),
    awards[["main_ocid", "value_currency"]].set_axis(["p", "c"], axis=1),
    contracts[["main_ocid", "value_currency"]].set_axis(["p", "c"], axis=1)]).dropna()
per = cur.groupby("p")["c"].nunique().reset_index()
record("13", "Each process uses a single currency", "currency columns across main/awards/contracts",
       per, per["c"] > 1, None, "SHACL SPARQL check",
       "Currency is not constant: " + ", ".join(f"{k} {v}" for k, v in cur["c"].value_counts().items()))

money = pd.concat([awards[["main_ocid", "value_amount"]], contracts[["main_ocid", "value_amount"]]])
money = money.assign(p=money["main_ocid"]).reset_index(drop=True)
record("14", "Award and contract amounts are non-negative", "awards.value_amount, contracts.value_amount",
       money, num(money["value_amount"]) < 0, None, "SHACL sh:minInclusive 0")

# ------------------------------------------------------------ identity traps


def norm(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]", "", s)


sup = parties[roles.str.contains("supplier")].dropna(subset=["identifier_id", "name"]).copy()
first = sup.drop_duplicates("identifier_id")
g = sup.groupby("identifier_id")["name"].nunique()
f = first.assign(p=first["main_ocid"])
record("15", "One supplier identifier always carries one name", "parties.identifier_id vs parties.name",
       f, f["identifier_id"].map(g) > 1, None, "SHACL sh:maxCount 1 on rdfs:label of Organization")

sup["nn"] = sup["name"].map(norm)
g2 = sup.groupby("nn")["identifier_id"].nunique()
f = sup.drop_duplicates("nn")
f = f.assign(p=f["main_ocid"], ids=f["nn"].map(sup.groupby("nn")["identifier_id"].unique().map(list)))
record("16", "One normalised supplier name always carries one identifier",
       "parties.name (normalised) vs parties.identifier_id",
       f, f["nn"].map(g2) > 1, "identity trap",
       "Mapping + entity resolution (Step 2): owl:sameAs only when the IDs agree",
       "Do not merge on name alone: same name can be two people", ["name", "ids"])

tm = main.assign(p=main["ocid"], n=n_ten)
f = tm[tm["tender_procurementMethodDetails"].str.strip() == "Contratación Directa"]
f = f[f["n"].notna()]
record("17", "Direct contracting means at most one tenderer",
       "main.tender_procurementMethodDetails vs tender_numberOfTenderers",
       f, f["n"] > 1, "label vs meaning",
       "Not a rule: the method name does not imply one bidder (ontology note on the method)")

labels = main["tender_procurementMethodDetails"].dropna()
lab = pd.DataFrame({"label": labels.unique()})
lab["p"] = lab["label"].map(main.drop_duplicates("tender_procurementMethodDetails")
                             .set_index("tender_procurementMethodDetails")["ocid"])
lab["clean"] = lab["label"].str.strip()
record("18", "Each procurement method label appears in one spelling",
       "main.tender_procurementMethodDetails", lab,
       lab["label"] != lab["clean"], "identity trap", "Mapping: trim the label (Step 2 views)",
       "Broken = labels with leading/trailing spaces")

inv = pd.DataFrame(results)
inv.to_csv(HERE / "constraint_inventory.csv", index=False)
with open(HERE / "constraint_inventory.csv", "a") as fh:
    fh.write(f'LICENCE,"Data: Paraguay DNCP via OCP Data Registry, CC BY 4.0, years {",".join(map(str, YEARS))}",'
             + "," * (len(inv.columns) - 3) + "https://data.open-contracting.org/en/publication/63\n")
print(f"\nWrote {HERE / 'constraint_inventory.csv'} ({len(inv)} rules, "
      f"{len(SELECTED)} selected: {', '.join(sorted(SELECTED))})")
