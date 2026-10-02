# Changelog — fetch_data.py

## 2026-10-02

Version initiale (0-1-0). Téléchargement des fichiers OHLCV stockés dans le
bucket OVH Object Storage public `resodia-ohlcv` (région eu-west-par) vers
`Market_data/Base_data/`, pour pouvoir travailler depuis une session cloud
(données trop volumineuses pour être dans le repo git).

- Listing public du bucket (ListObjectsV2, paginé) puis téléchargement de tous les objets
- `--prefix` pour limiter à un préfixe, `--dest` pour changer le dossier de destination, `--list` pour lister sans télécharger
- Fichiers déjà présents avec la même taille ignorés ; téléchargement dans un `.part`, taille vérifiée avant renommage
- Zips non dézippés : les scripts de backtest les lisent directement
- Aucune clé ni dépendance externe (stdlib Python uniquement) : bucket public en lecture
