#!/usr/bin/env python3
"""Construit le zip de release du runner OHLCV (run_ohlcv.sh + scripts -arg).

Portable Linux / Windows (stdlib uniquement, Python 3.10+).

Usage :
    python Scripts/make_release.py            # -> dist/ohlcv-runner-<RELEASE_VERSION>.zip
    python Scripts/make_release.py --out-dir X

Le zip contient un dossier racine `Donnees_import/` : il se dézippe depuis
~/ et déploie dans ~/Donnees_import. Il ne contient jamais Donnees/, logs/
ni Rapports/ (un dézip par-dessus un déploiement existant est sans risque).
"""
import argparse
import re
import sys
import zipfile
from pathlib import Path

RELEASE_VERSION = "0-1-0"
ROOT_DIR = "Donnees_import"
SCRIPTS_DIR = Path(__file__).resolve().parent

# Fichiers lancés par run_ohlcv.sh (chemins relatifs à Scripts/).
# Chaque script est accompagné de son changelog `<nom>.changelog.md`.
COMPONENTS = [
    "run_ohlcv.sh",
    "Hyperliquid/hyperliquid-future-ohlcv-arg.py",
    "Kraken/kraken-future-ohlcv-arg.py",
    "Mexc/mexc-spot-ohlcv-arg.py",
]

VERSION_RE = re.compile(r'^\s*VERSION\s*=\s*"([^"]+)"', re.MULTILINE)
FIXED_DATE = (2026, 1, 1, 0, 0, 0)  # zip reproductible


def read_bytes_lf(path: Path) -> bytes:
    """Contenu du fichier avec fins de ligne LF (indispensable pour bash)."""
    return path.read_bytes().replace(b"\r\n", b"\n")


def component_version(path: Path) -> str:
    m = VERSION_RE.search(path.read_text(encoding="utf-8"))
    if not m:
        sys.exit(f"Constante VERSION introuvable dans {path}")
    return m.group(1)


def add(zf: zipfile.ZipFile, arcname: str, data: bytes, executable: bool = False):
    info = zipfile.ZipInfo(f"{ROOT_DIR}/{arcname}", date_time=FIXED_DATE)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = (0o755 if executable else 0o644) << 16
    zf.writestr(info, data)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out-dir", type=Path, default=SCRIPTS_DIR.parent / "dist")
    args = ap.parse_args()

    manifest = [f"ohlcv-runner {RELEASE_VERSION}", ""]
    files = []
    for rel in COMPONENTS:
        src = SCRIPTS_DIR / rel
        if not src.is_file():
            sys.exit(f"Fichier manquant : {src}")
        manifest.append(f"{rel}  v{component_version(src)}")
        files.append((rel, src))
        changelog = src.with_name(src.name + ".changelog.md")
        if changelog.is_file():
            files.append((changelog.relative_to(SCRIPTS_DIR).as_posix(), changelog))

    args.out_dir.mkdir(parents=True, exist_ok=True)
    out = args.out_dir / f"ohlcv-runner-{RELEASE_VERSION}.zip"
    with zipfile.ZipFile(out, "w") as zf:
        add(zf, "MANIFEST.txt", ("\n".join(manifest) + "\n").encode("utf-8"))
        for rel, src in files:
            add(zf, rel, read_bytes_lf(src), executable=rel.endswith((".sh", ".py")))

    print(f"Release {RELEASE_VERSION} -> {out}")
    print("\n".join(manifest[2:]))


if __name__ == "__main__":
    main()
