---
name: ohlcv-runner-ops
description: Déploiement d'une nouvelle version du runner OHLCV (run_ohlcv.sh + scripts -arg Hyperliquid, Kraken Future, Mexc Spot) à partir d'un zip de release déposé dans ~/, vérification du déploiement et diagnostic des imports nocturnes (rapports, logs). À consulter dès qu'un zip ohlcv-runner-*.zip est déposé dans ~/, ou pour comprendre un échec d'import ou un fichier manquant dans Donnees/.
---

# Runner OHLCV : déploiement et exploitation (serveur)

Le runner est installé dans `~/Donnees_import` (`/home/ubuntu/Donnees_import`,
chemin écrit en dur dans `run_ohlcv.sh`). Un cron lance `run_ohlcv.sh` chaque nuit ;
il exécute, dans cet ordre, les scripts `Hyperliquid/hyperliquid-future-ohlcv-arg.py`,
`Kraken/kraken-future-ohlcv-arg.py` et `Mexc/mexc-spot-ohlcv-arg.py`.

Arborescence :

- `run_ohlcv.sh`, `Hyperliquid/`, `Kraken/`, `Mexc/`, `MANIFEST.txt` : fournis par la release (écrasés à chaque déploiement).
- `Donnees/` (CSV produits), `logs/`, `Rapports/` : générés par le runner, **jamais dans le zip, à ne jamais supprimer ni écraser**.

## Déployer une nouvelle version

L'utilisateur dépose lui-même le zip `ohlcv-runner-<version>.zip` dans `~/`
(FileZilla). Ne pas chercher à le télécharger.

1. Vérifier que le zip est bien dans `~/` et noter sa version.
2. Dézipper depuis `~/` (le zip contient le dossier racine `Donnees_import/`) :
   ```
   cd ~
   unzip -o ohlcv-runner-<version>.zip
   ```
   `-o` écrase les scripts sans question ; `Donnees/`, `logs/` et `Rapports/` ne sont pas touchés.
3. Vérifier : `cat ~/Donnees_import/MANIFEST.txt` doit afficher la version déposée,
   et `ls -l ~/Donnees_import/run_ohlcv.sh` doit montrer le bit exécutable
   (sinon `chmod +x ~/Donnees_import/run_ohlcv.sh`).
4. Contrôler que `python3 --version` est ≥ 3.10 (stdlib uniquement, pas de `pip install`).
5. Contrôler que le cron appelle bien `/home/ubuntu/Donnees_import/run_ohlcv.sh` (`crontab -l`),
   **sans le modifier** : signaler tout écart à l'utilisateur.
6. Supprimer le zip : `rm ~/ohlcv-runner-<version>.zip`.
7. Ne pas lancer `run_ohlcv.sh` pour « tester » sans demande de l'utilisateur : un run complet
   télécharge une journée de données pour tous les symboles et peut être long.

## Vérifier un déploiement après le premier run nocturne

- `Rapports/rapport_<AAAA-MM-JJ>.txt` : la première ligne se termine par
  `(run_ohlcv.sh v<version>)` ; chacun des trois scripts doit afficher `OK`.
- `Donnees/` doit contenir, pour la date : `Kraken_futures_ALL_1m_*.csv`,
  `hyperliquid_futures_1m_*.csv`, `mexc_spot_ALL_1m_*.csv` (+ les fichiers par symbole).

## Diagnostiquer un échec

- Rapport : `<script>: ECHEC (code N)` pour le script en cause (le runner continue avec les suivants
  et sort en code 1 si l'un a échoué).
- Log détaillé : `logs/<script>_<AAAAMMJJ_HHMMSS>.log` (lancement, sortie du script, code de fin).
- Causes habituelles : API de l'exchange indisponible ou limitée (429/418, déjà gérés par retry),
  `python3` trop ancien, droits d'exécution perdus, disque plein (`df -h`).
- Les scripts reprennent d'eux-mêmes un CSV partiel existant : relancer un seul script est sans danger
  pour les données déjà téléchargées, p. ex.
  `python3 ~/Donnees_import/Kraken/kraken-future-ohlcv-arg.py --out-dir ~/Donnees_import/Donnees`
  (voir `--help` pour `--symbol`, `--start`, `--end`, `--resume-from`). À faire seulement sur demande.

## Limites

- Lire rapports, logs, `MANIFEST.txt`, la crontab : libre.
- Déployer un zip déposé par l'utilisateur : libre (étapes ci-dessus).
- Modifier le cron, modifier les scripts livrés, supprimer quoi que ce soit dans
  `Donnees/`, `logs/` ou `Rapports/`, relancer un import : uniquement sur demande explicite.
  Les scripts sont produits depuis le dépôt de développement (poste de l'utilisateur) :
  toute modification faite ici serait écrasée au prochain déploiement.
