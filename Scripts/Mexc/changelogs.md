# Changelog — updateDataMexcSpot

Script Python de téléchargement de données OHLCV MEXC Spot vers CSV AmiBroker.

---

## Fonctionnalités principales

### Source de données
- Exchange : **MEXC Spot** (API publique v3)
- Endpoint klines : `GET https://api.mexc.com/api/v3/klines`
- Endpoint tickers : `GET https://api.mexc.com/api/v3/ticker/24hr`
- Authentification : clé publique API (`X-MEXC-APIKEY` dans les headers) — clé privée non requise
- Filtre marché : **paires USDT uniquement**

### Sélection des symboles
- Affichage du **Top 5 USDT** par volume 24h (quoteVolume) avec prix en cours
- Option **TOUS** les symboles USDT actifs (défaut si ENTER)
- Saisie manuelle d'un symbole arbitraire

### Intervalles supportés
Valeurs officielles MEXC : `1m`, `5m`, `15m`, `30m`, `60m`, `4h`, `1d`, `1W`, `1M`

Saisies abrégées acceptées : `1h` (=`60m`), `1w` (=`1W`)

### Plage temporelle
- Dates de début et de fin saisies interactivement (format ISO, timezone UTC)
- Valeurs par défaut : **hier 00:00:00 UTC → aujourd'hui 00:00:00 UTC** (borne de fin exclusive)
- Profondeur historique estimée à **30 jours** : un `startTime` antérieur ne provoque pas d'erreur mais les données démarrent simplement à la première bougie disponible ; un avertissement est affiché

### Pagination
- Maximum **500 bougies par appel** API (défaut et maximum MEXC)
- Découpage automatique de la plage en fenêtres de `500 × interval_sec`
- Curseur avancé bougie par bougie sans doublon

### Reprise (resume)
- **Par symbole** (mode ALL) : possibilité de reprendre à partir d'un symbole donné (ordre alphabétique)
- **Intra-symbole** : détection automatique de la dernière bougie présente dans le CSV existant ; reprise à la minute suivante
- Fonctionne en mode fichiers séparés et en mode concat

### Modes de sortie
- **Fichiers séparés** : un CSV par symbole, nommé `mexc_spot_<SYMBOL>_<interval>_<start>_to_<end>.csv`
- **Mode concat** (mode ALL uniquement) : un seul CSV multi-tickers `mexc_spot_ALL_<interval>_<start>_to_<end>.csv`

### Format CSV (compatible AmiBroker)
```
Ticker,Date,Time,Open,High,Low,Close,Volume
BTCUSDT,2024/01/15,08:00:00,42500.1,42750.0,42480.5,42600.3,125.847
```
- `Date` : `YYYY/MM/DD`
- `Time` : `HH:MM:SS`

### Progression
- Barre de progression **globale** sur l'ensemble du batch (en millisecondes couvertes)
- Barre de progression **par symbole**
- Affichage du nombre de bougies écrites à la fin de chaque symbole

### Robustesse
- Retry automatique (5 tentatives, backoff exponentiel) sur chaque appel HTTP
- Gestion spécifique des erreurs 429 (rate limit) avec pause prolongée
- Suppression automatique des fichiers JSONL (logs bruts temporaires) après chaque symbole traité
- Interruption propre par `Ctrl+C` (KeyboardInterrupt) avec code retour 130

### Configuration
- Clé API renseignée comme constante `MEXC_API_KEY` en tête de script (pas de saisie interactive)
- Vérification au démarrage : arrêt explicite si la constante n'a pas été personnalisée
- Aucune dépendance externe (stdlib Python 3.10+ uniquement)

---

## Historique des versions

---

### 0-2-0 — 2026-05-18

Première version stable. Avertissement profondeur historique 30 jours.

- Suppression de la troncature automatique à 90 jours (incorrecte) : la profondeur historique réelle de l'endpoint klines MEXC est d'environ **30 jours**. Un `startTime` antérieur ne provoque pas d'erreur API — les données démarrent simplement à la première bougie disponible.
- Ajout d'un avertissement non-bloquant lorsque le `startTime` dépasse 30 jours, indiquant la date limite estimée.
- Suppression définitive du bloc de troncature introduit en 0-1-2.

---

### 0-1-3 — 2026-05-18

Correction bug : erreur 400 causée par l'envoi de la clé API.

- Suppression de l'authentification par clé API : MEXC exige une signature HMAC-SHA256 dès qu'une clé est présente dans les headers, même pour les endpoints publics. Les endpoints utilisés (klines, tickers) étant publics, aucune clé n'est nécessaire.
- Suppression de la constante `MEXC_API_KEY`, des fonctions `set_api_key()` et `get_headers()`, et du paramètre `headers` dans `http_get_json()`.
- Mise à jour du docstring en conséquence.

---

### 0-1-2 — 2026-05-18

Correction bugs : limite historique 90 jours et boucle infinie sur erreur 400.

- Correction de la limite d'historique MEXC : l'API klines rejette tout `startTime` antérieur à 90 jours. Le script tronque désormais automatiquement la date de début avec un avertissement explicite.
- Correction de la boucle infinie : une erreur 400 (non-transitoire) provoquait un `continue` indéfini. `http_get_json` lève maintenant immédiatement une exception sur toute erreur 4xx (sauf 429/418 qui restent gérées par backoff).

---

### 0-1-1 — 2026-05-18

Correction bugs : intervalles klines invalides et limite de bougies incorrecte (HTTP 400).

- Correction des valeurs d'intervalle envoyées à l'API MEXC : remplacement des chaînes erronées (`Min1`, `Hour4`...) par les valeurs officielles de la doc (`1m`, `5m`, `60m`, `4h`, `1d`, `1W`, `1M`).
- `1h` conservé comme alias de `60m` ; `1w` comme alias de `1W` (majuscule obligatoire).
- Suppression de `3m` et `8h` : intervalles absents de l'API MEXC Spot.
- Correction de `KLINE_LIMIT` : valeur corrigée de 1000 à **500** (défaut et maximum réels de l'API).
- Mise à jour de `INTERVAL_MAP`, `INTERVAL_SEC`, `validate_interval` et du prompt interactif en conséquence.

---

### 0-1-0 — 2026-05-17

Version initiale.

- Téléchargement OHLCV MEXC Spot vers CSV AmiBroker
- Sélection interactive : Top 5 USDT, symbole manuel, ou TOUS les symboles USDT
- Intervalles : `1m`, `3m`, `5m`, `15m`, `30m`, `1h`, `4h`, `1d`, `1w`, `1M`
- Plage de dates saisie interactivement, défaut hier→aujourd'hui UTC
- Pagination automatique (max 1000 bougies/appel)
- Reprise intra-symbole depuis la dernière bougie du CSV existant
- Reprise par symbole (mode ALL, ordre alphabétique)
- Mode concat : un seul CSV multi-tickers (mode ALL uniquement)
- Barres de progression globale et par symbole
- Retry HTTP avec backoff, gestion rate limit 429
- Suppression automatique des JSONL temporaires
- Clé API publique MEXC définie comme constante `MEXC_API_KEY` dans le script
- Aucune dépendance externe (stdlib Python uniquement)
