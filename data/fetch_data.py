"""Step 1a: download the Paraguay DNCP OCDS CSV bundles for the configured years.

    python data/fetch_data.py            # years from .env (default 2019 to 2022)
    python data/fetch_data.py 2022       # one year

Each yearly archive holds 70+ CSV files. We only keep the 9 this project uses,
streaming them out of the archive so the other ~90% never touches the disk.
Source and licence: data/LICENCE.txt.
"""
import sys
import tarfile
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common.config import DATA_DIR, YEARS  # noqa: E402

URL = "https://data.open-contracting.org/en/publication/63/download?name={year}.csv.tar.gz"
KEEP = {
    "main", "parties", "awards", "awards_suppliers", "contracts", "tender_tenderers",
    # profiled in step 1 but not used in the graph
    "tender_lots", "tender_items", "contracts_implementation_transactions",
}


def progress(block, size, total):
    if total > 0 and block % 200 == 0:
        print(f"\r  {min(block * size, total) / 1e6:7.0f} / {total / 1e6:.0f} MB", end="", flush=True)


def fetch(year):
    out = DATA_DIR / str(year)
    if all((out / f"{t}.csv").exists() for t in KEEP):
        print(f"{year}: already there")
        return
    out.mkdir(parents=True, exist_ok=True)
    archive = DATA_DIR / f"{year}.csv.tar.gz"
    if not archive.exists():
        print(f"{year}: downloading")
        urllib.request.urlretrieve(URL.format(year=year), archive, progress)
        print()
    print(f"{year}: extracting {len(KEEP)} tables")
    with tarfile.open(archive, "r|gz") as t:          # streaming mode
        for m in t:
            name = Path(m.name).name
            if m.isfile() and name.endswith(".csv") and name[:-4] in KEEP:
                with t.extractfile(m) as src, open(out / name, "wb") as dst:
                    while chunk := src.read(1 << 20):
                        dst.write(chunk)
                print("   ", name)
    archive.unlink()   # the archive is big; delete it once the tables are out


if __name__ == "__main__":
    years = [int(a) for a in sys.argv[1:]] or YEARS
    for y in years:
        fetch(y)
    (DATA_DIR.parent / "LICENCE.txt").write_text(
        "Source: Paraguay DNCP (Direccion Nacional de Contrataciones Publicas) via the OCP Data Registry\n"
        "https://data.open-contracting.org/en/publication/63\n"
        f"Years used: {', '.join(map(str, years))}\n"
        "Licence: CC BY 4.0 https://creativecommons.org/licenses/by/4.0/\n"
        "Changes: only 9 of the published CSV tables are kept; the graph steps transform them to RDF.\n")
