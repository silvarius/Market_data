#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Kraken Futures → OHLC/OLHCV → CSV AmiBroker (interactif)
- PF (linéaire) / PI (inverse) avec Top 5 par liquidité (USD) et option 6=TOUS (défaut)
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
"""

import sys
import time
import csv
import json
import os
from pathlib import Path
from datetime import datetime, timezone, timedelta
from urllib.parse import urlencode
import urllib.request

VERSION = "0-1-0"

FUT_API    = "https://futures.kraken.com/api/charts/v1/trade"
TICK_API   = "https://futures.kraken.com/derivatives/api/v3/tickers"
INSTR_API  = "https://futures.kraken.com/derivatives/api/v3/instruments"

DEF_SLEEP  = 0.25  # délai standard entre appels
ERR_SLEEP  = 2.00  # délai en cas d’erreur transitoire

# ============ Utils généraux ============

def parse_user_datetime(s: str) -> datetime:
    s = s.strip()
    dt = datetime.fromisoformat(s.replace("T", " "))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)

def to_unix_seconds(dt: datetime) -> int:
    return int(dt.timestamp())

def http_get_json(url: str, max_retries: int = 5, backoff_sec: float = 0.8):
    last_err = None
    for attempt in range(1, max_retries + 1):
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            last_err = e
            time.sleep(backoff_sec * attempt)
    raise RuntimeError(f"GET failed after {max_retries} attempts: {url}\nLast error: {last_err}")

def ms_to_ab_date_time_from_ms(ms: int):
    dt = datetime.fromtimestamp(ms/1000, tz=timezone.utc)
    return dt.strftime("%Y/%m/%d"), dt.strftime("%H:%M:%S")

def ms_to_ab_date_time_from_sec(sec: int):
    dt = datetime.fromtimestamp(sec, tz=timezone.utc)
    return dt.strftime("%Y/%m/%d"), dt.strftime("%H:%M:%S")

def parse_ab_date_time_to_sec(date_str: str, time_str: str) -> int:
    # Date=YYYY/MM/DD, Time=HH:MM:SS
    dt = datetime.strptime(date_str + " " + time_str, "%Y/%m/%d %H:%M:%S")
    dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp())

def ensure_paths(out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)

def delete_file(path: Path):
    try:
        if path.exists():
            os.remove(path)
    except Exception as e:
        print(f"Impossible de supprimer {path}: {e}")

def fget(d, *names, default=None):
    for n in names:
        if n in d and d[n] is not None:
            return d[n]
    return default

def as_float(x, default=0.0):
    try:
        return float(x)
    except Exception:
        return default

def progress_bar(current: int, total: int, prefix: str = "", width: int = 60):
    if total <= 0:
        pct = 0.0
    else:
        pct = max(0.0, min(1.0, current/total))
    filled = int(width*pct)
    bar = "█"*filled + "░"*(width - filled)
    sys.stdout.write(f"\r{prefix} [{bar}] {pct*100:6.2f}%")
    sys.stdout.flush()

class GlobalProgress:
    def __init__(self, total_seconds: int, prefix="Progression globale"):
        self.total = max(0, int(total_seconds))
        self.cur   = 0
        self.prefix = prefix
        progress_bar(self.cur, self.total, prefix=self.prefix)

    def bump(self, delta_seconds: int):
        if delta_seconds is None:
            return
        self.cur = min(self.total, self.cur + max(0, int(delta_seconds)))
        progress_bar(self.cur, self.total, prefix=self.prefix)

    def done(self):
        self.cur = self.total
        progress_bar(self.cur, self.total, prefix=self.prefix)
        sys.stdout.write("\n")


class SymbolProgress:
    """Barre de progression SEQUENTIELLE pour un symbole (sans ANSI)."""
    def __init__(self, total_steps: int, prefix: str = "Symbole"):
        self.total  = max(0, int(total_steps))
        self.cur    = 0
        self.prefix = prefix

    def update_to(self, current_steps: int):
        self.cur = max(0, min(int(current_steps), self.total))
        progress_bar(self.cur, self.total, prefix=self.prefix)

    def end(self):
        # finalize line and break to next line
        self.cur = self.total
        progress_bar(self.cur, self.total, prefix=self.prefix)
        sys.stdout.write("\n")
        sys.stdout.flush()
# ============ Gestion fichiers sortie ============

def csv_paths(out_dir: Path, market_tag: str, ticker: str, frame_tag: str,
              start_dt: datetime, end_dt: datetime):
    stem = f"{market_tag}_{ticker}_{frame_tag}_{start_dt.isoformat().replace(':','-')}_to_{end_dt.isoformat().replace(':','-')}"
    raw_path = out_dir / f"{stem}.jsonl"
    csv_path = out_dir / f"{stem}.csv"
    return raw_path, csv_path

def open_outputs_with_resume(out_dir: Path, market_tag: str, ticker: str, frame_tag: str,
                             start_dt: datetime, end_dt: datetime):
    """
    Fichiers séparés par symbole:
      - JSONL append
      - CSV append si existe (reprise), sinon écrit l'en-tête
    Retourne: raw_f, csv_f, writer, raw_path, csv_path, resume_from_sec
    """
    raw_path, csv_path = csv_paths(out_dir, market_tag, ticker, frame_tag, start_dt, end_dt)
    raw_f = raw_path.open("a", encoding="utf-8")

    resume_from_sec = None
    new_csv = not csv_path.exists()
    csv_f = csv_path.open("a", newline="", encoding="utf-8")
    w = csv.writer(csv_f)
    if new_csv:
        w.writerow(["Ticker","Date","Time","Open","High","Low","Close","Volume"])
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
                    resume_from_sec = parse_ab_date_time_to_sec(last_line[1], last_line[2]) + 60
        except Exception:
            resume_from_sec = None

    return raw_f, csv_f, w, raw_path, csv_path, resume_from_sec

# ============ Concat helpers ============

def make_concat_csv(out_dir: Path, market_tag: str, frame_tag: str, start_dt: datetime, end_dt: datetime):
    stem = f"{market_tag}_ALL_{frame_tag}_{start_dt.isoformat().replace(':','-')}_to_{end_dt.isoformat().replace(':','-')}"
    csv_path = out_dir / f"{stem}.csv"
    created = not csv_path.exists()
    f = csv_path.open("a", newline="", encoding="utf-8")
    w = csv.writer(f)
    if created:
        w.writerow(["Ticker","Date","Time","Open","High","Low","Close","Volume"])
    return f, w, csv_path

def find_last_timestamp_in_concat(csv_path: Path, ticker: str) -> int | None:
    if not csv_path.exists():
        return None
    last_sec = None
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
                last_sec = parse_ab_date_time_to_sec(row[1], row[2])
    except Exception:
        return None
    return last_sec

def compute_symbol_resume_start(symbol: str, resolution: str,
                                start_dt: datetime, end_dt: datetime,
                                out_dir: Path, concat_mode: bool,
                                concat_csv_path: Path | None):
    """Calcule le start_s effectif pour ce symbole en tenant compte de la reprise (concat ou fichier séparé)."""
    req_start_s = to_unix_seconds(start_dt)
    if concat_mode:
        last_sec = find_last_timestamp_in_concat(concat_csv_path, symbol) if concat_csv_path else None
        return max(req_start_s, (last_sec + 60) if last_sec is not None else req_start_s)
    else:
        _, csv_path = csv_paths(out_dir, "futures", symbol, resolution, start_dt, end_dt)
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
                    last_sec = parse_ab_date_time_to_sec(last_line[1], last_line[2])
                    return max(req_start_s, last_sec + 60)
            except Exception:
                pass
        return req_start_s

# ============ Futures (PF & PI) ============

def fetch_instruments():
    data = http_get_json(INSTR_API, max_retries=5)
    return data.get("instruments", []) or data.get("data", {}).get("instruments", []) or []

def list_symbols_by_prefix(instruments, prefix):
    syms = []
    for inst in instruments:
        sym = str(inst.get("symbol","")).upper()
        if sym.startswith(prefix):
            syms.append(sym)
    return sorted(list(dict.fromkeys(syms)))

def classify_futures_symbol(symbol: str, instruments: list) -> str:
    sym = symbol.upper()
    for inst in instruments:
        try:
            if (inst.get("symbol") or "").upper() != sym:
                continue
            ct = (inst.get("contractType") or inst.get("contract_type")
                  or inst.get("futureType") or inst.get("type") or "")
            ct = str(ct).lower()
            if "linear" in ct or sym.startswith("PF_"):   return "linear"
            if "inverse" in ct or sym.startswith("PI_"):  return "inverse"
            margin_ccy = (inst.get("marginCurrency") or inst.get("margin_currency") or "")
            if isinstance(margin_ccy, str) and margin_ccy.upper() in ("BTC","XBT","ETH","SOL","XRP"):
                return "inverse"
            return "unknown"
        except Exception:
            continue
    if sym.startswith("PF_"): return "linear"
    if sym.startswith("PI_"): return "inverse"
    return "unknown"

def validate_resolution(res: str) -> str:
    s = res.strip().lower()
    if s.endswith(("m","h","d")):
        return s
    try:
        return f"{int(s)}m"
    except ValueError:
        raise ValueError("Résolution invalide. Ex: 1m,5m,15m,1h,1d (ou entier en minutes).")

def fetch_top5_by_prefix(prefix):
    data = http_get_json(TICK_API, max_retries=5)
    tickers = data.get("tickers", [])
    filtered = [t for t in tickers if str(t.get("symbol","")).upper().startswith(prefix.upper())]
    ranked = []
    for t in filtered:
        sym = t.get("symbol", "")
        last = as_float(fget(t, "last", "lastPrice"))
        vol_q = fget(t, "volume24hQuote", "volumeQuote24h", "volumeQuote", "volQuote24h")
        if vol_q is not None:
            vol_usd_24h = as_float(vol_q)
        else:
            vol_base_24h = as_float(fget(t, "volume24h", "vol24h", "volume"))
            vol_usd_24h = last * vol_base_24h
        oi = as_float(fget(t, "openInterest", "open_interest", "oi"))
        ranked.append((sym, vol_usd_24h, oi))
    ranked.sort(key=lambda x: x[1], reverse=True)
    return ranked[:5]

def show_top5_and_pick(prefix, default_sym):
    """Retourne (symbol, mode) où mode est None ou 'ALL'. ENTER = ALL (défaut)."""
    try:
        top5 = fetch_top5_by_prefix(prefix)
    except Exception as e:
        print("Avertissement: impossible de récupérer le Top 5 (", e, ").")
        return None, "ALL"

    print(f"\nTop 5 {prefix} par volume 24h en USD :")
    for i, (sym, vol_usd, oi) in enumerate(top5, start=1):
        print(f"{i}. {sym:>12}  volume24h≈${vol_usd:,.0f}  openInterest≈${oi:,.0f}")
    print("6. TOUS les symboles de cette catégorie (défaut)")

    choice = input("Choisir 1-6, ENTER = TOUS, ou saisir un symbole : ").strip().upper()
    if choice == "" or choice == "6":
        return None, "ALL"
    if choice.isdigit():
        n = int(choice)
        if 1 <= n <= 5:
            return top5[n-1][0], None
    return choice, None

def make_concat_handle_if_needed(out_dir, resolution, start_dt, end_dt, enable_concat):
    if not enable_concat:
        return None, None, None
    concat_f, concat_writer, concat_csv_path = make_concat_csv(out_dir, "futures", resolution, start_dt, end_dt)
    return concat_f, concat_writer, concat_csv_path

def run_futures_single(symbol: str, resolution: str, start_dt: datetime, end_dt: datetime,
                       out_dir: Path, concat_mode: bool,
                       concat_writer=None, concat_csv_path: Path | None=None,
                       gprogress: GlobalProgress | None=None):
    """
    Télécharge un symbole Futures.
    - concat_mode=False : fichiers séparés + reprise via CSV dédié
    - concat_mode=True  : écrit dans concat_writer; reprise via CSV concat
    - gprogress: mise à jour de la progression globale (en secondes couvertes)
    """
    res = validate_resolution(resolution)
    req_start_s = to_unix_seconds(start_dt)
    end_s       = to_unix_seconds(end_dt)

    # Déterminer start_s effectif (reprise)
    start_s = compute_symbol_resume_start(symbol, res, start_dt, end_dt, out_dir, concat_mode, concat_csv_path)
    remaining = max(0, end_s - start_s)
    if remaining <= 0:
        print(f"{symbol}: déjà à jour, rien à faire.")
        return 0

    # Barre de progression symbole + compteur de secondes progressées
    sprogress = SymbolProgress(total_steps=remaining, prefix=f"{symbol}")
    progressed = 0

    # Ouverture sorties
    if not concat_mode:
        raw_f, csv_f, writer, raw_path, csv_path, _resumed = open_outputs_with_resume(
            out_dir, "futures", symbol, res, start_dt, end_dt
        )
    else:
        if concat_writer is None or concat_csv_path is None:
            raise RuntimeError("concat_writer/csv_path manquants en mode concat.")
        raw_path, _ = csv_paths(out_dir, "futures", symbol, res, start_dt, end_dt)
        raw_f = raw_path.open("a", encoding="utf-8")
        csv_f = None
        writer = concat_writer
        csv_path = concat_csv_path

    print(f"\n[{symbol}] → {csv_path}")

    cur_from = start_s
    total_candles = 0

    try:
        while True:
            if cur_from >= end_s:
                break

            params = {"from": cur_from, "to": end_s}
            url = f"{FUT_API}/{symbol}/{res}?{urlencode(params)}"
            try:
                data = http_get_json(url, max_retries=5)
            except Exception as e:
                print(f"[{symbol}] Erreur HTTP:", e)
                time.sleep(ERR_SLEEP); continue

            raw_f.write(json.dumps(data, ensure_ascii=False) + "\n")

            candles = data.get("candles") or []
            wrote_any = False
            for c in candles:
                tms = int(c["time"])
                tsec = tms // 1000
                if tsec < start_s:
                    continue
                if tsec >= end_s:
                    break
                d, t = ms_to_ab_date_time_from_ms(tms)
                writer.writerow([symbol, d, t, c["open"], c["high"], c["low"], c["close"], c["volume"]])
                total_candles += 1
                wrote_any = True

            # Progression: avancer le curseur temps symbol et refléter globalement
            prev_from = cur_from
            last_ms = int(candles[-1]["time"]) if candles else (cur_from * 1000)
            next_from = (last_ms // 1000) + 60
            cur_from = max(next_from, cur_from + 60)

            # Avance réelle et mise à jour de la barre symbole
            step_advance = min(end_s, cur_from) - min(end_s, prev_from)
            if step_advance > 0:
                progressed += step_advance
                sprogress.update_to(progressed)

            # Sortie si pas de suite et rien écrit
            if not data.get("more_candles") and not wrote_any:
                break

            time.sleep(DEF_SLEEP)

    finally:
        raw_f.close()
        if csv_f:
            csv_f.close()
        # Fin barre symbole + affichage instantané de la barre globale
        try:
            sprogress.end()
        except Exception:
            pass
        if gprogress and progressed:
            gprogress.bump(progressed)
            sys.stdout.write("\n")
            sys.stdout.flush()
        delete_file(raw_path)

    print(f"Terminé ({symbol}). Bougies écrites: {total_candles}")
    return total_candles

# ============ MAIN ============

def main():
    print(f"=== Kraken Futures OHLC → AmiBroker CSV (v{VERSION}) ===")

    # Défauts UTC: hier 00:00 → aujourd'hui 00:00 (borne exclusive)
    today_utc = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    y0 = today_utc - timedelta(days=1)
    y1 = today_utc
    default_start_str = y0.strftime("%Y-%m-%d 00:00:00+00:00")
    default_end_str   = y1.strftime("%Y-%m-%d 00:00:00+00:00")

    out_dir_str = input("Dossier de sortie (ENTER = courant) : ").strip() or "."
    out_dir = Path(out_dir_str)
    ensure_paths(out_dir)

    ftype = input("Type de contrat ?  PF = linéaire (défaut) | PI = inverse : ").strip().upper() or "PF"
    prefix = "PF_" if ftype != "PI" else "PI_"
    default_sym = "PF_XBTUSD" if prefix == "PF_" else "PI_XBTUSD"

    # Top 5 — ENTER => ALL par défaut
    chosen_sym, mode = show_top5_and_pick(prefix, default_sym)
    if mode == "ALL":
        symbols_mode = "ALL"
        symbol_list = []
    else:
        user_sym = input(f"Symbole futures (ENTER = {chosen_sym}) : ").strip().upper()
        symbol = user_sym if user_sym else chosen_sym
        symbols_mode = "ONE"
        symbol_list = [symbol]

    resolution = input("Résolution (ex: 1m,5m,15m,1h,1d) [défaut 1m] : ").strip() or "1m"
    start_str  = input(f"Start UTC (ENTER = {default_start_str}) : ").strip() or default_start_str
    end_str    = input(f"End   UTC (ENTER = {default_end_str} ; borne exclusive) : ").strip() or default_end_str

    try:
        start_dt = parse_user_datetime(start_str)
        end_dt   = parse_user_datetime(end_str)
    except Exception as e:
        print("Date invalide :", e); return 1
    if end_dt <= start_dt:
        print("Erreur : End doit être > Start."); return 1

    concat_mode = False
    concat_f = concat_writer = concat_csv_path = None

    if symbols_mode == "ALL":
        try:
            instruments = fetch_instruments()
            full_list = list_symbols_by_prefix(instruments, prefix)
            if not full_list:
                print(f"Aucun symbole trouvé pour {prefix}."); return 1
            print(f"{len(full_list)} symboles trouvés pour {prefix} (ordre alphabétique).")
            resume_from_sym = input("Reprendre à partir de ce symbole (ENTER = début) : ").strip().upper()
            if resume_from_sym:
                if resume_from_sym in full_list:
                    start_idx = full_list.index(resume_from_sym)
                    symbol_list = full_list[start_idx:]
                else:
                    print(f"{resume_from_sym} introuvable, on démarre au début.")
                    symbol_list = full_list
            else:
                symbol_list = full_list
            # Mode concat ?
            ans_concat = input("Mode concat (UN SEUL CSV multi-tickers) ? [O/n] : ").strip().lower()
            if ans_concat in ("", "o", "oui", "y", "yes"):
                concat_mode = True
                concat_f, concat_writer, concat_csv_path = make_concat_csv(out_dir, "futures", resolution, start_dt, end_dt)
        except KeyboardInterrupt:
            print("\nInterruption par l'utilisateur (listing)."); return 130
        except Exception as e:
            print("Erreur instruments :", e); return 1
    else:
        try:
            instruments = fetch_instruments()
        except Exception:
            instruments = []
        if symbol_list:
            ctype = classify_futures_symbol(symbol_list[0], instruments)
            attendu = "linear" if prefix == "PF_" else "inverse"
            if ctype not in ("unknown", attendu):
                print(f"Attention: {symbol_list[0]} détecté '{ctype}' (attendu: {attendu}).")

    # ======= Progression globale: calcul du total à parcourir (en secondes) =======
    end_s = to_unix_seconds(end_dt)
    total_seconds = 0
    for sym in symbol_list:
        eff_start_s = compute_symbol_resume_start(sym, validate_resolution(resolution),
                                                  start_dt, end_dt, out_dir, concat_mode, concat_csv_path)
        total_seconds += max(0, end_s - eff_start_s)
    gprog = GlobalProgress(total_seconds, prefix="Progression globale")

    # ======= Téléchargements =======
    try:
        if concat_mode:
            try:
                for i, sym in enumerate(symbol_list, 1):
                    print(f"\n[{i}/{len(symbol_list)}] {sym}")
                    run_futures_single(sym, resolution, start_dt, end_dt, out_dir,
                                       concat_mode=True, concat_writer=concat_writer, concat_csv_path=concat_csv_path,
                                       gprogress=gprog)
                    time.sleep(0.4)
            finally:
                if concat_f:
                    concat_f.close()
        else:
            for i, sym in enumerate(symbol_list, 1):
                print(f"\n[{i}/{len(symbol_list)}] {sym}")
                run_futures_single(sym, resolution, start_dt, end_dt, out_dir,
                                   concat_mode=False, gprogress=gprog)
                time.sleep(0.4)
    except KeyboardInterrupt:
        print("\nInterruption par l'utilisateur (futures)."); return 130

    gprog.done()
    print("\nTerminé.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
