# Changelog - make_release.py

## 2026-10-15

Version initiale. Construit `dist/ohlcv-runner-<version>.zip` (release 0-1-0) : `run_ohlcv.sh` + les scripts `-arg` Hyperliquid, Kraken Future et Mexc Spot + leurs changelogs + `MANIFEST.txt` (version de chaque composant).

- Portable Linux / Windows (stdlib Python 3.10+)
- Dossier racine `Donnees_import/` dans le zip (dézip depuis `~/`) ; jamais de `Donnees/`, `logs/` ni `Rapports/`
- Fins de ligne normalisées en LF ; bit exécutable posé sur `.sh` et `.py` ; zip reproductible (dates fixes)
- Versions des composants lues dans leur constante `VERSION`
