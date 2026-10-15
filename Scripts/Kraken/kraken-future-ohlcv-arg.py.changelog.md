# Changelog — kraken-future-ohlcv-arg.py

## 2026-10-15

Renommage du fichier concat : `Kraken_futures_ALL_1m_[dates].csv` au lieu de `futures_ALL_1m_[dates].csv`. Les fichiers par symbole gardent le préfixe `futures_`.

## 2026-09-23

Retrait de la partie Spot (`--market`, `--pair`) : le script ne gère
plus que les Futures. La partie Spot devient un script dédié,
`kraken-spot-ohlcv-arg.py`.

## 2026-09-23

Version initiale (0-1-0). Variante pilotable par arguments CLI du script interactif `kraken-future-ohlcv-ihm.py` (mêmes endpoints, même logique de téléchargement/reprise/CSV), pour permettre le lancement par un script d'automatisation sans interaction.

- Téléchargement OHLC Kraken vers CSV AmiBroker, Spot ou Futures (PF linéaire / PI inverse), via `--market {spot,futures}` (défaut futures)
- Spot : `--pair` (défaut XBTUSD) et `--interval` en minutes (défaut 1)
- Futures : `--contract-type {PF,PI}` (défaut PF), `--symbol` (un symbole) ou `--all` (défaut, tous les symboles de la catégorie), `--interval` type 1m/5m/15m/1h/1d (défaut 1m)
- Plage de dates via `--start`/`--end`, défaut hier→aujourd'hui UTC (borne de fin exclusive)
- Reprise intra-symbole depuis la dernière bougie du CSV existant, et par symbole via `--resume-from` (mode --all, ordre alphabétique, futures uniquement)
- Mode concat via `--concat`/`--no-concat` (défaut concat activé, mode --all, futures uniquement)
- Barres de progression globale et par symbole
- Retry HTTP avec backoff
- Suppression automatique des JSONL temporaires après chaque symbole
- Aucune dépendance externe (stdlib Python 3.10+ uniquement, argparse)
