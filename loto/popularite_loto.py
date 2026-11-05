# -*- coding: utf-8 -*-
"""
popularite_loto.py — popularité des numéros (1-49) et du numéro Chance (1-10) estimée sur les
gagnants par rang publiés par la FDJ (loto_PRIZES.csv).

Numéros : ratio (gagnants à 3 numéros, avec ou sans Chance) / (gagnants à 2 numéros, idem), qui
élimine les ventes inconnues et ne dépend que de la popularité des 5 numéros tirés. Règle 2008-2017 :
rang 4 / rang 5 ; règle 2017+ : (rang 5 + rang 6) / (rang 7 + rang 8). Régression de log(ratio) sur
les indicatrices des numéros tirés, b_n ≈ SLOPE_NUMS × (ρ_n − 1), pente calibrée par simulation
(0,260 pour 5 parmi 49 — tools/calibration_r7.py adapté).

Numéro Chance (règle 2017+ seulement) : ratio (k numéros + Chance) / (k numéros sans Chance),
rangs 3/4 + 5/6 + 7/8 sommés ; sous jeu uniforme il vaut 1/9. log(ratio) régressé sur l'indicatrice
du numéro Chance tiré, b_c ≈ SLOPE_CHANCE × (ρ_c − 1), pente analytique 1,08.

Pur stdlib : réutilise le solveur ridge de popularite.py (dépôt parent).
"""
import csv, math, os, sys
from collections import Counter
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from popularite import _ridge_fit   # noqa: E402

SLOPE_NUMS = 0.260
SLOPE_CHANCE = 1.076
MIN_DRAWS_NUMS = 400
MIN_DRAWS_CHANCE = 300

def load_prizes(path):
    """CSV date;era;w1..w9;rapport_rang1 → {date: {"era": 6|9, "w": {rang: gagnants}, "rapport1": float|None}}."""
    out = {}
    if not os.path.exists(path): return out
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f, delimiter=";"):
            W = {k: int(float(row[f"w{k}"])) for k in range(1, 10) if row.get(f"w{k}") not in ("", None)}
            r1 = row.get("rapport_rang1")
            out[row["date"]] = {"era": int(row["era"]), "w": W, "rapport1": float(r1) if r1 not in ("", None) else None}
    return out

def save_prizes(path, prizes):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter=";", lineterminator="\n")
        w.writerow(["date", "era"] + [f"w{k}" for k in range(1, 10)] + ["rapport_rang1"])
        for d in sorted(prizes):
            p = prizes[d]
            w.writerow([d, p["era"]] + [p["w"].get(k, "") for k in range(1, 10)] + [p["rapport1"] if p["rapport1"] is not None else ""])

def w3_w2(p):
    """(gagnants 3 numéros, gagnants 2 numéros) toutes classes Chance confondues, selon la règle."""
    W = p["w"]
    if p["era"] == 6:
        return W.get(4), W.get(5)
    return (W.get(5, 0) + W.get(6, 0)) or None, (W.get(7, 0) + W.get(8, 0)) or None

def with_without_chance(p):
    if p["era"] != 9: return None, None
    W = p["w"]
    return W.get(3, 0) + W.get(5, 0) + W.get(7, 0), W.get(4, 0) + W.get(6, 0) + W.get(8, 0)

def fit_numbers(prizes, draws):
    by_date = {d: nums for d, nums, _ in draws}
    rows_x, y, cnt = [], [], Counter()
    for d in sorted(prizes):
        if d not in by_date: continue
        w3, w2 = w3_w2(prizes[d])
        if not w3 or not w2 or w2 < 5_000 or w3 < 300: continue
        idx = [n - 1 for n in by_date[d]]
        rows_x.append(idx); y.append(math.log(w3 / w2)); cnt.update(idx)
    if len(y) < MIN_DRAWS_NUMS: return None
    a, b, resid = _ridge_fit(rows_x, y, 49)
    sigma = math.sqrt(sum(r * r for r in resid) / max(1, len(y) - 50))
    var_y = sum((v - sum(y) / len(y)) ** 2 for v in y) / len(y)
    return {"rho": {n: max(0.3, 1.0 + b[n - 1] / SLOPE_NUMS) for n in range(1, 50)},
            "se": {n: sigma / math.sqrt(max(1, cnt[n - 1])) / SLOPE_NUMS for n in range(1, 50)},
            "n_draws": len(y), "periode": [min(d for d in prizes if d in by_date), max(prizes)],
            "intercept": a, "intercept_uniforme": math.log((math.comb(5, 3) * math.comb(44, 2)) / (math.comb(5, 2) * math.comb(44, 3))),
            "sigma_resid": sigma, "r2": 1 - sigma ** 2 / var_y if var_y > 0 else 0.0}

def fit_chance(prizes, draws):
    by_date = {d: ch for d, _, ch in draws}
    rows_x, y, cnt = [], [], Counter()
    for d in sorted(prizes):
        if d not in by_date: continue
        wc, wn = with_without_chance(prizes[d])
        if not wc or not wn or wn < 5_000 or wc < 500: continue
        idx = [by_date[d] - 1]
        rows_x.append(idx); y.append(math.log(wc / wn)); cnt.update(idx)
    if len(y) < MIN_DRAWS_CHANCE: return None
    a, b, resid = _ridge_fit(rows_x, y, 10)
    # _ridge_fit recentre l'intercept pour k=50 (5 indicatrices) ou sinon 2 : ici 1 indicatrice → corrige
    sigma = math.sqrt(sum(r * r for r in resid) / max(1, len(y) - 11))
    return {"rho": {c: max(0.3, 1.0 + b[c - 1] / SLOPE_CHANCE) for c in range(1, 11)},
            "se": {c: sigma / math.sqrt(max(1, cnt[c - 1])) / SLOPE_CHANCE for c in range(1, 11)},
            "n_draws": len(y), "sigma_resid": sigma, "intercept_uniforme": math.log(1 / 9)}

def estimate(prizes_path, draws):
    prizes = load_prizes(prizes_path)
    if not prizes: return None
    fn, fc = fit_numbers(prizes, draws), fit_chance(prizes, draws)
    if fn is None or fc is None: return None
    return {"source": "gagnants par rang FDJ (loto_PRIZES.csv)", "nums": fn["rho"], "chance": fc["rho"],
            "meta": {"numeros": {k: v for k, v in fn.items() if k != "rho"},
                     "chance": {k: v for k, v in fc.items() if k != "rho"},
                     "slope_nums": SLOPE_NUMS, "slope_chance": SLOPE_CHANCE}}
