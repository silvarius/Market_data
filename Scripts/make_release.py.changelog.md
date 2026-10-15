# Changelog - make_release.py

## 2026-10-15

Release portée à 0-1-1 (`RELEASE_VERSION`). Versions des composants inchangées (toujours 0-1-0).

- Le zip embarque désormais la skill serveur `ohlcv-runner-ops` (source : `Scripts/skills/ohlcv-runner-ops/SKILL.md`, livrée en `Donnees_import/.claude/skills/ohlcv-runner-ops/SKILL.md`) : déploiement d'un zip déposé dans `~/`, vérification, diagnostic des imports
- Liste `SERVER_SKILLS` ; la skill est mentionnée dans `MANIFEST.txt`
- La skill de développement `deploy-ohlcv-runner` gagne l'étape de suppression du zip sur le serveur après déploiement, et décrit le dépôt du zip par FileZilla

## 2026-10-15

Version initiale. Construit `dist/ohlcv-runner-<version>.zip` (release 0-1-0) : `run_ohlcv.sh` + les scripts `-arg` Hyperliquid, Kraken Future et Mexc Spot + leurs changelogs + `MANIFEST.txt` (version de chaque composant).

- Portable Linux / Windows (stdlib Python 3.10+)
- Dossier racine `Donnees_import/` dans le zip (dézip depuis `~/`) ; jamais de `Donnees/`, `logs/` ni `Rapports/`
- Fins de ligne normalisées en LF ; bit exécutable posé sur `.sh` et `.py` ; zip reproductible (dates fixes)
- Versions des composants lues dans leur constante `VERSION`
