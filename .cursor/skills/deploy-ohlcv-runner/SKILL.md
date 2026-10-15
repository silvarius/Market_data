---
name: deploy-ohlcv-runner
description: Construction, publication (release GitHub) et déploiement sur serveur Linux du runner OHLCV nocturne (run_ohlcv.sh + scripts -arg Hyperliquid, Kraken Future, Mexc Spot). À consulter avant de livrer une nouvelle version de ces scripts, de les déployer sur un serveur, ou de vérifier un déploiement existant.
---

# Release et déploiement du runner OHLCV

`run_ohlcv.sh` lance les scripts `-arg` par chemin relatif : on les livre
toujours ensemble, sous un seul numéro de release (`ohlcv-runner-<version>.zip`).
La version de chaque composant figure dans son `VERSION` et dans le
`MANIFEST.txt` du zip.

## Construire (Linux ou Windows)

```
python Scripts/make_release.py      # -> dist/ohlcv-runner-<version>.zip (dist/ est ignoré par git)
```

Pour une nouvelle version : modifier `RELEASE_VERSION` dans `make_release.py`,
mettre à jour les `VERSION` / changelogs des composants modifiés, committer,
puis construire. Le zip ne contient que `run_ohlcv.sh`, les trois scripts
`-arg.py` et leurs changelogs (pas les `-ihm.py`, pas `kraken-spot`).

## Publier

1. Tag git `release-<version>` (ex. `release-0-1-0`) sur le commit livré, poussé sur `origin`.
2. Release GitHub (dépôt `silvarius/Market_data`) sur ce tag, avec le zip en pièce jointe
   (`gh release create release-0-1-0 dist/ohlcv-runner-0-1-0.zip` si `gh` est installé,
   sinon via l'interface web).

## Déployer sur le serveur (Linux, utilisateur `ubuntu`)

Le zip contient un dossier `Donnees_import/` : il se place et se dézippe à la
racine de `~/`.

```
cd ~
unzip -o ohlcv-runner-<version>.zip
cat Donnees_import/MANIFEST.txt
```

- Un dézip par-dessus un déploiement existant est sans risque pour les
  données : `Donnees/`, `logs/` et `Rapports/` ne sont pas dans le zip.
- Les scripts sont livrés exécutables ; si besoin : `chmod +x Donnees_import/run_ohlcv.sh`.
- Prérequis : `python3` ≥ 3.10 (stdlib uniquement, aucun `pip install`).
- `run_ohlcv.sh` a `DIR=/home/ubuntu/Donnees_import` codé en dur : un
  déploiement ailleurs exige de modifier cette variable.
- Cron : l'entrée doit appeler `/home/ubuntu/Donnees_import/run_ohlcv.sh`
  (chemin absolu). Vérifier avec `crontab -l` ; ne pas la recréer si elle existe déjà.

## Vérifier

- `Donnees_import/MANIFEST.txt` affiche la version attendue.
- Après le premier run nocturne : `Donnees_import/Rapports/rapport_<date>.txt` commence par
  `(run_ohlcv.sh v<version>)` et affiche `OK` pour les trois scripts ; sinon
  voir `Donnees_import/logs/`.
- Fichiers attendus dans `Donnees/` : `Kraken_futures_ALL_1m_*.csv`,
  `hyperliquid_futures_1m_*.csv`, `mexc_spot_ALL_1m_*.csv`.
