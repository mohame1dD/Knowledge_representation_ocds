"""Copy hooks/pre-commit into .git/hooks so every commit runs the SHACL gate."""
import shutil
import stat
from pathlib import Path

root = Path(__file__).resolve().parent.parent
dst = root / ".git" / "hooks" / "pre-commit"
if not dst.parent.exists():
    raise SystemExit("Not a git repository: run `git init` first")
shutil.copy(root / "hooks" / "pre-commit", dst)
dst.chmod(dst.stat().st_mode | stat.S_IEXEC)
print(f"Installed {dst}")
