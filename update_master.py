# -*- coding: utf-8 -*-
"""
update_master.py — Rafraîchit euromillions_MASTER.csv depuis l'API pedromealha.
Append-only : n'écrase jamais un tirage existant, refuse d'écrire si l'intégrité casse.
Alimente aussi euromillions_PRIZES.csv (gagnants par rang, append-only, pour la popularité R7)
et écrit output/api_meta.json (dernier tirage, jackpot du dernier tirage, gagnant ou non)
pour l'estimation du prochain jackpot par run_qsc.py.

Usage : python3 update_master.py [--csv euromillions_MASTER.csv] [--dry-run]
Sortie : code 0 si OK (même sans nouveauté), 2 si l'API ET le repli FDJ sont injoignables, 3 si intégrité KO.
"""
import argparse, csv, io, json, os, sys, time, urllib.request, urllib.error, zipfile
from datetime import date, datetime
import qsc_v40 as q
import popularite as P

API = "https://euromillions.api.pedromealha.dev/v1/draws?year={year}"

# v4.2 : repli sur l'historique officiel FDJ (zip CSV « euromillions_202002 », règle en vigueur depuis
# 02/2020) quand l'API pedromealha est injoignable (timeout, 429). Même source que le Loto.
FDJ_ZIP = "https://www.sto.api.fdj.fr/anonymous/service-draw-info/v3/documentations/1a2b3c4d-9876-4562-b3fc-2c963f66afe6"
# Rang FDJ → (numéros, étoiles) : 1=5+2, 2=5+1, 3=5+0, 4=4+2, 5=4+1, 6=3+2, 7=4+0, 8=2+2, 9=3+1, 10=3+0, 11=1+2, 12=2+1, 13=2+0
FDJ_RANKS = {1: (5, 2), 2: (5, 1), 3: (5, 0), 4: (4, 2), 5: (4, 1), 6: (3, 2), 7: (4, 0),
             8: (2, 2), 9: (3, 1), 10: (3, 0), 11: (1, 2), 12: (2, 1), 13: (2, 0)}

def fetch_year(year, retries=4):
    req = urllib.request.Request(API.format(year=year), headers={"User-Agent": "qsc-euromillions/4.0"})
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

def _fr_num(x):
    x = (x or "").replace(",", ".").replace(" ", "").replace("\u202f", "").replace("\xa0", "")
    return float(x) if x else 0.0

def fdj_rows_to_items(rows):
    """Lignes du CSV FDJ → {année: [items au format de l'API]} (date, numbers, stars, has_winner,
    prizes[matched_numbers, matched_stars, prize (€), winners (Europe)]). Les gagnants par rang sont
    ceux du pool européen, comme l'API. Les lignes illisibles sont ignorées."""
    out = {}
    for r in rows:
        try:
            d = datetime.strptime(r["date_de_tirage"].strip(), "%d/%m/%Y").date().isoformat()
            nums = sorted(int(r[f"boule_{i}"]) for i in range(1, 6))
            stars = sorted(int(r[f"etoile_{i}"]) for i in (1, 2))
            prizes = []
            for k, (mn, ms) in FDJ_RANKS.items():
                prizes.append({"matched_numbers": mn, "matched_stars": ms,
                               "prize": _fr_num(r.get(f"rapport_du_rang{k}_Euro_Millions")),
                               "winners": int(_fr_num(r.get(f"nombre_de_gagnant_au_rang{k}_Euro_Millions_en_europe")))})
        except Exception as e:
            print(f"ligne FDJ illisible ignorée : {e}", file=sys.stderr); continue
        winners1 = next(p["winners"] for p in prizes if (p["matched_numbers"], p["matched_stars"]) == (5, 2))
        out.setdefault(int(d[:4]), []).append({"date": d, "numbers": [str(n) for n in nums],
                                               "stars": [str(s) for s in stars],
                                               "has_winner": winners1 > 0, "prizes": prizes})
    return out

def fetch_fdj(retries=3):
    req = urllib.request.Request(FDJ_ZIP, headers={"User-Agent": "qsc-euromillions/4.2"})
    for i in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read()
            z = zipfile.ZipFile(io.BytesIO(data))
            name = next(n for n in z.namelist() if n.endswith(".csv"))
            rows = list(csv.DictReader(io.StringIO(z.read(name).decode("latin-1")), delimiter=";"))
            return fdj_rows_to_items(rows)
        except Exception:
            if i < retries - 1:
                time.sleep(5 * (i + 1)); continue
            raise

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default="euromillions_MASTER.csv")
    ap.add_argument("--prizes", default="euromillions_PRIZES.csv")
    ap.add_argument("--out", default="output")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    draws = q.load_master(a.csv)
    known = {d[0]: d for d in draws}
    prizes = P.load_prizes(a.prizes); prizes_added = []
    last_year = int(draws[-1][0][:4])
    this_year = date.today().year

    added, api_last = [], None
    fdj, used_fdj = None, False
    for year in range(last_year, this_year + 1):
        try:
            items = fetch_year(year)
        except Exception as e:
            print(f"API injoignable ({year}) : {e}", file=sys.stderr)
            try:   # v4.2 : repli sur l'historique officiel FDJ
                if fdj is None:
                    fdj = fetch_fdj()
                items = fdj.get(year) or []
                if not items:
                    raise ValueError(f"aucun tirage {year} dans l'historique FDJ")
                used_fdj = True
                print(f"repli FDJ officiel ({year}) : {len(items)} tirages lus", file=sys.stderr)
            except Exception as e2:
                print(f"FDJ injoignable aussi ({year}) : {e2}", file=sys.stderr)
                if not added and year == last_year:
                    sys.exit(2)
                break
        os.makedirs(os.path.join(a.out, "api_cache"), exist_ok=True)   # montants par rang pour le registre en euros
        with open(os.path.join(a.out, "api_cache", f"{year}.json"), "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False)
        for it in items:
            d = it["date"]
            nums = tuple(sorted(int(x) for x in it["numbers"]))
            stars = tuple(sorted(int(x) for x in it["stars"]))
            if it.get("prizes") and d not in prizes:
                prizes[d] = P.prizes_from_api_item(it); prizes_added.append(d)
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
        time.sleep(3)   # l'API renvoie 429 dès 3 requêtes rapprochées

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
    if prizes_added:
        P.save_prizes(a.prizes, prizes)
    print(f"gagnants par rang : {len(prizes_added)} ligne(s) ajoutée(s), {len(prizes)} au total")
    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, "api_meta.json"), "w", encoding="utf-8") as f:
        json.dump({"fetched_at": date.today().isoformat(), "added": added, "last_draw": api_last,
                   "fingerprint": q.dataset_fingerprint(new_draws, "csv+fdj" if used_fdj else "csv+api")}, f, ensure_ascii=False, indent=1)

if __name__ == "__main__":
    main()
