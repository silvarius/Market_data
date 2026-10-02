---
name: s3-ovh-ohlcv
description: Accès aux données OHLCV hébergées dans le bucket public OVH resodia-ohlcv (S3, région eu-west-par) — téléchargement vers Market_data/Base_data avec S3_ovh_ohlcv/fetch_data.py, notamment depuis une session cloud ; ajout de nouveaux fichiers au bucket. À consulter dès que des données de backtest manquent dans Base_data, avant tout travail en session cloud, ou avant d'envoyer un fichier dans le bucket.
---

# Données OHLCV sur le bucket S3 OVH

Les fichiers OHLCV (volumineux, hors git) sont stockés dans le bucket OVH
Object Storage **public en lecture** `resodia-ohlcv` (région `eu-west-par`,
endpoint `https://s3.eu-west-par.io.cloud.ovh.net`, URL virtual-host
`https://resodia-ohlcv.s3.eu-west-par.io.cloud.ovh.net/`). Les fichiers
doivent être dans `Market_data/Base_data/` pour que les scripts de backtest
(projet gunmaster : `Trading/Modeles/Gunmaster/Backtest/`) les trouvent.

## Télécharger

```
python S3_ovh_ohlcv/fetch_data.py            # tout le bucket -> Base_data/
python S3_ovh_ohlcv/fetch_data.py --list     # lister sans télécharger
```

Options : `--prefix`, `--dest`. Fichiers déjà présents (même taille)
ignorés ; zips non dézippés (les scripts les lisent directement). Aucune clé
ni dépendance externe. Détail : `S3_ovh_ohlcv/fetch_data.py.changelog.md`.

## Session cloud

- Cloner **les deux dépôts** : `Market_data` et `Gunmaster`. Les scripts de
  backtest cherchent les données en `<Gunmaster>/../../Market_data/Base_data/`
  (arborescence `Trading/Modeles/Gunmaster` + `Trading/Market_data`). Si
  l'arborescence cloud diffère, passer `--dest` et surcharger le chemin de
  données côté script de backtest (argument dédié selon le script).
- Le réseau sortant de l'environnement doit autoriser
  `*.io.cloud.ovh.net`. Si `fetch_data.py` échoue au listing, c'est la
  cause probable.
- Premier réflexe en début de session : lancer `fetch_data.py`, puis vérifier
  la taille des fichiers (le script le fait).

## Ajouter un fichier au bucket

- Le bucket est public **par ACL** (`public-read`). OVH n'implémente pas
  `PutBucketPolicy` (erreur `NotImplemented`). Un nouvel objet reste donc
  **privé** s'il n'est pas envoyé avec l'ACL `public-read` — ou si l'ACL
  n'est pas posée ensuite (`put_object_acl`).
- Envoi et ACL demandent un utilisateur OVH avec droits d'écriture (rôle
  « ObjectStore operator » ou équivalent) ; une clé en lecture seule donne
  `AccessDenied`. Ne jamais stocker ces clés dans le repo.
- Nom de fichier : garder la convention existante
  (`<ticker> <exchange> futures OHLCV <début> <fin> 1mn.zip`).
- Après envoi, vérifier sans clé :
  `curl -I "https://resodia-ohlcv.s3.eu-west-par.io.cloud.ovh.net/<nom encodé>"`
  doit répondre `200`.

## Pièges connus

- Une URL présignée est signée pour **une méthode** : un `HEAD` sur une URL
  signée pour `GET` donne 403. Sans objet pour un bucket public, utile si le
  bucket redevient privé.
- La signature SigV4 est limitée à 7 jours de validité ; SigV2 accepte plus
  long mais n'est valable qu'en génération d'URL, pas pour le listing.
- Données publiques : n'y mettre que des données de marché OHLCV, jamais de
  fichier contenant des clés, des positions ou des trades réels.
