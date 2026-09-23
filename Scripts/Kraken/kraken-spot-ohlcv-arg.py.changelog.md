# Changelog — kraken-spot-ohlcv-arg.py

## 2026-09-23

Version initiale (0-1-0). Extrait de la partie Spot de
`kraken-future-ohlcv-arg.py`, qui ne gère désormais plus que les
Futures. Variante pilotable par arguments CLI du script interactif
`kraken-spot-ohlcv-ihm.py` (mêmes endpoints, même logique de
téléchargement/reprise/CSV), pour permettre le lancement par un script
d'automatisation sans interaction.

- Téléchargement OHLC Kraken Spot vers CSV AmiBroker, endpoint public OHLC
- `--pair` (défaut XBTUSD) et `--interval` en minutes (défaut 1)
- Plage de dates via `--start`/`--end`, défaut hier→aujourd'hui UTC (borne de fin exclusive)
- Reprise depuis la dernière bougie du CSV existant
- Retry HTTP avec backoff
- Suppression automatique du JSONL temporaire en fin de téléchargement
- Aucune dépendance externe (stdlib Python 3.10+ uniquement, argparse)
