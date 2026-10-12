# -*- coding: utf-8 -*-
"""
update_loto.py — Rafraîchit loto_MASTER.csv et loto_PRIZES.csv depuis l'historique officiel FDJ
(zip CSV « loto_201911 », règle en vigueur, téléchargé depuis l'API documentaire FDJ).
Append-only : un tirage déjà présent n'est jamais réécrit. Écrit output/fdj_meta.json (dernier tirage,
jackpot du dernier tirage, gagnant ou non) pour l'estimation du jackpot par run_loto.py.

Usage : python3 update_loto.py [--dry-run]
Sortie : 0 si OK, 2 si la FDJ est injoignable, 3 si l'intégrité casse.
"""
import argparse, csv, io, json, os, sys, time, urllib.request, zipfile
from datetime import date, datetime
import qsc_loto as q
import popularite_loto as P

FDJ_ZIP = "https://www.sto.api.fdj.fr/anonymous/service-draw-info/v3/documentations/1a2b3c4d-9876-4562-b3fc-2c963f66afp6"

def fetch_rows(retries=3):
    req = urllib.request.Request(FDJ_ZIP, headers={"User-Agent": "qsc-loto/1.0"})
    for i in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read()
            z = zipfile.ZipFile(io.BytesIO(data))
            name = next(n for n in z.namelist() if n.endswith(".csv"))
            text = z.read(name).decode("latin-1")
            return list(csv.DictReader(io.StringIO(text), delimiter=";"))
        except Exception as e:
            if i < retries - 1: time.sleep(5 * (i + 1)); continue
            raise

def parse(it):
    d = datetime.strptime(it["date_de_tirage"].strip(), "%d/%m/%Y").date().isoformat()
    nums = tuple(sorted(int(it[f"boule_{i}"]) for i in range(1, 6)))
    ch = int(it["numero_chance"])
    W = {k: int(it[f"nombre_de_gagnant_au_rang{k}"].replace(" ", ""))
         for k in range(1, 10) if it.get(f"nombre_de_gagnant_au_rang{k}") not in (None, "")}
    r1 = it.get("rapport_du_rang1", "")
    r1 = float(r1.replace(",", ".").replace(" ", "")) if r1 else None
    return d, nums, ch, {"era": 9 if len(W) >= 9 else 6, "w": W, "rapport1": r1}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default="loto_MASTER.csv")
    ap.add_argument("--prizes", default="loto_PRIZES.csv")
    ap.add_argument("--out", default="output")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    draws = q.load_master(a.csv); known = {d[0]: d for d in draws}
    prizes = P.load_prizes(a.prizes)
    try:
        rows = fetch_rows()
    except Exception as e:
        print(f"FDJ injoignable : {e}", file=sys.stderr); sys.exit(2)
    added, padded, last = [], [], None
    for it in rows:
        try:
            d, nums, ch, pz = parse(it)
        except Exception as e:
            print(f"ligne illisible ignorée : {e}", file=sys.stderr); continue
        if d not in known:
            known[d] = (d, nums, ch); added.append(d)
        elif known[d][1] != nums or known[d][2] != ch:
            print(f"CONFLIT {d} : CSV {known[d][1:]} vs FDJ {(nums, ch)} — CSV conservé", file=sys.stderr)
        if d not in prizes:
            prizes[d] = pz; padded.append(d)
        if last is None or d > last[0]:
            last = (d, pz)
    new_draws = sorted(known.values())
    ok, alerts = q.integrity_check(new_draws)
    print(f"{len(added)} nouveau(x) tirage(s) : {', '.join(sorted(added)) if added else '—'} ; gagnants par rang : +{len(padded)}")
    print(f"total {len(new_draws)} ({new_draws[0][0]} → {new_draws[-1][0]}) ; intégrité {'OK' if ok else 'KO'} {alerts}")
    if not ok: sys.exit(3)
    if a.dry_run: return
    if added: q.save_master(a.csv, new_draws)
    if padded: P.save_prizes(a.prizes, prizes)
    os.makedirs(a.out, exist_ok=True)
    meta = {"fetched_at": date.today().isoformat(), "added": sorted(added), "last_draw": None,
            "fingerprint": q.dataset_fingerprint(new_draws, "csv+fdj")}
    if last:
        d, pz = last
        meta["last_draw"] = {"date": d, "has_winner": pz["w"].get(1, 0) > 0, "jackpot_eur": pz["rapport1"],
                             "jackpot_winners": pz["w"].get(1, 0)}
    with open(os.path.join(a.out, "fdj_meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)

if __name__ == "__main__":
    main()
