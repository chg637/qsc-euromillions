# -*- coding: utf-8 -*-
"""
update_master.py — Rafraîchit euromillions_MASTER.csv depuis l'API pedromealha.
Append-only : n'écrase jamais un tirage existant, refuse d'écrire si l'intégrité casse.
Écrit aussi output/api_meta.json (dernier tirage, jackpot du dernier tirage, gagnant ou non)
pour l'estimation du prochain jackpot par run_qsc.py.

Usage : python3 update_master.py [--csv euromillions_MASTER.csv] [--dry-run]
Sortie : code 0 si OK (même sans nouveauté), 2 si l'API est injoignable, 3 si intégrité KO.
"""
import argparse, json, os, sys, time, urllib.request, urllib.error
from datetime import date
import qsc_v37 as q

API = "https://euromillions.api.pedromealha.dev/v1/draws?year={year}"

def fetch_year(year, retries=4):
    req = urllib.request.Request(API.format(year=year), headers={"User-Agent": "qsc-euromillions/3.7"})
    for i in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 429 and i < retries - 1:
                time.sleep(5 * (i + 1)); continue
            raise
        except (urllib.error.URLError, TimeoutError):
            if i < retries - 1:
                time.sleep(5 * (i + 1)); continue
            raise

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default="euromillions_MASTER.csv")
    ap.add_argument("--out", default="output")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    draws = q.load_master(a.csv)
    known = {d[0]: d for d in draws}
    last_year = int(draws[-1][0][:4])
    this_year = date.today().year

    added, api_last = [], None
    for year in range(last_year, this_year + 1):
        try:
            items = fetch_year(year)
        except Exception as e:
            print(f"API injoignable ({year}) : {e}", file=sys.stderr)
            if not added and year == last_year:
                sys.exit(2)
            break
        for it in items:
            d = it["date"]
            nums = tuple(sorted(int(x) for x in it["numbers"]))
            stars = tuple(sorted(int(x) for x in it["stars"]))
            if d in known:
                if known[d][1] != nums or known[d][2] != stars:
                    print(f"CONFLIT {d} : CSV {known[d][1:]} vs API {(nums, stars)} — CSV conservé", file=sys.stderr)
                continue
            known[d] = (d, nums, stars); added.append(d)
        # méta du dernier tirage connu de l'API
        items_sorted = sorted(items, key=lambda x: x["date"])
        if items_sorted:
            last = items_sorted[-1]
            jp = next((p for p in last.get("prizes", []) if p["matched_numbers"] == 5 and p["matched_stars"] == 2), None)
            api_last = {"date": last["date"], "has_winner": bool(last.get("has_winner")),
                        "jackpot_eur": jp["prize"] if jp else None,
                        "jackpot_winners": jp["winners"] if jp else None}
        time.sleep(1.5)

    new_draws = sorted(known.values())
    ok, alerts = q.integrity_check(new_draws)
    print(f"{len(added)} nouveau(x) tirage(s) : {', '.join(added) if added else '—'}")
    print(f"total {len(new_draws)} ({new_draws[0][0]} → {new_draws[-1][0]}) ; intégrité {'OK' if ok else 'KO'} {alerts}")
    if not ok:
        sys.exit(3)
    if a.dry_run:
        return
    if added:
        q.save_master(a.csv, new_draws)
    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, "api_meta.json"), "w", encoding="utf-8") as f:
        json.dump({"fetched_at": date.today().isoformat(), "added": added, "last_draw": api_last,
                   "fingerprint": q.dataset_fingerprint(new_draws, "csv+api")}, f, ensure_ascii=False, indent=1)

if __name__ == "__main__":
    main()
