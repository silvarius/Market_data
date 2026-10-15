#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hyperliquid (HL) Perps → OHLCV → CSV AmiBroker (pilotable par arguments CLI)
- Top 5 perps par OI (via meta) + option 6=TOUS (défaut)
- Mode ALL: possibilité "concat" (un seul CSV multi-tickers) ou fichiers séparés
- Reprise:
    * Par symbole: reprendre à partir d'un symbole (ordre alphabétique)
    * Intra-symbole: reprend à la minute suivant la dernière bougie existante
      (dans le CSV du symbole ou dans le CSV concat)
- Barre de progression GLOBALE (sur tout le batch)
- Suppression automatique des JSONL (logs bruts) après chaque symbole
- Dates par défaut (UTC) : hier 00:00:00 → aujourd'hui 00:00:00 (borne exclusive)
- CSV AmiBroker: Ticker,Date,Time,Open,High,Low,Close,Volume
  Date=YYYY/MM/DD, Time=HH:MM:SS

API Hyperliquid:
  Endpoint unique : POST https://api.hyperliquid.xyz/info
  Aucune authentification requise (lecture seule publique)
  Limite : 5 000 bougies par réponse
  Intervalles : 1m,3m,5m,15m,30m,1h,2h,4h,8h,12h,1d,3d,1w,1M
"""

import sys
import time
import csv
import json
import os
import argparse
from pathlib import Path
from datetime import datetime, timezone, timedelta
import urllib.request

VERSION = "0-1-0"

HL_API     = "https://api.hyperliquid.xyz/info"
DEF_SLEEP  = 0.25   # délai standard entre appels (suffisant pour budget 1200 wu/min)
ERR_SLEEP  = 2.00   # délai en cas d'erreur transitoire
HL_LIMIT   = 5000   # max bougies par réponse HL

# Intervalles supportés par HL et leur durée en ms
INTERVAL_MS: dict[str, int] = {
    "1m":  60_000,
    "3m":  180_000,
    "5m":  300_000,
    "15m": 900_000,
    "30m": 1_800_000,
    "1h":  3_600_000,
    "2h":  7_200_000,
    "4h":  14_400_000,
    "8h":  28_800_000,
    "12h": 43_200_000,
    "1d":  86_400_000,
    "3d":  259_200_000,
    "1w":  604_800_000,
    "1M":  2_592_000_000,
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

def ms_to_ab_date_time_from_ms(ms: int):
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

def progress_bar(current: int, total: int, prefix: str = "", width: int = 60):
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

# ============ HTTP POST ============

def http_post_json(url: str, payload: dict, max_retries: int = 5, backoff_sec: float = 0.8):
    body = json.dumps(payload).encode("utf-8")
    last_err = None
    for attempt in range(1, max_retries + 1):
        try:
            req = urllib.request.Request(
                url, data=body,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            last_err = e
            err_str = str(e)
            # Erreurs 4xx non-transitoires : pas de retry
            if any(code in err_str for code in ("400", "401", "403", "404")):
                raise RuntimeError(f"Erreur non-retriable ({err_str[:80]}): {url}")
            # Rate limit : attente prolongée
            if "429" in err_str or "418" in err_str:
                wait = max(backoff_sec * attempt, 10.0)
                print(f"\n[Rate limit] attente {wait:.0f}s...")
                time.sleep(wait)
            else:
                time.sleep(backoff_sec * attempt)
    raise RuntimeError(f"POST failed after {max_retries} attempts: {url}\nLast error: {last_err}")

# ============ Validation intervalle ============

def validate_interval(res: str) -> tuple[str, int]:
    """
    Retourne (interval_str, interval_ms).
    Intervalles valides : 1m,3m,5m,15m,30m,1h,2h,4h,8h,12h,1d,3d,1w,1M
    """
    s = res.strip()
    if s in INTERVAL_MS:
        return s, INTERVAL_MS[s]
    raise ValueError(
        f"Intervalle '{res}' non reconnu.\n"
        "Valeurs valides : 1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h, 8h, 12h, 1d, 3d, 1w, 1M"
    )

# ============ API HL — symboles ============

def fetch_hl_meta() -> dict:
    """Retourne la réponse complète de l'endpoint meta."""
    return http_post_json(HL_API, {"type": "meta"})

def fetch_hl_meta_and_asset_ctxs() -> tuple[list, list]:
    """
    Retourne (universe, assetCtxs) depuis metaAndAssetCtxs.
    universe : liste de dicts {name, szDecimals, ...}
    assetCtxs: liste de dicts {dayNtlVlm, openInterest, ...} — même ordre que universe
    """
    data = http_post_json(HL_API, {"type": "metaAndAssetCtxs"})
    # réponse = [meta_dict, [assetCtx, ...]]
    if isinstance(data, list) and len(data) == 2:
        meta, ctxs = data
        return meta.get("universe", []), ctxs
    # fallback : on tente juste meta
    meta = fetch_hl_meta()
    return meta.get("universe", []), []

def fetch_hl_perps_list() -> list[str]:
    """Retourne la liste triée alphabétiquement des perps HL disponibles."""
    try:
        universe, _ = fetch_hl_meta_and_asset_ctxs()
    except Exception:
        meta = fetch_hl_meta()
        universe = meta.get("universe", [])
    return sorted(d["name"] for d in universe if "name" in d)

# ============ Gestion fichiers sortie ============

def csv_paths(out_dir: Path, market_tag: str, ticker: str, frame_tag: str,
              start_dt: datetime, end_dt: datetime):
    stem = (
        f"{market_tag}_{ticker}_{frame_tag}_"
        f"{start_dt.isoformat().replace(':', '-')}_to_"
        f"{end_dt.isoformat().replace(':', '-')}"
    )
    raw_path = out_dir / f"{stem}.jsonl"
    csv_path = out_dir / f"{stem}.csv"
    return raw_path, csv_path

def open_outputs_with_resume(out_dir: Path, market_tag: str, ticker: str,
                              frame_tag: str, start_dt: datetime, end_dt: datetime):
    """
    Fichiers séparés par symbole.
    Retourne: raw_f, csv_f, writer, raw_path, csv_path, resume_from_ms
    """
    raw_path, csv_path = csv_paths(out_dir, market_tag, ticker, frame_tag, start_dt, end_dt)
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

def make_concat_csv(out_dir: Path, market_tag: str, frame_tag: str,
                    start_dt: datetime, end_dt: datetime):
    stem = (
        f"{market_tag}_{frame_tag}_"
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

def compute_symbol_resume_start(symbol: str, interval: str,
                                 start_dt: datetime, end_dt: datetime,
                                 out_dir: Path, concat_mode: bool,
                                 concat_csv_path: Path | None) -> int:
    """Calcule le start_ms effectif pour ce symbole (gestion reprise)."""
    req_start_ms = to_unix_ms(start_dt)
    if concat_mode:
        last_ms = find_last_ms_in_concat(concat_csv_path, symbol) if concat_csv_path else None
        return max(req_start_ms, (last_ms + 60_000) if last_ms is not None else req_start_ms)
    else:
        _, csv_path = csv_paths(out_dir, "HL", symbol, interval, start_dt, end_dt)
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

# ============ Téléchargement HL ============

def run_hl_single(symbol: str, interval: str, interval_ms: int,
                  start_dt: datetime, end_dt: datetime,
                  out_dir: Path,
                  concat_mode: bool,
                  concat_writer=None, concat_csv_path: Path | None = None,
                  gprogress: GlobalProgress | None = None) -> int:
    """
    Télécharge les bougies d'un symbole Hyperliquid.
    - concat_mode=False : fichiers séparés + reprise via CSV dédié
    - concat_mode=True  : écrit dans concat_writer; reprise via CSV concat
    - gprogress: mise à jour de la progression globale (en ms couvertes)
    """
    req_start_ms = to_unix_ms(start_dt)
    end_ms       = to_unix_ms(end_dt)

    # Reprise
    start_ms = compute_symbol_resume_start(
        symbol, interval, start_dt, end_dt, out_dir, concat_mode, concat_csv_path
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
            out_dir, "HL", symbol, interval, start_dt, end_dt
        )
    else:
        if concat_writer is None or concat_csv_path is None:
            raise RuntimeError("concat_writer/csv_path manquants en mode concat.")
        raw_path, _ = csv_paths(out_dir, "HL", symbol, interval, start_dt, end_dt)
        raw_f  = raw_path.open("a", encoding="utf-8")
        csv_f  = None
        writer = concat_writer
        csv_path = concat_csv_path

    print(f"\n  [{symbol}] → {csv_path}")

    cur_from_ms   = start_ms
    total_candles = 0

    try:
        while True:
            if cur_from_ms >= end_ms:
                break

            payload = {
                "type": "candleSnapshot",
                "req": {
                    "coin":      symbol,
                    "interval":  interval,
                    "startTime": cur_from_ms,
                    "endTime":   end_ms,
                }
            }

            try:
                candles = http_post_json(HL_API, payload, max_retries=5)
            except Exception as e:
                print(f"\n  [{symbol}] Erreur HTTP: {e}")
                time.sleep(ERR_SLEEP)
                continue

            raw_f.write(json.dumps(candles, ensure_ascii=False) + "\n")

            # Réponse vide → fin de données
            if not isinstance(candles, list) or len(candles) == 0:
                break

            wrote_any   = False
            prev_from_ms = cur_from_ms
            last_t_ms   = cur_from_ms

            for c in candles:
                t_ms = int(c["t"])
                if t_ms < req_start_ms:
                    continue
                if t_ms >= end_ms:
                    break
                d, t = ms_to_ab_date_time_from_ms(t_ms)
                writer.writerow([symbol, d, t, c["o"], c["h"], c["l"], c["c"], c["v"]])
                total_candles += 1
                wrote_any  = True
                last_t_ms  = t_ms

            # Avancer le curseur
            cur_from_ms = last_t_ms + interval_ms

            step_advance = min(end_ms, cur_from_ms) - min(end_ms, prev_from_ms)
            if step_advance > 0:
                progressed += step_advance
                sprogress.update_to(progressed)

            # Fin naturelle : moins de HL_LIMIT bougies retournées
            if len(candles) < HL_LIMIT:
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
        description="Hyperliquid Perps → OHLCV → CSV AmiBroker (pilotable par arguments CLI)"
    )
    parser.add_argument("--out-dir", default=".",
                         help="Dossier de sortie (défaut: répertoire courant)")

    sym_group = parser.add_mutually_exclusive_group()
    sym_group.add_argument("--symbol", metavar="SYMBOL",
                            help="Symbole unique à télécharger (ex: BTC)")
    sym_group.add_argument("--all", action="store_true",
                            help="Tous les perps HL (défaut si --symbol absent)")

    parser.add_argument("--interval", default="1m",
                         help="Intervalle: 1m,3m,5m,15m,30m,1h,2h,4h,8h,12h,1d,3d,1w,1M (défaut: 1m)")
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
    print(f"=== Hyperliquid Perps → AmiBroker CSV (v{VERSION}) ===\n")

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
        interval, interval_ms = validate_interval(args.interval)
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
            print("\nRécupération de la liste des perps HL...")
            full_list = fetch_hl_perps_list()
            if not full_list:
                print("Aucun symbole trouvé."); return 1
            print(f"{len(full_list)} perps trouvés (ordre alphabétique).")

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
                    out_dir, "hyperliquid_futures", interval, start_dt, end_dt
                )

        except KeyboardInterrupt:
            print("\nInterruption."); return 130
        except Exception as e:
            print("Erreur listing symboles :", e); return 1

    # --- Calcul progression globale (en ms) ---
    end_ms   = to_unix_ms(end_dt)
    total_ms = 0
    for sym in symbol_list:
        eff_start_ms = compute_symbol_resume_start(
            sym, interval, start_dt, end_dt, out_dir, concat_mode, concat_csv_path
        )
        total_ms += max(0, end_ms - eff_start_ms)
    gprog = GlobalProgress(total_ms, prefix="Progression globale")

    # --- Téléchargements ---
    try:
        if concat_mode:
            try:
                for i, sym in enumerate(symbol_list, 1):
                    print(f"\n[{i}/{len(symbol_list)}] {sym}")
                    run_hl_single(
                        sym, interval, interval_ms, start_dt, end_dt, out_dir,
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
                run_hl_single(
                    sym, interval, interval_ms, start_dt, end_dt, out_dir,
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
