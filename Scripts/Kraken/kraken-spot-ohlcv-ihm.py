#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Kraken Spot → OHLC/OLHCV → CSV AmiBroker (interactif)
- Endpoint public OHLC, saisie interactive de la paire et de l'intervalle en minutes
- Reprise intra-paire: reprend à la minute suivant la dernière bougie existante dans le CSV
- Suppression automatique du JSONL (log brut) en fin de téléchargement
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

SPOT_API   = "https://api.kraken.com/0/public/OHLC"

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
    Fichier unique par paire:
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

# ============ Spot ============

def validate_spot_pair(pair: str) -> bool:
    try:
        test_since = int(time.time()) - 3600
        url = f"{SPOT_API}?{urlencode({'pair': pair, 'interval': 1, 'since': test_since})}"
        data = http_get_json(url, max_retries=3)
        return not data.get("error")
    except Exception:
        return False

def run_spot(pair: str, interval_min: int, start_dt: datetime, end_dt: datetime, out_dir: Path):
    start_s = to_unix_seconds(start_dt)
    end_s   = to_unix_seconds(end_dt)

    raw_f, csv_f, w, raw_path, csv_path, resume_from_sec = open_outputs_with_resume(
        out_dir, "spot", pair, f"{interval_min}m", start_dt, end_dt
    )
    if resume_from_sec is not None:
        start_s = max(start_s, resume_from_sec)

    since = start_s
    total_written = 0

    print(f"\nTéléchargement SPOT {pair} @{interval_min}m")
    print(f"CSV: {csv_path}")

    try:
        while True:
            if since >= end_s:
                break
            params = {"pair": pair, "interval": interval_min, "since": since}
            url = f"{SPOT_API}?{urlencode(params)}"
            try:
                data = http_get_json(url, max_retries=5)
            except Exception as e:
                print("Erreur spot:", e)
                time.sleep(ERR_SLEEP); continue

            raw_f.write(json.dumps(data, ensure_ascii=False) + "\n")

            if data.get("error"):
                print("Erreur API Kraken (spot):", data["error"])
                time.sleep(ERR_SLEEP); continue

            result = data.get("result", {})
            next_since = int(result.get("last", since))

            keys = [k for k in result.keys() if k != "last"]
            if keys:
                kpair = keys[0]
                rows = result.get(kpair, [])
                for r in rows:
                    t = int(r[0])
                    if t < start_s:
                        continue
                    if t >= end_s:
                        next_since = end_s
                        break
                    d, tstr = ms_to_ab_date_time_from_sec(t)
                    open_, high, low, close, vwap, volume, count = r[1:8]
                    w.writerow([pair, d, tstr, open_, high, low, close, volume])
                    total_written += 1

            since = max(next_since, since + 60)
            time.sleep(DEF_SLEEP)
    finally:
        raw_f.close()
        csv_f.close()
        delete_file(raw_path)

    print(f"Terminé (spot). Bougies écrites: {total_written}")

# ============ MAIN ============

def main():
    print(f"=== Kraken Spot OHLC → AmiBroker CSV (v{VERSION}) ===")

    # Défauts UTC: hier 00:00 → aujourd'hui 00:00 (borne exclusive)
    today_utc = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    y0 = today_utc - timedelta(days=1)
    y1 = today_utc
    default_start_str = y0.strftime("%Y-%m-%d 00:00:00+00:00")
    default_end_str   = y1.strftime("%Y-%m-%d 00:00:00+00:00")

    out_dir_str = input("Dossier de sortie (ENTER = courant) : ").strip() or "."
    out_dir = Path(out_dir_str)
    ensure_paths(out_dir)

    while True:
        pair = input("Paire spot (ex: XBTUSD ; ENTER = XBTUSD) : ").strip().upper() or "XBTUSD"
        if validate_spot_pair(pair):
            break
        print("Paire invalide pour l'endpoint OHLC spot. Réessaie (ex: XBTUSD).")

    interval_str = input("Interval spot en minutes (ex: 1,5,15,60,240,1440) [défaut 1] : ").strip() or "1"
    try:
        interval = int(interval_str)
    except ValueError:
        print("Interval invalide."); return 1

    start_str = input(f"Start UTC (ENTER = {default_start_str}) : ").strip() or default_start_str
    end_str   = input(f"End   UTC (ENTER = {default_end_str} ; borne exclusive) : ").strip() or default_end_str

    try:
        start_dt = parse_user_datetime(start_str)
        end_dt   = parse_user_datetime(end_str)
    except Exception as e:
        print("Date invalide :", e); return 1
    if end_dt <= start_dt:
        print("Erreur : End doit être > Start."); return 1

    try:
        run_spot(pair, interval, start_dt, end_dt, out_dir)
    except KeyboardInterrupt:
        print("\nInterruption par l'utilisateur (spot)."); return 130
    return 0

if __name__ == "__main__":
    sys.exit(main())
