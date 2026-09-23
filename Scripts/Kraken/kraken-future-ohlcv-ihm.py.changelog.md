# Changelog — kraken-future-ohlcv-ihm.py

## 2026-09-23

Version initiale (0-1-0).

- Téléchargement OHLC Kraken vers CSV AmiBroker, Spot ou Futures (PF linéaire / PI inverse)
- Spot : endpoint public OHLC, saisie interactive de la paire et de l'intervalle en minutes
- Futures : Top 5 par liquidité 24h (USD) et option TOUS les symboles de la catégorie choisie
- Plage de dates saisie interactivement, défaut hier→aujourd'hui UTC (borne de fin exclusive)
- Reprise intra-symbole depuis la dernière bougie du CSV existant, et par symbole (mode ALL, ordre alphabétique, futures uniquement)
- Mode concat : un seul CSV multi-tickers (mode ALL, futures uniquement)
- Barres de progression globale et par symbole
- Retry HTTP avec backoff
- Suppression automatique des JSONL temporaires après chaque symbole
- Aucune dépendance externe (stdlib Python 3.10+ uniquement)
