# Changelog — mexc-spot-ohlcv-ihm.py

## 2026-09-23

Rebasage en version 0-1-0 : nouveau point de départ du versioning pour ce script dans ce dépôt. L'historique 0-1-0 → 0-2-0 de l'ancien script `updateDataMexcSpot` (sous `Scripts/Mexc/Archive/`, hors dépôt git) n'est pas repris ici.

- Téléchargement OHLCV MEXC Spot vers CSV AmiBroker (endpoints publics klines + ticker/24hr, aucune authentification requise)
- Sélection interactive : Top 5 USDT par volume 24h, symbole manuel, ou TOUS les symboles USDT
- Intervalles : 1m, 5m, 15m, 30m, 60m (alias 1h), 4h, 1d, 1W (alias 1w), 1M
- Plage de dates saisie interactivement, défaut hier→aujourd'hui UTC (borne de fin exclusive)
- Pagination automatique (max 500 bougies/appel, maximum réel MEXC)
- Reprise intra-symbole depuis la dernière bougie du CSV existant, et par symbole (mode ALL, ordre alphabétique)
- Mode concat : un seul CSV multi-tickers (mode ALL uniquement)
- Barres de progression globale et par symbole
- Retry HTTP avec backoff, gestion rate limit 429/418
- Suppression automatique des JSONL temporaires après chaque symbole
- Avertissement non-bloquant si la plage demandée dépasse la profondeur historique estimée (~30 jours)
- Aucune dépendance externe (stdlib Python 3.10+ uniquement)
