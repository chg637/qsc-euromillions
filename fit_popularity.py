# -*- coding: utf-8 -*-
"""
fit_popularity.py — Estime la popularité RELATIVE de chaque numéro (1-50) et de chaque étoile
(1-12) auprès des joueurs EuroMillions, à partir du nombre de gagnants par rang publié à
chaque tirage (API pedromealha, totaux européens — c'est la bonne population pour le partage,
puisque les rangs sont pari-mutuel au niveau européen).

Principe : conditionnellement au tirage, le nombre de tickets ayant k numéros exacts vaut
    W_k ≈ T · q_k · moyenne_{A ⊂ tirage, |A|=k} Π_{n∈A} w_n
avec T le nombre de tickets du tirage (nuisance, éliminée en forme close), q_k la probabilité
hypergéométrique de k matches et w_n la popularité relative du numéro n (moyenne 1).
On ajuste w (50 paramètres) sur k = 2, 3, 4 pour tous les tirages de l'ère 12 étoiles
(27/09/2016 →). Même logique pour les étoiles (fractions 0/1/2 étoiles parmi les gagnants
à 2 et 3 numéros ; T s'élimine aussi).

C'est le seul apprentissage qui ait un sens dans ce jeu : il porte sur les autres joueurs,
pas sur les boules. Il ne change pas la probabilité de gagner, seulement le partage attendu.

Sorties :
  winners_MASTER.csv   date;k;s;winners  (cache append-only des gagnants par rang)
  popularity_fdj.json  table w (numéros), v (étoiles), métadonnées d'ajustement
Usage : python3 fit_popularity.py [--no-fetch] [--out popularity_fdj.json]
Dépendances : numpy, scipy (le pipeline du jour n'en a pas besoin : il lit seulement le JSON).
"""
import argparse, csv, json, math, itertools, os, sys, time, urllib.request, urllib.error
from datetime import date

API = "https://euromillions.api.pedromealha.dev/v1/draws?year={year}"
ERA12 = "2016-09-27"
WIN_CSV = "winners_MASTER.csv"

def fetch_year(year, retries=4):
    req = urllib.request.Request(API.format(year=year), headers={"User-Agent": "qsc-euromillions/3.9"})
    for i in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 429 and i < retries - 1:
                time.sleep(20 * (i + 1)); continue
            raise
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            if i < retries - 1:
                time.sleep(10 * (i + 1)); continue
            raise

def load_winners(path):
    rows = {}
    if os.path.exists(path):
        with open(path, newline="", encoding="utf-8") as f:
            r = csv.DictReader(f, delimiter=";")
            for x in r:
                rows.setdefault(x["date"], {})[(int(x["k"]), int(x["s"]))] = int(x["winners"])
    return rows

def save_winners(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter=";", lineterminator="\n")
        w.writerow(["date", "k", "s", "winners"])
        for d in sorted(rows):
            for (k, s), n in sorted(rows[d].items()):
                w.writerow([d, k, s, n])

def refresh(rows, draws_by_date):
    """Complète le cache : années dont il manque des tirages (toujours l'année courante)."""
    years_have = {}
    for d in rows: years_have[int(d[:4])] = years_have.get(int(d[:4]), 0) + 1
    today = date.today()
    todo = [y for y in range(int(ERA12[:4]), today.year + 1)
            if y >= today.year - 1 or years_have.get(y, 0) < 100]
    for y in todo:
        try:
            items = fetch_year(y)
        except Exception as e:
            print(f"API injoignable ({y}) : {e}", file=sys.stderr); continue
        n = 0
        for it in items:
            d = it["date"]
            if d < ERA12 or not it.get("prizes"): continue
            rows[d] = {(p["matched_numbers"], p["matched_stars"]): int(p["winners"]) for p in it["prizes"]}
            draws_by_date[d] = (tuple(sorted(int(x) for x in it["numbers"])), tuple(sorted(int(x) for x in it["stars"])))
            n += 1
        print(f"{y} : {n} tirages avec gagnants par rang")
        time.sleep(12)
    return rows

def fit(rows, draws_by_date):
    import numpy as np
    from scipy.optimize import least_squares
    data = []
    for d in sorted(rows):
        if d not in draws_by_date: continue
        pr = rows[d]; nums, stars = draws_by_date[d]
        W = {k: sum(pr.get((k, s), 0) for s in (0, 1, 2)) for k in (2, 3, 4)}
        if min(W.values()) <= 0: continue
        data.append((d, nums, stars, W, {(k, s): pr.get((k, s), 0) for k in (2, 3) for s in (0, 1, 2)}))
    N = len(data)
    NUMS = np.array([x[1] for x in data]) - 1
    ks = (2, 3, 4)
    q = {k: math.comb(5, k) * math.comb(45, 5 - k) / math.comb(50, 5) for k in ks}
    combos = {k: np.array(list(itertools.combinations(range(5), k))) for k in ks}
    LW = np.array([[math.log(x[3][k]) for k in ks] for x in data]); LQ = np.array([math.log(q[k]) for k in ks])

    def model(theta):
        w = np.exp(theta); w = w / w.mean()
        wn = w[NUMS]
        LS = np.stack([np.log(np.prod(wn[:, combos[k]], axis=2).mean(axis=1)) for k in ks], axis=1)
        return LS, w
    def resid(theta):
        LS, _ = model(theta)
        logT = (LW - LQ - LS).mean(axis=1, keepdims=True)
        return (logT + LQ + LS - LW).ravel()
    res = least_squares(resid, np.zeros(50), max_nfev=300)
    _, w = model(res.x)
    rms, rms0 = float(np.sqrt(np.mean(res.fun ** 2))), float(np.sqrt(np.mean(resid(np.zeros(50)) ** 2)))

    ST = np.array([x[2] for x in data]) - 1
    WS = np.array([[[x[4][(k, s)] for s in (0, 1, 2)] for k in (2, 3)] for x in data], float)
    def resid_s(p):
        v = np.exp(p); v = v / v.mean()
        a, b = v[ST[:, 0]], v[ST[:, 1]]
        mask = np.ones((N, 12), bool); mask[np.arange(N), ST[:, 0]] = False; mask[np.arange(N), ST[:, 1]] = False
        oth = np.where(mask, v[None, :], 0.0)
        s1 = oth.sum(1); s2 = (oth ** 2).sum(1)
        p2 = a * b / 66; p1 = (a + b) / 2 * (s1 / 10) * 20 / 66; p0 = (s1 ** 2 - s2) / 2 / 45 * 45 / 66
        P = np.stack([p0, p1, p2], 1); P = P / P.sum(1, keepdims=True)
        F = WS / WS.sum(2, keepdims=True)
        return (np.log(P[:, None, :]) - np.log(np.maximum(F, 1e-9))).ravel()
    rs = least_squares(resid_s, np.zeros(12), max_nfev=300)
    v = np.exp(rs.x); v = v / v.mean()
    rms_s, rms_s0 = float(np.sqrt(np.mean(rs.fun ** 2))), float(np.sqrt(np.mean(resid_s(np.zeros(12)) ** 2)))

    # stabilité : ajustement sur chaque moitié, corrélation des log-popularités
    half = N // 2
    def fit_half(idx):
        sub_N, sub_LW = NUMS[idx], LW[idx]
        def r(theta):
            w_ = np.exp(theta); w_ = w_ / w_.mean(); wn = w_[sub_N]
            LS = np.stack([np.log(np.prod(wn[:, combos[k]], axis=2).mean(axis=1)) for k in ks], axis=1)
            logT = (sub_LW - LQ - LS).mean(axis=1, keepdims=True)
            return (logT + LQ + LS - sub_LW).ravel()
        x = least_squares(r, np.zeros(50), max_nfev=200).x
        return np.log(np.exp(x) / np.exp(x).mean())
    corr_halves = float(np.corrcoef(fit_half(np.arange(half)), fit_half(np.arange(half, N)))[0, 1])

    return {"fitted_at": date.today().isoformat(), "n_draws": N, "from": data[0][0], "to": data[-1][0],
            "rms_log_numbers": round(rms, 4), "rms_log_numbers_uniform": round(rms0, 4),
            "rms_log_stars": round(rms_s, 4), "rms_log_stars_uniform": round(rms_s0, 4),
            "corr_halves_numbers": round(corr_halves, 3),
            "numbers": {str(i + 1): round(float(w[i]), 4) for i in range(50)},
            "stars": {str(i + 1): round(float(v[i]), 4) for i in range(12)}}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default="euromillions_MASTER.csv")
    ap.add_argument("--winners", default=WIN_CSV)
    ap.add_argument("--out", default="popularity_fdj.json")
    ap.add_argument("--no-fetch", action="store_true")
    a = ap.parse_args()
    draws_by_date = {}
    with open(a.csv, newline="", encoding="utf-8") as f:
        r = csv.reader(f, delimiter=";"); next(r)
        for row in r:
            if row and row[0].strip():
                draws_by_date[row[0]] = (tuple(sorted(int(x) for x in row[1:6])), tuple(sorted(int(x) for x in row[6:8])))
    rows = load_winners(a.winners)
    if not a.no_fetch:
        rows = refresh(rows, draws_by_date)
        save_winners(a.winners, rows)
    if len(rows) < 300:
        print(f"trop peu de tirages avec gagnants ({len(rows)}) : table non réécrite", file=sys.stderr); sys.exit(2)
    out = fit(rows, draws_by_date)
    with open(a.out, "w", encoding="utf-8") as f: json.dump(out, f, ensure_ascii=False, indent=1)
    w = out["numbers"]; order = sorted(w, key=lambda k: w[k])
    print(f"{out['n_draws']} tirages ({out['from']} → {out['to']}) · rms log {out['rms_log_numbers']} (uniforme {out['rms_log_numbers_uniform']}) · corr. moitiés {out['corr_halves_numbers']}")
    print("moins populaires :", ", ".join(f"{k} ({w[k]:.2f})" for k in order[:10]))
    print("plus populaires  :", ", ".join(f"{k} ({w[k]:.2f})" for k in order[-10:][::-1]))
    print("étoiles :", " ".join(f"{k}:{x:.2f}" for k, x in out["stars"].items()))

if __name__ == "__main__":
    main()
