# Changelog - run_ohlcv.sh

## 2026-10-15

Version 0-1-0. Ajout de la constante `VERSION`, affichée dans l'en-tête du rapport quotidien.

- Livré désormais avec les scripts `-arg` Hyperliquid, Kraken Future et Mexc Spot dans la release `ohlcv-runner-0-1-0.zip` (construite par `make_release.py`).
- Les fichiers concat de sortie sont renommés par les scripts lancés : `Kraken_futures_ALL_1m_[dates].csv` (ex `futures_ALL_...`) et `hyperliquid_futures_1m_[dates].csv` (ex `HL_ALL_...`). Voir les changelogs de `kraken-future-ohlcv-arg.py` et `hyperliquid-future-ohlcv-arg.py`.

## 2026-09-24

- Ajout du lancement des scripts depuis leurs sous-dossiers et propagation d'un code d'erreur au cron lorsqu'un import échoue.