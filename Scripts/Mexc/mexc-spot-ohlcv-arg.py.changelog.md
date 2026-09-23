# Changelog — mexc-spot-ohlcv-arg.py

## 2026-09-23

Version initiale (0-1-0). Variante pilotable par arguments CLI du script interactif `mexc-spot-ohlcv-ihm.py` (mêmes endpoints, même logique de téléchargement/reprise/CSV), pour permettre le lancement par un script d'automatisation sans interaction.

- Téléchargement OHLCV MEXC Spot vers CSV AmiBroker (endpoints publics klines + ticker/24hr, aucune authentification requise)
- Sélection via arguments : `--symbol` (un symbole) ou `--all` (tous les symboles USDT, défaut)
- Intervalles : 1m, 5m, 15m, 30m, 60m (alias 1h), 4h, 1d, 1W (alias 1w), 1M via `--interval`
- Plage de dates via `--start`/`--end`, défaut hier→aujourd'hui UTC (borne de fin exclusive)
- Pagination automatique (max 500 bougies/appel, maximum réel MEXC)
- Reprise intra-symbole depuis la dernière bougie du CSV existant, et par symbole via `--resume-from` (mode --all, ordre alphabétique)
- Mode concat via `--concat`/`--no-concat` (défaut concat activé, mode --all uniquement)
- Barres de progression globale et par symbole
- Retry HTTP avec backoff, gestion rate limit 429/418
- Suppression automatique des JSONL temporaires après chaque symbole
- Avertissement non-bloquant si la plage demandée dépasse la profondeur historique estimée (~30 jours)
- Aucune dépendance externe (stdlib Python 3.10+ uniquement, argparse)
