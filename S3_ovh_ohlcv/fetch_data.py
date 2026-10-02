"""Télécharge les données OHLCV du bucket public OVH `resodia-ohlcv` vers
`Market_data/Base_data/` (dossier lu par les scripts de backtest du projet
gunmaster). Les zips ne sont pas dézippés (les scripts les lisent
directement). Aucune clé ni dépendance externe.

Usage :
    python S3_ovh_ohlcv/fetch_data.py [--dest DIR] [--prefix XXX] [--list]

Tous les objets du bucket (ou du préfixe) sont téléchargés. Les fichiers déjà
présents avec la même taille sont ignorés.
"""
import argparse
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

BASE_URL = "https://resodia-ohlcv.s3.eu-west-par.io.cloud.ovh.net/"
DEFAULT_DEST = Path(__file__).resolve().parents[1] / "Base_data"
NS = {"s3": "http://s3.amazonaws.com/doc/2006-03-01/"}


def list_objects(prefix=""):
    """Liste publique du bucket (ListObjectsV2, paginée) : [(clé, taille)]."""
    token = None
    while True:
        params = {"list-type": "2", "prefix": prefix}
        if token:
            params["continuation-token"] = token
        with urllib.request.urlopen(BASE_URL + "?" + urllib.parse.urlencode(params), timeout=60) as r:
            root = ET.fromstring(r.read())
        for c in root.findall("s3:Contents", NS):
            key = c.findtext("s3:Key", namespaces=NS)
            if not key.endswith("/"):
                yield key, int(c.findtext("s3:Size", namespaces=NS))
        if root.findtext("s3:IsTruncated", namespaces=NS) != "true":
            return
        token = root.findtext("s3:NextContinuationToken", namespaces=NS)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dest", default=str(DEFAULT_DEST))
    ap.add_argument("--prefix", default="")
    ap.add_argument("--list", action="store_true", help="lister sans télécharger")
    args = ap.parse_args()

    try:
        objects = list(list_objects(args.prefix))
    except Exception as e:
        sys.exit(f"Listing impossible ({e}) : réseau bloqué vers *.io.cloud.ovh.net ?")
    print(f"{len(objects)} objets, {sum(s for _, s in objects) / 1e6:.1f} Mo")
    if args.list:
        for key, size in objects:
            print(f"{size / 1e6:10.2f} Mo  {key}")
        return

    dest = Path(args.dest)
    dest.mkdir(parents=True, exist_ok=True)
    for key, size in objects:
        target = dest / Path(key).name
        if target.exists() and target.stat().st_size == size:
            print(f"OK (déjà présent) : {target.name}")
            continue
        print(f"Téléchargement : {key} ({size / 1e6:.1f} Mo)")
        tmp = target.with_suffix(target.suffix + ".part")
        try:
            urllib.request.urlretrieve(BASE_URL + urllib.parse.quote(key), tmp)
        except Exception as e:
            tmp.unlink(missing_ok=True)
            sys.exit(f"Échec du téléchargement de {key} : {e}")
        if tmp.stat().st_size != size:
            tmp.unlink(missing_ok=True)
            sys.exit(f"Taille inattendue pour {key}.")
        tmp.replace(target)
    print(f"Données dans : {dest}")


if __name__ == "__main__":
    main()
