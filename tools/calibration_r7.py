# -*- coding: utf-8 -*-
"""Outil hors pipeline (numpy) — calibration des pentes SLOPE_NUMS / SLOPE_STARS de popularite.py
et contrôle croisé de l'estimateur stdlib. Usage : python3 tools/calibration_r7.py <dossier des JSON annuels de l'API>

R7 — estimation de la popularité des numéros/étoiles à partir des gagnants par rang.
Principe : W_k(t) = N_t × e_k(S_t). Le ratio W3/W2 élimine N_t (ventes inconnues) et ne
dépend que de la popularité des 5 numéros tirés. Régression de log(W3/W2) sur les
indicatrices des numéros tirés → effet relatif par numéro. Idem étoiles avec
(gagnants à 2 étoiles)/(gagnants à 1 étoile), toutes classes de numéros confondues."""
import json, glob, math, sys, os, random
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import qsc_v39 as q

API_DIR = sys.argv[1] if len(sys.argv) > 1 else "api_json"
rows = []
for f in sorted(glob.glob(API_DIR + "/*.json")):
    for it in json.load(open(f)):
        if not it.get("prizes"): continue
        W = {}
        for p in it["prizes"]:
            W[(p["matched_numbers"], p["matched_stars"])] = p["winners"]
        nums = tuple(sorted(int(x) for x in it["numbers"]))
        stars = tuple(sorted(int(x) for x in it["stars"]))
        rows.append((it["date"], nums, stars, W))
rows.sort()
print("tirages avec gagnants par rang :", len(rows), rows[0][0], "→", rows[-1][0])

def wk(W, k): return sum(v for (n, s), v in W.items() if n == k)
def ws(W, s): return sum(v for (n, st), v in W.items() if st == s)

def fit_numbers(sub, label):
    X, y = [], []
    for d, nums, stars, W in sub:
        w2, w3 = wk(W, 2), wk(W, 3)
        if w2 < 10000 or w3 < 500: continue
        x = np.zeros(50); x[[n - 1 for n in nums]] = 1
        X.append(x); y.append(math.log(w3 / w2))
    X = np.array(X); y = np.array(y)
    # modèle : y = a + Σ b_n x_n ; contrainte Σ b_n = 0 (centrage) via pénalité ridge légère
    A = np.hstack([np.ones((len(y), 1)), X])
    lam = 1e-3
    P = np.eye(51) * lam; P[0, 0] = 0
    beta = np.linalg.solve(A.T @ A + P, A.T @ y)
    resid = y - A @ beta
    b = beta[1:] - beta[1:].mean()
    sig2 = resid.var() * len(y) / (len(y) - 51)
    cov = sig2 * np.linalg.inv(A.T @ A + P)
    se = np.sqrt(np.diag(cov))[1:]
    print(f"\n[{label}] n={len(y)}  R²={1 - resid.var() / y.var():.3f}  σ_resid={resid.std():.4f}  "
          f"intercept={beta[0]:.4f} (uniforme théorique log(h3/h2)={math.log(990 / 14190):.4f})")
    return b, se, len(y)

def fit_stars(sub, label, pool):
    X, y = [], []
    for d, nums, stars, W in sub:
        if q.star_pool(d) != pool: continue
        s1, s2 = ws(W, 1), ws(W, 2)
        if s1 < 10000 or s2 < 500: continue
        x = np.zeros(pool); x[[s - 1 for s in stars]] = 1
        X.append(x); y.append(math.log(s2 / s1))
    X = np.array(X); y = np.array(y)
    A = np.hstack([np.ones((len(y), 1)), X])
    lam = 1e-3
    P = np.eye(pool + 1) * lam; P[0, 0] = 0
    beta = np.linalg.solve(A.T @ A + P, A.T @ y)
    resid = y - A @ beta
    b = beta[1:] - beta[1:].mean()
    sig2 = resid.var() * len(y) / (len(y) - pool - 1)
    se = np.sqrt(np.diag(sig2 * np.linalg.inv(A.T @ A + P)))[1:]
    print(f"\n[{label}] n={len(y)}  R²={1 - resid.var() / y.var():.3f}  σ_resid={resid.std():.4f}")
    return b, se, len(y)

# ---------------------------------------------------------------- calibration b → ρ par simulation
def simulate_calibration(rho, n_draws=400, n_tickets=400_000, seed=1):
    """Tickets = 5 numéros tirés sans remise avec poids rho. Mesure log(W3/W2) pour des S
    aléatoires, régresse, renvoie la pente b vs (rho-1)."""
    rng = np.random.default_rng(seed)
    p = np.array(rho) / np.sum(rho)
    # tickets : échantillonnage pondéré sans remise (Efraimidis-Spirakis)
    keys = rng.random((n_tickets, 50)) ** (1.0 / p)
    tickets = np.argsort(-keys, axis=1)[:, :5]           # indices 0..49
    T = np.zeros((n_tickets, 50), dtype=np.int8)
    np.put_along_axis(T, tickets, 1, axis=1)
    X, y = [], []
    for _ in range(n_draws):
        S = rng.choice(50, 5, replace=False)
        m = T[:, S].sum(axis=1)
        w2, w3 = np.sum(m == 2), np.sum(m == 3)
        x = np.zeros(50); x[S] = 1
        X.append(x); y.append(math.log(w3 / w2))
    X = np.array(X); y = np.array(y)
    A = np.hstack([np.ones((len(y), 1)), X])
    P = np.eye(51) * 1e-3; P[0, 0] = 0
    beta = np.linalg.solve(A.T @ A + P, A.T @ y)
    b = beta[1:] - beta[1:].mean()
    d = np.array(rho) / np.mean(rho) - 1
    slope = np.sum(b * d) / np.sum(d * d)
    return slope, np.corrcoef(b, d)[0, 1]

if __name__ == "__main__":
    post2011 = [r for r in rows if r[0] >= "2011-05-10"]
    b_all, se_all, n_all = fit_numbers(post2011, "numéros 2011→2026")
    b_a, _, _ = fit_numbers([r for r in post2011 if r[0] < "2019-01-01"], "numéros 2011→2018")
    b_b, _, _ = fit_numbers([r for r in post2011 if r[0] >= "2019-01-01"], "numéros 2019→2026")
    print("stabilité temporelle (corr. des effets 2011-18 vs 2019-26) :", round(np.corrcoef(b_a, b_b)[0, 1], 3))

    # calibration
    uk = np.array([q.popularity_proxy_uk(n) for n in q.ALL_NUMS])
    slope, corr = simulate_calibration(uk)
    print(f"\ncalibration simulée (proxy UK en entrée) : b ≈ {slope:.3f} × (ρ−1), corr {corr:.3f}")
    rho_hat = 1 + b_all / slope
    rho_uk = uk / uk.mean()
    print("\n n  | ρ̂ FDJ-EU (données) | ρ UK proxy | b   (±se)")
    for n in q.ALL_NUMS:
        i = n - 1
        print(f"{n:3d} | {rho_hat[i]:6.2f}            | {rho_uk[i]:5.2f}     | {b_all[i]:+.4f} (±{se_all[i]:.4f})")
    print("\ncorr(ρ̂ données, ρ proxy UK) =", round(np.corrcoef(rho_hat, rho_uk)[0, 1], 3))
    print("ρ̂ min/max =", rho_hat.min().round(2), rho_hat.max().round(2), " | proxy UK min/max =", rho_uk.min().round(2), rho_uk.max().round(2))
    # moyennes par tranche
    for lo, hi in [(1, 12), (13, 31), (32, 40), (41, 50)]:
        sel = slice(lo - 1, hi)
        print(f"tranche {lo:2d}-{hi:2d} : ρ̂ moyen {rho_hat[sel].mean():.2f}   proxy {rho_uk[sel].mean():.2f}")

    # étoiles pool 12
    bs, ses, ns = fit_stars(rows, "étoiles 2016→2026 (pool 12)", 12)
    uks = np.array([q.star_popularity_proxy_uk(s) for s in q.ALL_STARS])
    # calibration étoiles : 2 parmi 12 — même simulation adaptée
    def sim_stars(rho, n_draws=400, n_tickets=400_000, seed=2):
        rng = np.random.default_rng(seed); p = np.array(rho) / np.sum(rho)
        keys = rng.random((n_tickets, 12)) ** (1.0 / p)
        tk = np.argsort(-keys, axis=1)[:, :2]
        T = np.zeros((n_tickets, 12), dtype=np.int8); np.put_along_axis(T, tk, 1, axis=1)
        X, y = [], []
        for _ in range(n_draws):
            S = rng.choice(12, 2, replace=False); m = T[:, S].sum(axis=1)
            x = np.zeros(12); x[S] = 1; X.append(x); y.append(math.log(np.sum(m == 2) / np.sum(m == 1)))
        X = np.array(X); y = np.array(y); A = np.hstack([np.ones((len(y), 1)), X])
        P = np.eye(13) * 1e-3; P[0, 0] = 0
        beta = np.linalg.solve(A.T @ A + P, A.T @ y); b = beta[1:] - beta[1:].mean()
        d = np.array(rho) / np.mean(rho) - 1
        return np.sum(b * d) / np.sum(d * d)
    sl_s = sim_stars(uks)
    rho_s = 1 + bs / sl_s
    print(f"calibration étoiles : b ≈ {sl_s:.3f} × (ρ−1)")
    print("\n ★ | ρ̂ données | ρ proxy UK | b (±se)")
    for s in q.ALL_STARS:
        print(f"{s:2d} | {rho_s[s-1]:5.2f}     | {uks[s-1]/uks.mean():5.2f}      | {bs[s-1]:+.4f} (±{ses[s-1]:.4f})")
    print("corr étoiles (données vs proxy) =", round(np.corrcoef(rho_s, uks)[0, 1], 3))

    json.dump({"rho_nums": {str(n): round(float(rho_hat[n-1]), 4) for n in q.ALL_NUMS},
               "rho_stars": {str(s): round(float(rho_s[s-1]), 4) for s in q.ALL_STARS},
               "n_draws_nums": n_all, "n_draws_stars": ns, "slope_nums": slope, "slope_stars": sl_s},
              open("rho_estime.json", "w"), indent=1)
