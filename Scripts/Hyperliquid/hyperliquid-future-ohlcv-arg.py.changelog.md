# Changelog — hyperliquid-future-ohlcv-arg.py

## 2026-09-23

Version initiale (0-1-0). Variante pilotable par arguments CLI du script interactif `hyperliquid-future-ohlcv-ihm.py` (mêmes endpoints, même logique de téléchargement/reprise/CSV), pour permettre le lancement par un script d'automatisation sans interaction.

- Téléchargement OHLCV Hyperliquid Perps vers CSV AmiBroker (endpoint unique POST `/info`, aucune authentification requise)
- Sélection via arguments : `--symbol` (un perp) ou `--all` (tous les perps, défaut)
- Intervalles : 1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h, 8h, 12h, 1d, 3d, 1w, 1M via `--interval`
- Plage de dates via `--start`/`--end`, défaut hier→aujourd'hui UTC (borne de fin exclusive)
- Pagination automatique (max 5000 bougies/réponse)
- Reprise intra-symbole depuis la dernière bougie du CSV existant, et par symbole via `--resume-from` (mode --all, ordre alphabétique)
- Mode concat via `--concat`/`--no-concat` (défaut concat activé, mode --all uniquement)
- Barres de progression globale et par symbole
- Retry HTTP avec backoff, gestion rate limit 429/418
- Suppression automatique des JSONL temporaires après chaque symbole
- Aucune dépendance externe (stdlib Python 3.10+ uniquement, argparse)
