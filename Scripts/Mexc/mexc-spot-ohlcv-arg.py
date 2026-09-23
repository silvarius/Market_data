#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MEXC Spot → OHLCV → CSV AmiBroker (pilotable par arguments CLI)
- Top 5 USDT par volume 24h + option TOUS (défaut)
- Mode ALL: possibilité "concat" (un seul CSV multi-tickers) ou fichiers séparés
- Reprise intra-symbole: reprend à la minute suivant la dernière bougie existante
  (dans le CSV du symbole ou dans le CSV concat)
- Barre de progression GLOBALE (sur tout le batch)
- Suppression automatique des JSONL (logs bruts) après chaque symbole
- Dates par défaut (UTC) : hier 00:00:00 → aujourd'hui 00:00:00 (borne exclusive)
- CSV AmiBroker: Ticker,Date,Time,Open,High,Low,Close,Volume
  Date=YYYY/MM/DD, Time=HH:MM:SS
- Aucune authentification requise : endpoints de marché publics (pas de clé API)

Endpoints utilisés:
  Klines  : GET https://api.mexc.com/api/v3/klines
  Tickers : GET https://api.mexc.com/api/v3/ticker/24hr
  Interval: 1m,5m,15m,30m,60m,4h,1d,1W,1M (valeurs officielles MEXC)
            Saisie simplifiée acceptée: 1h (=60m), 1w (=1W)
"""

import sys
import time
import csv
import json
import os
import argparse
from pathlib import Path
from datetime import datetime, timezone, timedelta
from urllib.parse import urlencode
import urllib.request

VERSION = "0-1-0"

BASE_URL   = "https://api.mexc.com"
KLINE_API  = f"{BASE_URL}/api/v3/klines"
TICKER_API = f"{BASE_URL}/api/v3/ticker/24hr"

DEF_SLEEP  = 0.30   # délai standard entre appels (MEXC: 300 req/10s IP)
ERR_SLEEP  = 2.00   # délai en cas d'erreur transitoire
KLINE_LIMIT = 500   # max par appel MEXC (défaut et maximum = 500)

# Correspondance intervalle humain -> chaine MEXC officielle
# Valeurs acceptees par l'API: 1m,5m,15m,30m,60m,4h,1d,1W,1M
# Ref: https://www.mexc.com/api-docs/spot-v3/public-api-definitions#kline-interval
INTERVAL_MAP = {
    "1m":  "1m",
    "5m":  "5m",
    "15m": "15m",
    "30m": "30m",
    "60m": "60m", "1h": "60m",
    "4h":  "4h",
    "1d":  "1d",
    "1W":  "1W",  "1w": "1W",
    "1M":  "1M",
}
# Duree en secondes de chaque intervalle (pour la pagination)
INTERVAL_SEC = {
    "1m":  60,
    "5m":  300,
    "15m": 900,
    "30m": 1800,
    "60m": 3600,
    "4h":  14400,
    "1d":  86400,
    "1W":  604800,
    "1M":  2592000,
}

# ============ Utils généraux ============

def parse_user_datetime(s: str) -> datetime:
    s = s.strip()
    dt = datetime.fromisoformat(s.replace("T", " "))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)

def to_unix_ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)

def to_unix_sec(dt: datetime) -> int:
    return int(dt.timestamp())

def ms_to_ab_date_time(ms: int):
    dt = datetime.fromtimestamp(ms / 1000, tz=timezone.utc)
    return dt.strftime("%Y/%m/%d"), dt.strftime("%H:%M:%S")

def parse_ab_date_time_to_ms(date_str: str, time_str: str) -> int:
    dt = datetime.strptime(date_str + " " + time_str, "%Y/%m/%d %H:%M:%S")
    dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)

def ensure_paths(out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)

def delete_file(path: Path):
    try:
        if path.exists():
            os.remove(path)
    except Exception as e:
        print(f"Impossible de supprimer {path}: {e}")

def as_float(x, default=0.0):
    try:
        return float(x)
    except Exception:
        return default

def http_get_json(url: str, max_retries: int = 5, backoff_sec: float = 0.8):
    last_err = None
    for attempt in range(1, max_retries + 1):
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            last_err = e
            err_str = str(e)
            # Erreurs 4xx non-transitoires (sauf 429/418) : inutile de retrier
            if any(code in err_str for code in ("400", "401", "403", "404")):
                raise RuntimeError(f"Erreur non-retriable ({err_str[:80]}): {url}")
            # Gestion 429 / 418 : rate limit, attendre plus longtemps
            if "429" in err_str or "418" in err_str:
                wait = max(backoff_sec * attempt, 10.0)
                print(f"\n[Rate limit] attente {wait:.0f}s...")
                time.sleep(wait)
            else:
                time.sleep(backoff_sec * attempt)
    raise RuntimeError(f"GET failed after {max_retries} attempts: {url}\nLast error: {last_err}")

# ============ Barres de progression ============

def progress_bar(current: int, total: int, prefix: str = "", width: int = 55):
    if total <= 0:
        pct = 0.0
    else:
        pct = max(0.0, min(1.0, current / total))
    filled = int(width * pct)
    bar = "█" * filled + "░" * (width - filled)
    sys.stdout.write(f"\r{prefix} [{bar}] {pct * 100:6.2f}%")
    sys.stdout.flush()

class GlobalProgress:
    def __init__(self, total_ms: int, prefix="Progression globale"):
        self.total  = max(0, int(total_ms))
        self.cur    = 0
        self.prefix = prefix
        progress_bar(self.cur, self.total, prefix=self.prefix)

    def bump(self, delta_ms: int):
        if delta_ms is None:
            return
        self.cur = min(self.total, self.cur + max(0, int(delta_ms)))
        progress_bar(self.cur, self.total, prefix=self.prefix)

    def done(self):
        self.cur = self.total
        progress_bar(self.cur, self.total, prefix=self.prefix)
        sys.stdout.write("\n")

class SymbolProgress:
    def __init__(self, total_steps: int, prefix: str = "Symbole"):
        self.total  = max(0, int(total_steps))
        self.cur    = 0
        self.prefix = prefix

    def update_to(self, current_steps: int):
        self.cur = max(0, min(int(current_steps), self.total))
        progress_bar(self.cur, self.total, prefix=self.prefix)

    def end(self):
        self.cur = self.total
        progress_bar(self.cur, self.total, prefix=self.prefix)
        sys.stdout.write("\n")
        sys.stdout.flush()

# ============ Validation intervalle ============

def validate_interval(raw: str) -> tuple[str, int]:
    """
    Retourne (mexc_interval_str, interval_sec).
    Accepte: 1m, 5m, 15m, 30m, 60m, 1h (=60m), 4h, 1d, 1w/1W, 1M
    Ref: https://www.mexc.com/api-docs/spot-v3/public-api-definitions#kline-interval
    """
    s = raw.strip()
    mexc_str = INTERVAL_MAP.get(s) or INTERVAL_MAP.get(s.lower()) or INTERVAL_MAP.get(s.upper())
    if mexc_str is None:
        raise ValueError(
            f"Intervalle '{raw}' non reconnu.\n"
            "Valeurs valides : 1m, 5m, 15m, 30m, 60m, 1h (=60m), 4h, 1d, 1W, 1M"
        )
    sec = INTERVAL_SEC[mexc_str]
    return mexc_str, sec

# ============ Gestion fichiers sortie ============

def csv_paths(out_dir: Path, ticker: str, interval_tag: str,
              start_dt: datetime, end_dt: datetime):
    stem = (
        f"mexc_spot_{ticker}_{interval_tag}_"
        f"{start_dt.isoformat().replace(':', '-')}_to_"
        f"{end_dt.isoformat().replace(':', '-')}"
    )
    raw_path = out_dir / f"{stem}.jsonl"
    csv_path = out_dir / f"{stem}.csv"
    return raw_path, csv_path

def open_outputs_with_resume(out_dir: Path, ticker: str, interval_tag: str,
                             start_dt: datetime, end_dt: datetime):
    """
    Fichiers séparés par symbole.
    Retourne: raw_f, csv_f, writer, raw_path, csv_path, resume_from_ms
    """
    raw_path, csv_path = csv_paths(out_dir, ticker, interval_tag, start_dt, end_dt)
    raw_f = raw_path.open("a", encoding="utf-8")

    resume_from_ms = None
    new_csv = not csv_path.exists()
    csv_f = csv_path.open("a", newline="", encoding="utf-8")
    w = csv.writer(csv_f)
    if new_csv:
        w.writerow(["Ticker", "Date", "Time", "Open", "High", "Low", "Close", "Volume"])
    else:
        try:
            last_line = None
            with csv_path.open("r", newline="", encoding="utf-8") as fchk:
                reader = csv.reader(fchk)
                header_skipped = False
                for row in reader:
                    if not header_skipped:
                        header_skipped = True
                        continue
                    if row and len(row) >= 3:
                        last_line = row
            if last_line:
                resume_from_ms = parse_ab_date_time_to_ms(last_line[1], last_line[2]) + 60_000
        except Exception:
            resume_from_ms = None

    return raw_f, csv_f, w, raw_path, csv_path, resume_from_ms

# ============ Concat helpers ============

def make_concat_csv(out_dir: Path, interval_tag: str,
                    start_dt: datetime, end_dt: datetime):
    stem = (
        f"mexc_spot_ALL_{interval_tag}_"
        f"{start_dt.isoformat().replace(':', '-')}_to_"
        f"{end_dt.isoformat().replace(':', '-')}"
    )
    csv_path = out_dir / f"{stem}.csv"
    created = not csv_path.exists()
    f = csv_path.open("a", newline="", encoding="utf-8")
    w = csv.writer(f)
    if created:
        w.writerow(["Ticker", "Date", "Time", "Open", "High", "Low", "Close", "Volume"])
    return f, w, csv_path

def find_last_ms_in_concat(csv_path: Path, ticker: str) -> int | None:
    if not csv_path.exists():
        return None
    last_ms = None
    try:
        with csv_path.open("r", newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            header_skipped = False
            for row in reader:
                if not header_skipped:
                    header_skipped = True
                    continue
                if not row or len(row) < 3:
                    continue
                if row[0].upper() != ticker.upper():
                    continue
                last_ms = parse_ab_date_time_to_ms(row[1], row[2])
    except Exception:
        return None
    return last_ms

def compute_resume_start_ms(symbol: str, interval_tag: str,
                             start_dt: datetime, end_dt: datetime,
                             out_dir: Path, concat_mode: bool,
                             concat_csv_path: Path | None) -> int:
    req_start_ms = to_unix_ms(start_dt)
    if concat_mode:
        last_ms = find_last_ms_in_concat(concat_csv_path, symbol) if concat_csv_path else None
        return max(req_start_ms, (last_ms + 60_000) if last_ms is not None else req_start_ms)
    else:
        _, csv_path = csv_paths(out_dir, symbol, interval_tag, start_dt, end_dt)
        if csv_path.exists():
            try:
                last_line = None
                with csv_path.open("r", newline="", encoding="utf-8") as f:
                    reader = csv.reader(f)
                    header_skipped = False
                    for row in reader:
                        if not header_skipped:
                            header_skipped = True
                            continue
                        if row and len(row) >= 3:
                            last_line = row
                if last_line:
                    last_ms = parse_ab_date_time_to_ms(last_line[1], last_line[2])
                    return max(req_start_ms, last_ms + 60_000)
            except Exception:
                pass
        return req_start_ms

# ============ Liste des symboles USDT ============

def fetch_all_usdt_symbols() -> list[str]:
    """Retourne tous les symboles USDT actifs triés alphabétiquement."""
    data = http_get_json(TICKER_API, max_retries=5)
    syms = sorted({
        str(t.get("symbol", "")).upper()
        for t in data
        if str(t.get("symbol", "")).upper().endswith("USDT")
    })
    return syms

# ============ Téléchargement klines ============

def run_spot_single(symbol: str, mexc_interval: str, interval_sec: int,
                    start_dt: datetime, end_dt: datetime,
                    out_dir: Path,
                    concat_mode: bool,
                    concat_writer=None, concat_csv_path: Path | None = None,
                    gprogress: GlobalProgress | None = None):
    """
    Télécharge les klines d'un symbole MEXC spot.
    - concat_mode=False : fichiers séparés + reprise via CSV dédié
    - concat_mode=True  : écrit dans concat_writer; reprise via CSV concat
    - gprogress: progression globale (en ms couverts)
    """
    interval_tag = mexc_interval  # ex: "1m", "15m", "1d"
    req_start_ms = to_unix_ms(start_dt)
    end_ms       = to_unix_ms(end_dt)

    # Avertissement si startTime dépasse la profondeur historique de 30 jours
    MEXC_MAX_HISTORY_MS = 30 * 24 * 3600 * 1000
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    limit_dt = datetime.fromtimestamp((now_ms - MEXC_MAX_HISTORY_MS) / 1000, tz=timezone.utc)
    if req_start_ms < now_ms - MEXC_MAX_HISTORY_MS:
        print(f"  [{symbol}] Info: startTime antérieur à 30 jours "
              f"(limite estimée: {limit_dt.strftime('%Y-%m-%d %H:%M')} UTC). "
              f"Les données démarreront à la première bougie disponible.")

    # Reprise
    start_ms = compute_resume_start_ms(
        symbol, interval_tag, start_dt, end_dt, out_dir, concat_mode, concat_csv_path
    )
    remaining_ms = max(0, end_ms - start_ms)
    if remaining_ms <= 0:
        print(f"  {symbol}: déjà à jour, rien à faire.")
        return 0

    sprogress = SymbolProgress(total_steps=remaining_ms, prefix=f"  {symbol}")
    progressed = 0

    # Ouverture sorties
    if not concat_mode:
        raw_f, csv_f, writer, raw_path, csv_path, _ = open_outputs_with_resume(
            out_dir, symbol, interval_tag, start_dt, end_dt
        )
    else:
        if concat_writer is None or concat_csv_path is None:
            raise RuntimeError("concat_writer/csv_path manquants en mode concat.")
        raw_path, _ = csv_paths(out_dir, symbol, interval_tag, start_dt, end_dt)
        raw_f  = raw_path.open("a", encoding="utf-8")
        csv_f  = None
        writer = concat_writer
        csv_path = concat_csv_path

    cur_from_ms = start_ms
    total_candles = 0

    try:
        while True:
            if cur_from_ms >= end_ms:
                break

            # Fenêtre de pagination: KLINE_LIMIT bougies maximum
            window_end_ms = min(end_ms, cur_from_ms + interval_sec * KLINE_LIMIT * 1000)

            params = {
                "symbol":    symbol,
                "interval":  mexc_interval,
                "startTime": cur_from_ms,
                "endTime":   window_end_ms,
                "limit":     KLINE_LIMIT,
            }
            url = f"{KLINE_API}?{urlencode(params)}"

            try:
                data = http_get_json(url, max_retries=5)
            except Exception as e:
                print(f"\n  [{symbol}] Erreur HTTP: {e}")
                time.sleep(ERR_SLEEP)
                continue

            raw_f.write(json.dumps(data, ensure_ascii=False) + "\n")

            # Réponse MEXC: liste de listes
            # [open_time_ms, open, high, low, close, volume, close_time_ms,
            #  quote_volume, trades, taker_buy_base, taker_buy_quote, ignore]
            if not isinstance(data, list):
                # Erreur API (ex: {"code": -1121, "msg": "Invalid symbol."})
                print(f"\n  [{symbol}] Réponse inattendue: {data}")
                break

            candles = data
            wrote_any = False
            last_open_ms = cur_from_ms

            for c in candles:
                open_ms = int(c[0])
                if open_ms < req_start_ms:
                    continue
                if open_ms >= end_ms:
                    break
                d, t = ms_to_ab_date_time(open_ms)
                writer.writerow([symbol, d, t, c[1], c[2], c[3], c[4], c[5]])
                total_candles += 1
                wrote_any = True
                last_open_ms = open_ms

            # Avancer le curseur
            prev_from_ms = cur_from_ms
            if candles:
                # Prochain départ = dernière open_time + 1 intervalle
                next_ms = int(candles[-1][0]) + interval_sec * 1000
            else:
                # Aucune bougie dans cette fenêtre: sauter la fenêtre
                next_ms = window_end_ms

            cur_from_ms = max(next_ms, cur_from_ms + interval_sec * 1000)

            step_advance = min(end_ms, cur_from_ms) - min(end_ms, prev_from_ms)
            if step_advance > 0:
                progressed += step_advance
                sprogress.update_to(progressed)

            # Sortie anticipée si aucune donnée et fenêtre couvre tout
            if not wrote_any and cur_from_ms >= end_ms:
                break

            time.sleep(DEF_SLEEP)

    finally:
        raw_f.close()
        if csv_f:
            csv_f.close()
        try:
            sprogress.end()
        except Exception:
            pass
        if gprogress and progressed:
            gprogress.bump(progressed)
            sys.stdout.write("\n")
            sys.stdout.flush()
        delete_file(raw_path)

    print(f"  Terminé ({symbol}). Bougies écrites: {total_candles}")
    return total_candles

# ============ CLI ============

def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="MEXC Spot → OHLCV → CSV AmiBroker (pilotable par arguments CLI)"
    )
    parser.add_argument("--out-dir", default=".",
                         help="Dossier de sortie (défaut: répertoire courant)")

    sym_group = parser.add_mutually_exclusive_group()
    sym_group.add_argument("--symbol", metavar="SYMBOL",
                            help="Symbole unique à télécharger (ex: BTCUSDT)")
    sym_group.add_argument("--all", action="store_true",
                            help="Tous les symboles USDT (défaut si --symbol absent)")

    parser.add_argument("--interval", default="1m",
                         help="Intervalle: 1m,5m,15m,30m,60m,1h(=60m),4h,1d,1W,1M (défaut: 1m)")
    parser.add_argument("--start", default=None,
                         help="Début UTC, ex '2026-09-22 00:00:00+00:00' (défaut: hier 00:00:00 UTC)")
    parser.add_argument("--end", default=None,
                         help="Fin UTC, borne exclusive (défaut: aujourd'hui 00:00:00 UTC)")
    parser.add_argument("--resume-from", metavar="SYMBOL", default=None,
                         help="Reprendre à partir de ce symbole, ordre alphabétique (mode --all uniquement)")

    concat_group = parser.add_mutually_exclusive_group()
    concat_group.add_argument("--concat", dest="concat", action="store_true",
                               help="Un seul CSV multi-tickers (défaut, mode --all uniquement)")
    concat_group.add_argument("--no-concat", dest="concat", action="store_false",
                               help="Fichiers CSV séparés par symbole (mode --all uniquement)")
    parser.set_defaults(concat=True)

    return parser

# ============ MAIN ============

def main():
    print(f"=== MEXC Spot → AmiBroker CSV (v{VERSION}) ===\n")

    parser = build_arg_parser()
    args = parser.parse_args()

    if args.resume_from and args.symbol:
        parser.error("--resume-from n'est utilisable qu'en mode --all (pas avec --symbol).")

    # --- Dossier de sortie ---
    out_dir = Path(args.out_dir)
    ensure_paths(out_dir)

    # --- Sélection symbole(s) ---
    if args.symbol:
        symbol_list  = [args.symbol.strip().upper()]
        symbols_mode = "ONE"
    else:
        symbols_mode = "ALL"
        symbol_list  = []

    # --- Intervalle ---
    try:
        mexc_interval, interval_sec = validate_interval(args.interval)
    except ValueError as e:
        print(e); return 1

    # --- Plage de dates ---
    today_utc = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    y0 = today_utc - timedelta(days=1)
    default_start_str = y0.strftime("%Y-%m-%d 00:00:00+00:00")
    default_end_str   = today_utc.strftime("%Y-%m-%d 00:00:00+00:00")

    start_str = args.start or default_start_str
    end_str   = args.end or default_end_str

    try:
        start_dt = parse_user_datetime(start_str)
        end_dt   = parse_user_datetime(end_str)
    except Exception as e:
        print("Date invalide :", e); return 1
    if end_dt <= start_dt:
        print("Erreur : End doit être > Start."); return 1

    # --- Mode ALL: charger la liste + options ---
    concat_mode = False
    concat_f = concat_writer = concat_csv_path = None

    if symbols_mode == "ALL":
        try:
            print("\nRécupération de la liste des symboles USDT actifs...")
            full_list = fetch_all_usdt_symbols()
            if not full_list:
                print("Aucun symbole USDT trouvé."); return 1
            print(f"{len(full_list)} symboles USDT trouvés (ordre alphabétique).")

            # Reprise par symbole
            resume_from_sym = (args.resume_from or "").strip().upper()
            if resume_from_sym:
                if resume_from_sym in full_list:
                    start_idx = full_list.index(resume_from_sym)
                    symbol_list = full_list[start_idx:]
                    print(f"Reprise à partir de {resume_from_sym} ({len(symbol_list)} symboles restants).")
                else:
                    print(f"{resume_from_sym} introuvable, démarrage au début.")
                    symbol_list = full_list
            else:
                symbol_list = full_list

            # Mode concat
            if args.concat:
                concat_mode = True
                concat_f, concat_writer, concat_csv_path = make_concat_csv(
                    out_dir, mexc_interval, start_dt, end_dt
                )

        except KeyboardInterrupt:
            print("\nInterruption."); return 130
        except Exception as e:
            print("Erreur listing symboles :", e); return 1

    # --- Calcul progression globale (en ms) ---
    end_ms = to_unix_ms(end_dt)
    total_ms = 0
    for sym in symbol_list:
        eff_start_ms = compute_resume_start_ms(
            sym, mexc_interval, start_dt, end_dt, out_dir, concat_mode, concat_csv_path
        )
        total_ms += max(0, end_ms - eff_start_ms)
    gprog = GlobalProgress(total_ms, prefix="Progression globale")

    # --- Téléchargements ---
    try:
        if concat_mode:
            try:
                for i, sym in enumerate(symbol_list, 1):
                    print(f"\n[{i}/{len(symbol_list)}] {sym}")
                    run_spot_single(
                        sym, mexc_interval, interval_sec, start_dt, end_dt, out_dir,
                        concat_mode=True,
                        concat_writer=concat_writer, concat_csv_path=concat_csv_path,
                        gprogress=gprog,
                    )
                    time.sleep(0.4)
            finally:
                if concat_f:
                    concat_f.close()
        else:
            for i, sym in enumerate(symbol_list, 1):
                print(f"\n[{i}/{len(symbol_list)}] {sym}")
                run_spot_single(
                    sym, mexc_interval, interval_sec, start_dt, end_dt, out_dir,
                    concat_mode=False,
                    gprogress=gprog,
                )
                time.sleep(0.4)

    except KeyboardInterrupt:
        print("\nInterruption par l'utilisateur."); return 130

    gprog.done()
    print("\n=== Terminé. ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
