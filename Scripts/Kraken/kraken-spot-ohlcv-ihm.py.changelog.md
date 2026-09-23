# Changelog — kraken-spot-ohlcv-ihm.py

## 2026-09-23

Version initiale (0-1-0). Extrait de la partie Spot de
`kraken-future-ohlcv-ihm.py`, qui ne gère désormais plus que les
Futures.

- Téléchargement OHLC Kraken Spot vers CSV AmiBroker, endpoint public OHLC
- Saisie interactive de la paire (défaut XBTUSD) et de l'intervalle en minutes (défaut 1)
- Plage de dates saisie interactivement, défaut hier→aujourd'hui UTC (borne de fin exclusive)
- Reprise depuis la dernière bougie du CSV existant
- Retry HTTP avec backoff
- Suppression automatique du JSONL temporaire en fin de téléchargement
- Aucune dépendance externe (stdlib Python 3.10+ uniquement)
