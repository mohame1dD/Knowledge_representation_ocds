"""Step 2a: load the OCDS tables into a SQLite database (stands in for DNCP's live database).

    python step2_mapping/load_db.py

Tables keep the source columns. The database also gets VIEWS that do the cleaning,
so the mapping (mapping.r2rml.ttl) stays declarative:
    - method labels are trimmed (rule 18), one label per method
    - OCDS status codes are turned into PPO class IRIs (rule 6e: 'terminated' -> ClosedContract)
    - amounts are stored as plain decimal text, years and counts as integers
Swap the SQLite URL for PostgreSQL/MySQL in mapping.ini and nothing else changes.
"""
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import rdf as R  # noqa: E402
from common.config import PPO, ROOT  # noqa: E402
from common.data import load  # noqa: E402

DB = ROOT / "data" / "procurement.db"
if DB.exists():
    DB.unlink()
con = sqlite3.connect(DB)


def dec(v):
    d = R.dec(v) if R.present(v) else None
    return d.split('"')[1] if d else None


tables = {
    "main": ["ocid", "year", "buyer_id", "tender_status", "tender_title", "tender_mainProcurementCategory",
             "tender_procurementMethodDetails", "tender_value_amount", "tender_value_currency",
             "tender_tenderPeriod_startDate", "tender_tenderPeriod_endDate", "tender_datePublished",
             "tender_numberOfTenderers"],
    "parties": ["main_ocid", "id", "name", "roles", "identifier_id", "identifier_scheme",
                "address_countryName", "year"],
    "awards": ["main_ocid", "id", "date", "status", "value_amount", "value_currency"],
    "awards_suppliers": ["main_ocid", "awards_id", "id", "name"],
    "contracts": ["main_ocid", "id", "awardID", "status", "dateSigned", "period_startDate",
                  "period_endDate", "value_amount", "value_currency"],
    "tender_tenderers": ["main_ocid", "id", "name"],
}
for t, cols in tables.items():
    df = load(t)[cols].copy()
    for c in ("tender_value_amount", "value_amount"):
        if c in df:
            df[c] = df[c].map(dec)
    if "tender_numberOfTenderers" in df:
        df["tender_numberOfTenderers"] = df["tender_numberOfTenderers"].map(
            lambda v: str(int(float(v))) if R.present(v) else None)
    df.to_sql(t, con, index=False)
    print(f"{t:18} {len(df):>8,} rows")

# method lookup: the slug is the IRI key (computed once here; SQLite has no accent folding)
m = load("main")["tender_procurementMethodDetails"].dropna().unique()
con.execute("CREATE TABLE method(label TEXT, slug TEXT)")
con.executemany("INSERT INTO method VALUES (?, ?)", [(x, R.slug(x)) for x in m])

P = PPO
con.executescript(f"""
CREATE INDEX i_aw ON awards(main_ocid, id);
CREATE INDEX i_pa ON parties(id);

CREATE VIEW v_process AS SELECT ocid, CAST(year AS INTEGER) AS year, buyer_id FROM main;

CREATE VIEW v_tender AS
SELECT m.ocid, m.tender_status AS status,
  CASE m.tender_status
    WHEN 'planning' THEN '{P}PlanningTender' WHEN 'planned' THEN '{P}PlanningTender'
    WHEN 'active' THEN '{P}ActiveTender' WHEN 'complete' THEN '{P}CompleteTender'
    WHEN 'unsuccessful' THEN '{P}UnsuccessfulTender'
    WHEN 'cancelled' THEN '{P}CancelledTender' WHEN 'withdrawn' THEN '{P}CancelledTender' END AS status_class,
  m.tender_title AS title, m.tender_mainProcurementCategory AS category,
  me.slug AS method_slug, m.tender_value_amount AS estimate, m.tender_value_currency AS currency,
  NULLIF(m.tender_tenderPeriod_startDate, '') AS period_start,
  NULLIF(m.tender_tenderPeriod_endDate, '') AS period_end,
  NULLIF(m.tender_datePublished, '') AS published,
  m.tender_numberOfTenderers AS n_tenderers
FROM main m LEFT JOIN method me ON me.label = m.tender_procurementMethodDetails;

-- rule 18: one trimmed label per method
CREATE VIEW v_method AS SELECT DISTINCT slug, TRIM(label) AS label FROM method;

CREATE VIEW v_award AS
SELECT main_ocid AS ocid, id, status, NULLIF(date, '') AS date, value_amount AS amount, value_currency AS currency,
  CASE status WHEN 'active' THEN '{P}ActiveAward' WHEN 'cancelled' THEN '{P}CancelledAward'
    WHEN 'pending' THEN '{P}PendingAward' WHEN 'unsuccessful' THEN '{P}UnsuccessfulAward' END AS status_class
FROM awards;

-- rule 6e: the code 'terminated' becomes ClosedContract, never a failure
CREATE VIEW v_contract AS
SELECT main_ocid AS ocid, id, awardID AS award_id, status,
  CASE status WHEN 'active' THEN '{P}ActiveContract' WHEN 'terminated' THEN '{P}ClosedContract'
    WHEN 'cancelled' THEN '{P}CancelledContract' WHEN 'pending' THEN '{P}PendingContract' END AS status_class,
  NULLIF(dateSigned, '') AS signed, NULLIF(period_startDate, '') AS period_start,
  NULLIF(period_endDate, '') AS period_end, value_amount AS amount, value_currency AS currency
FROM contracts;

CREATE VIEW v_supplier AS SELECT main_ocid AS ocid, awards_id AS award_id, id AS org_id FROM awards_suppliers;
CREATE VIEW v_tenderer AS SELECT main_ocid AS ocid, id AS org_id FROM tender_tenderers;

-- one row per organisation: the latest year, then the highest name
CREATE VIEW v_org AS
SELECT id, name, identifier_id, identifier_scheme, address_countryName AS country FROM (
  SELECT *, ROW_NUMBER() OVER (PARTITION BY id ORDER BY year DESC, name DESC) AS rn
  FROM parties WHERE id IS NOT NULL) WHERE rn = 1;

-- every organisation referenced by a process (typed, so chunks validate alone)
CREATE VIEW v_org_ref AS
SELECT buyer_id AS org_id FROM main WHERE buyer_id IS NOT NULL
UNION SELECT id FROM tender_tenderers UNION SELECT id FROM awards_suppliers;
""")
con.commit()
con.close()
print(f"Database: {DB}")
