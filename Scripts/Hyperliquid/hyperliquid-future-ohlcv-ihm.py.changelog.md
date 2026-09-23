# Changelog — hyperliquid-future-ohlcv-ihm.py

## 2026-09-23

Version initiale (0-1-0).

- Téléchargement OHLCV Hyperliquid Perps vers CSV AmiBroker (endpoint unique POST `/info`, aucune authentification requise)
- Sélection interactive : Top 5 perps par volume 24h (`dayNtlVlm`), symbole manuel, ou TOUS les perps
- Intervalles : 1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h, 8h, 12h, 1d, 3d, 1w, 1M
- Plage de dates saisie interactivement, défaut hier→aujourd'hui UTC (borne de fin exclusive)
- Pagination automatique (max 5000 bougies/réponse)
- Reprise intra-symbole depuis la dernière bougie du CSV existant, et par symbole (mode ALL, ordre alphabétique)
- Mode concat : un seul CSV multi-tickers (mode ALL uniquement)
- Barres de progression globale et par symbole
- Retry HTTP avec backoff, gestion rate limit 429/418
- Suppression automatique des JSONL temporaires après chaque symbole
- Aucune dépendance externe (stdlib Python 3.10+ uniquement)
