# -*- coding: utf-8 -*-
"""
popularite.py — R7 : popularité des numéros et des étoiles estimée sur les gagnants par rang.

Idée. À chaque tirage, le nombre de gagnants au rang « k numéros » vaut W_k = N × e_k(S),
où N est le nombre de grilles vendues (inconnu) et e_k(S) la part des grilles qui ont
exactement k numéros du tirage S. Le ratio W3/W2 élimine N et ne dépend plus que de la
popularité des 5 numéros tirés : plus ils sont joués, plus la part des grilles à 3 bons
numéros monte par rapport à celle à 2. La régression de log(W3/W2) sur les indicatrices des
numéros tirés donne donc, pour chaque numéro, un effet b_n proportionnel à (ρ_n − 1), où ρ_n
est la popularité relative du numéro (1 = numéro moyen). Même construction pour les étoiles
avec (gagnants à 2 étoiles)/(gagnants à 1 étoile), toutes classes de numéros confondues :
numéros et étoiles sont choisis indépendamment sur une grille, les effets se séparent.

Pourquoi c'est la bonne population. Les rangs EuroMillions sont pari-mutuel sur le pool
européen : le partage d'un gain dépend des joueurs européens, pas des seuls joueurs FDJ.
Les gagnants par rang mesurent exactement cette population — et incluent mécaniquement
les grilles Flash (aléatoires), qui diluent les préférences humaines.

Calibration. La pente b ≈ SLOPE × (ρ − 1) est obtenue par simulation (grilles tirées sans
remise avec poids ρ, 400 000 grilles × 400 tirages, voir tools/calibration_r7.py) :
SLOPE_NUMS = 0,259, SLOPE_STARS = 0,660. Linéarisation valable pour ρ dans [0,5 ; 2].

Pur stdlib (le workflow GitHub n'a pas numpy). Régression ridge très légère (λ = 1e-6 sur
les effets, jamais sur l'intercept) pour lever la colinéarité intercept / Σ indicatrices.
"""
import csv, math, os
from collections import Counter

SLOPE_NUMS = 0.259
SLOPE_STARS = 0.660
SINCE_NUMS = "2011-05-10"      # 2 tirages/semaine, rang 2+0 présent à partir de cette date
MIN_DRAWS_NUMS = 300
MIN_DRAWS_STARS = 200
RANKS = [(5, 2), (5, 1), (5, 0), (4, 2), (4, 1), (4, 0), (3, 2), (3, 1), (3, 0),
         (2, 2), (2, 1), (2, 0), (1, 2)]

def load_prizes(path):
    """CSV date;w5_2;…;w1_2 → {date: {(k_num, k_star): winners}} (cases vides ignorées)."""
    out = {}
    if not os.path.exists(path):
        return out
    with open(path, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f, delimiter=";")
        for row in r:
            W = {}
            for n, s in RANKS:
                v = row.get(f"w{n}_{s}", "")
                if v not in ("", None):
                    W[(n, s)] = int(float(v))
            out[row["date"]] = W
    return out

def save_prizes(path, prizes):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter=";", lineterminator="\n")
        w.writerow(["date"] + [f"w{n}_{s}" for n, s in RANKS])
        for d in sorted(prizes):
            w.writerow([d] + [prizes[d].get(r, "") for r in RANKS])

def prizes_from_api_item(it):
    """Ligne de gagnants par rang à partir d'un item de l'API pedromealha."""
    return {(p["matched_numbers"], p["matched_stars"]): int(p["winners"]) for p in it.get("prizes", [])}

# ---------------------------------------------------------------- algèbre (stdlib)

def _solve(A, b):
    """Gauss-Jordan avec pivot partiel. A : liste de listes (n×n), b : liste (n)."""
    n = len(A)
    M = [row[:] + [b[i]] for i, row in enumerate(A)]
    for c in range(n):
        p = max(range(c, n), key=lambda r: abs(M[r][c]))
        M[c], M[p] = M[p], M[c]
        piv = M[c][c]
        if abs(piv) < 1e-14:
            raise ValueError("système singulier")
        inv = 1.0 / piv
        M[c] = [v * inv for v in M[c]]
        for r in range(n):
            if r != c and M[r][c] != 0.0:
                f = M[r][c]
                M[r] = [vr - f * vc for vr, vc in zip(M[r], M[c])]
    return [M[i][n] for i in range(n)]

def _ridge_fit(rows_x, y, k, lam=1e-6):
    """y = a + Σ b_j x_j, rows_x = listes d'indices actifs (indicatrices à 1).
       Retourne (a, b centré, résidus)."""
    n = len(y)
    p = k + 1
    XtX = [[0.0] * p for _ in range(p)]
    Xty = [0.0] * p
    for idx, yy in zip(rows_x, y):
        cols = [0] + [j + 1 for j in idx]
        for a_ in cols:
            Xty[a_] += yy
            for b_ in cols:
                XtX[a_][b_] += 1.0
    for j in range(1, p):
        XtX[j][j] += lam
    beta = _solve(XtX, Xty)
    a, b = beta[0], beta[1:]
    mean_b = sum(b) / k
    b = [v - mean_b for v in b]
    a = a + 5 * mean_b if k == 50 else a + 2 * mean_b   # recentrage sans changer les prédictions
    resid = [yy - a - sum(b[j] for j in idx) for idx, yy in zip(rows_x, y)]
    return a, b, resid

# ---------------------------------------------------------------- estimation

def fit_numbers(prizes, draws, since=SINCE_NUMS):
    """draws : [(date, (5 nums), (2 stars))]. Retourne dict ou None si trop peu de points."""
    by_date = {d: nums for d, nums, _ in draws}
    rows_x, y, cnt = [], [], Counter()
    for d in sorted(prizes):
        if d < since or d not in by_date:
            continue
        W = prizes[d]
        w2 = sum(v for (n, s), v in W.items() if n == 2)
        w3 = sum(v for (n, s), v in W.items() if n == 3)
        if w2 < 10_000 or w3 < 500:
            continue
        idx = [n - 1 for n in by_date[d]]
        rows_x.append(idx); y.append(math.log(w3 / w2)); cnt.update(idx)
    if len(y) < MIN_DRAWS_NUMS:
        return None
    a, b, resid = _ridge_fit(rows_x, y, 50)
    sigma = math.sqrt(sum(r * r for r in resid) / max(1, len(y) - 51))
    var_y = sum((v - sum(y) / len(y)) ** 2 for v in y) / len(y)
    rho = {n: max(0.3, 1.0 + b[n - 1] / SLOPE_NUMS) for n in range(1, 51)}
    se = {n: sigma / math.sqrt(max(1, cnt[n - 1])) / SLOPE_NUMS for n in range(1, 51)}
    return {"rho": rho, "se": se, "n_draws": len(y), "periode": [min(d for d in prizes if d >= since), max(prizes)],
            "intercept": a, "intercept_uniforme": math.log(990 / 14190), "sigma_resid": sigma,
            "r2": 1 - (sigma ** 2) / var_y if var_y > 0 else 0.0}

def fit_stars(prizes, draws, pool=12, star_pool_fn=None):
    by_date = {d: stars for d, _, stars in draws}
    rows_x, y, cnt = [], [], Counter()
    for d in sorted(prizes):
        if d not in by_date:
            continue
        if star_pool_fn is not None and star_pool_fn(d) != pool:
            continue
        W = prizes[d]
        s1 = sum(v for (n, s), v in W.items() if s == 1)
        s2 = sum(v for (n, s), v in W.items() if s == 2)
        if s1 < 10_000 or s2 < 500:
            continue
        idx = [s - 1 for s in by_date[d]]
        rows_x.append(idx); y.append(math.log(s2 / s1)); cnt.update(idx)
    if len(y) < MIN_DRAWS_STARS:
        return None
    a, b, resid = _ridge_fit(rows_x, y, pool)
    sigma = math.sqrt(sum(r * r for r in resid) / max(1, len(y) - pool - 1))
    rho = {s: max(0.3, 1.0 + b[s - 1] / SLOPE_STARS) for s in range(1, pool + 1)}
    se = {s: sigma / math.sqrt(max(1, cnt[s - 1])) / SLOPE_STARS for s in range(1, pool + 1)}
    return {"rho": rho, "se": se, "n_draws": len(y), "sigma_resid": sigma, "pool": pool}

def estimate(prizes_path, draws, star_pool_fn=None):
    """Point d'entrée du pipeline. Retourne une table de popularité prête pour qsc.set_popularity :
       {"source", "nums": {n: ρ}, "stars": {s: ρ}, "meta": {...}}. Dégrade vers None (proxy) si
       le fichier manque ou si l'échantillon est trop court — jamais une exception."""
    prizes = load_prizes(prizes_path)
    if not prizes:
        return None
    fn = fit_numbers(prizes, draws)
    fs = fit_stars(prizes, draws, 12, star_pool_fn)
    if fn is None or fs is None:
        return None
    return {"source": "R7 — gagnants par rang (pool européen)",
            "nums": fn["rho"], "stars": fs["rho"],
            "meta": {"numeros": {k: v for k, v in fn.items() if k not in ("rho",)},
                     "etoiles": {k: v for k, v in fs.items() if k not in ("rho",)},
                     "slope_nums": SLOPE_NUMS, "slope_stars": SLOPE_STARS}}
