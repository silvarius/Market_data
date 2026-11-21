@AGENTS.md

# Organisation des données (poste Tower4)

Depuis le 2026-11-21, les données de marché vivent uniquement dans
`~/Tower4/Market_data/`, un dossier par marché :

- `Kraken/`, `Hyperliquid/`, `Mexc/` : séries OHLCV 1mn (zips et CSV produits par
  `Scripts/`) ; `Raw_data/` y reçoit les fichiers téléchargés.
- `CME/` : données Databento, séries continues, scripts de construction
  (`scripts/`). C'est un dépôt git indépendant (`silvarius/donnees-trading`, ancien
  `Trading_data/Donnees_trading`), ignoré par le dépôt `Market_data`.
- `Amibroker/`, `Cache/` : emplacements réservés (base AmiBroker, caches des backtests).
- Les dossiers de données ne sont pas versionnés par le dépôt `Market_data` (voir
  `.gitignore`) ; seuls `Scripts/`, `S3_ovh_ohlcv/`, les skills et les `.ods` le sont.
- `Base_data/` (git-ignoré) n'existe que sur les postes distants (cloud, VPS) : cache plat
  du bucket S3 rempli par `S3_ovh_ohlcv/fetch_data.py`.

Anciens emplacements (copies conservées, ne plus y écrire) : `~/Tower4/Trading_data/`,
`Trading/Market_data/Base_data/` (Drive), `/run/media/jerome/Maxtor/Trading/`.
