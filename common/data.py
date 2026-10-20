"""Load the DNCP OCDS tables for all configured years as one DataFrame each.

Each yearly bundle has the same tables. We read the ones we need, add a `year`
column, and stack them. A process (ocid) lives in exactly one yearly bundle,
but we drop duplicate ocids anyway, keeping the latest year, in case the
registry ever moves a process between files.
"""
import pandas as pd

from common.config import DATA_DIR, YEARS


def year_dirs():
    found = []
    for y in YEARS:
        d = DATA_DIR / str(y)
        if (d / "main.csv").exists():
            found.append((y, d))
        else:
            print(f"  ! year {y}: {d}/main.csv not found, skipped (run data/fetch_data.py)")
    if not found:
        raise SystemExit("No data found. Run: python data/fetch_data.py")
    return found


def load(table, usecols=None):
    frames = []
    for y, d in year_dirs():
        p = d / f"{table}.csv"
        if not p.exists():
            continue
        df = pd.read_csv(p, dtype=str, low_memory=False,
                         usecols=(lambda c: c in usecols) if usecols else None)
        df["year"] = str(y)
        frames.append(df)
    if not frames:
        raise SystemExit(f"Table {table} not found for any year")
    df = pd.concat(frames, ignore_index=True)
    if table == "main":
        df = df.drop_duplicates("ocid", keep="last")
    return df


def num(s):
    return pd.to_numeric(s, errors="coerce")


def dt(s):
    return pd.to_datetime(s, errors="coerce", utc=True)
