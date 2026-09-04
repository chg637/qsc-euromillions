# -*- coding: utf-8 -*-
"""
QSC v3.7 — Module EuroMillions
Chantier du 04/09/2026. Changements vs v3.6 :
  C1  test de significativité corrigé : null hypergéométrique exact + max-statistic
      (correction des tests multiples) — l'ancien "test de permutation" comparait
      l'observé à un ré-échantillonnage de lui-même.
  C2  walk-forward step=1 (1 818 points de test au lieu de 228).
  C3  Dirichlet-multinomial retiré du catalogue (classement identique à Fréquence globale).
  C4  consensus dégénère dès qu'aucun modèle n'est significatif après correction.
  C5  étoiles backtestées (3 modèles, baseline 1/3) avec le même protocole.
  C6  registre / rotation narrative / rapprochement portés dans run_qsc.py.

DISCLAIMER (jamais omis dans les livrables construits sur ce module):
Claude ne prédit pas les tirages. Le hasard est sans mémoire. Aucune analyse
ne garantit un gain. EV nette structurellement négative (~-1,42 EUR/grille).
Les edges backtestés et percentiles Monte-Carlo peuvent être du bruit
statistique — méthodologie documentée, pas un oracle.
"""
import csv, math, random, itertools, bisect, hashlib
from collections import Counter, defaultdict
from datetime import date, timedelta

VERSION = "3.7"
ALL_NUMS = list(range(1, 51))
ALL_STARS = list(range(1, 13))
BASELINE = 5 * 5 / 50            # E[matches numéros] hypergéométrique = 0.5
STAR_BASELINE = 2 * 2 / 12       # E[matches étoiles] = 0.333...

# ---------------------------------------------------------------- DONNEES

def load_master(path):
    """Charge le CSV maître (date;n1..n5;e1;e2). Retourne [(date_iso,(5 nums),(2 stars))]."""
    draws = []
    with open(path, newline="", encoding="utf-8") as f:
        r = csv.reader(f, delimiter=";")
        next(r)
        for row in r:
            if not row or not row[0].strip():
                continue
            nums = tuple(sorted(int(x) for x in row[1:6]))
            stars = tuple(sorted(int(x) for x in row[6:8]))
            draws.append((row[0], nums, stars))
    draws.sort(key=lambda x: x[0])
    return draws

def save_master(path, draws):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter=";", lineterminator="\n")
        w.writerow(["date", "n1", "n2", "n3", "n4", "n5", "e1", "e2"])
        for d, nums, stars in sorted(draws):
            w.writerow([d, *nums, *stars])

def integrity_check(draws):
    """5 contrôles. Retourne (ok, alertes)."""
    alerts = []
    dates = [d[0] for d in draws]
    if len(set(dates)) != len(dates):
        alerts.append("dates dupliquées détectées")
    for _, nums, stars in draws:
        if len(set(nums)) != 5 or not all(1 <= n <= 50 for n in nums):
            alerts.append(f"numéros invalides: {nums}"); break
    for _, nums, stars in draws:
        if len(set(stars)) != 2 or not all(1 <= s <= 12 for s in stars):
            alerts.append(f"étoiles invalides: {stars}"); break
    prev = None
    for ds in dates:
        cur = date.fromisoformat(ds)
        if prev is not None:
            limit = 9 if cur.year < 2012 else 5
            if (cur - prev).days > limit:
                alerts.append(f"trou de {(cur-prev).days} j avant {ds}")
        prev = cur
    if len(draws) < 1900:
        alerts.append(f"profondeur faible: {len(draws)} tirages")
    return (len(alerts) == 0, alerts)

def dataset_fingerprint(draws, source):
    h = hashlib.sha256(repr(draws).encode()).hexdigest()[:12]
    return {"n": len(draws), "premier": draws[0][0], "dernier": draws[-1][0],
            "source": source, "hash": h}

# ---------------------------------------------------------------- CATALOGUE TYPÉ — NUMÉROS

def m_freq_globale(draws):
    c = Counter()
    for _, n, _ in draws: c.update(n)
    return {x: c.get(x, 0) for x in ALL_NUMS}

def m_lag(draws):
    gap = {x: len(draws) for x in ALL_NUMS}
    for i, (_, nums, _) in enumerate(reversed(draws)):
        for x in nums:
            if gap[x] == len(draws): gap[x] = i
    return {x: gap[x] / 10.0 for x in ALL_NUMS}

def m_fenetres(draws, windows=(10, 20, 30)):
    s = {x: 0.0 for x in ALL_NUMS}
    for w in windows:
        c = Counter()
        for _, n, _ in draws[-w:]: c.update(n)
        tot = sum(c.values()) or 1
        for x in ALL_NUMS: s[x] += c.get(x, 0) / tot / len(windows)
    return s

def m_momentum(draws, recent=10, prior=10):
    cr, cp = Counter(), Counter()
    for _, n, _ in draws[-recent:]: cr.update(n)
    for _, n, _ in draws[-(recent+prior):-recent]: cp.update(n)
    return {x: cr.get(x, 0)/recent - cp.get(x, 0)/prior for x in ALL_NUMS}

def m_cooccurrence(draws):
    if not draws: return {x: 0.0 for x in ALL_NUMS}
    last = set(draws[-1][1]); co = defaultdict(float)
    for _, nums, _ in draws:
        inter = set(nums) & last
        if inter:
            for x in nums:
                if x not in last: co[x] += len(inter)
    return {x: co.get(x, 0.0) for x in ALL_NUMS}

def m_markov(draws):
    tc = defaultdict(lambda: defaultdict(int)); occ = defaultdict(int)
    for i in range(len(draws)-1):
        nxt = set(draws[i+1][1])
        for m in draws[i][1]:
            occ[m] += 1
            for n in nxt: tc[m][n] += 1
    s = {x: 0.0 for x in ALL_NUMS}
    if not draws: return s
    for m in draws[-1][1]:
        if occ[m]:
            for x in ALL_NUMS: s[x] += tc[m].get(x, 0) / occ[m]
    return s

CATALOG = {
    "Fréquence globale":        {"type": "selector",   "fn": m_freq_globale},
    "Lag / retard normalisé":   {"type": "selector",   "fn": m_lag},
    "Fenêtres glissantes":      {"type": "selector",   "fn": m_fenetres},
    "Momentum":                 {"type": "selector",   "fn": m_momentum},
    "Co-occurrence / graphe":   {"type": "selector",   "fn": m_cooccurrence},
    "Chaînes de Markov":        {"type": "selector",   "fn": m_markov},
    "Entropie / chi2":          {"type": "diagnostic", "fn": None},
    "Anti-partage":             {"type": "filter",     "fn": None},
}
SELECTORS = [k for k, v in CATALOG.items() if v["type"] == "selector"]

def top5(scores):
    return tuple(sorted(sorted(ALL_NUMS, key=lambda n: -scores[n])[:5]))

# ---------------------------------------------------------------- CATALOGUE — ÉTOILES (C5)
# Le pool d'étoiles a changé : 9 (2004→06/05/2011), 11 (10/05/2011→23/09/2016), 12 depuis
# le 27/09/2016. Baseline, candidats et null sont indexés sur le pool en vigueur à chaque
# tirage — sinon tout modèle "fréquence" hérite d'un faux edge (étoiles 10-12 inexistantes).

def star_pool(date_iso):
    if date_iso < "2011-05-10": return 9
    if date_iso < "2016-09-27": return 11
    return 12

def star_baseline(pool):
    return 2 * 2 / pool

def _stars_of(pool):
    return list(range(1, pool + 1))

def s_freq(draws, pool=12):
    c = Counter()
    for _, _, st in draws: c.update(st)
    return {s: c.get(s, 0) for s in _stars_of(pool)}

def s_lag(draws, pool=12):
    stars = _stars_of(pool)
    gap = {s: len(draws) for s in stars}
    for i, (_, _, st) in enumerate(reversed(draws)):
        for s in st:
            if s in gap and gap[s] == len(draws): gap[s] = i
    return {s: float(gap[s]) for s in stars}

def s_fenetres(draws, pool=12, windows=(10, 20, 30)):
    stars = _stars_of(pool)
    sc = {s: 0.0 for s in stars}
    for w in windows:
        c = Counter()
        for _, _, st in draws[-w:]: c.update(st)
        tot = sum(c.values()) or 1
        for s in stars: sc[s] += c.get(s, 0) / tot / len(windows)
    return sc

STAR_CATALOG = {
    "Étoiles — fréquence":  s_freq,
    "Étoiles — lag":        s_lag,
    "Étoiles — fenêtres":   s_fenetres,
}

def top2_stars(scores):
    return tuple(sorted(sorted(scores, key=lambda s: -scores[s])[:2]))

# ---------------------------------------------------------------- CONTRAINTES DURES

def hard_ok(nums):
    s = sorted(nums)
    if not (95 <= sum(s) <= 155): return False
    ev = sum(1 for n in s if n % 2 == 0)
    if not (2 <= ev <= 3): return False
    low = sum(1 for n in s if n <= 25)
    if not (2 <= low <= 3): return False
    if any(s[i+1]-s[i] < 3 for i in range(4)): return False
    return True

def overlap(a, b):
    return len(set(a) & set(b))

# ---------------------------------------------------------------- ANTI-PARTAGE SOURCÉ
# Popularités relatives — proxy UK Lotto (Baker & McHale 2009 ; McHale 2012).
# La distribution FDJ EuroMillions n'est pas publiée : limite à afficher.

def popularity(n):
    if n <= 12:   base = 1.55
    elif n <= 31: base = 1.30
    elif n <= 40: base = 0.80
    else:         base = 0.62
    if n == 7:  base *= 1.25
    elif n == 3: base *= 1.10
    elif n % 7 == 0 and n != 7: base *= 1.05
    return base

def star_popularity(s):
    base = 1.25 if s <= 7 else 0.85
    if s == 7: base *= 1.15
    return base

def grid_popularity(nums, stars=None):
    p = 1.0
    for n in nums: p *= popularity(n)
    k = 5
    if stars:
        for s in stars: p *= star_popularity(s)
        k += 2
    return p ** (1.0 / k)

def anti_share_score(nums, stars=None):
    """Score 0-100 continu : 100 = très impopulaire."""
    gp = grid_popularity(nums, stars)
    score = 100.0 * max(0.0, min(1.0, (1.75 - gp) / 1.0))
    s = sorted(nums)
    if all(n <= 31 for n in s): score -= 15
    if sum(1 for n in s if n % 5 == 0) >= 3: score -= 10
    runs = max(len(list(g)) for _, g in itertools.groupby(enumerate(s), lambda t: t[1]-t[0]))
    if runs >= 3: score -= 15
    diffs = {s[i+1]-s[i] for i in range(4)}
    if len(diffs) == 1: score -= 15
    if len({n % 10 for n in s}) == 1: score -= 10
    return max(0.0, min(100.0, score))

def expected_cowinners(nums, n_tickets=25_000_000):
    """Co-gagnants attendus au rang 1 si la grille gagne (descriptif, proxy UK)."""
    p_rel = grid_popularity(nums) ** 5
    q_uniform = 1.0 / 139_838_160
    return n_tickets * q_uniform * p_rel

# ---------------------------------------------------------------- BACKTEST (C1, C2)

def walk_forward(model_fn, draws, burn_in=150, step=1):
    """Numéros : matches du top-5 prédit contre le tirage t, t = burn_in, burn_in+step, ..."""
    pts = []
    t = burn_in
    while t < len(draws):
        pred = set(top5(model_fn(draws[:t])))
        pts.append(len(pred & set(draws[t][1])))
        t += step
    return pts

def walk_forward_stars(model_fn, draws, burn_in=150, step=1):
    """Étoiles : le modèle ne voit que le pool en vigueur au tirage t.
       Retourne (matches, excès vs baseline du pool, pool) par point."""
    pts, excess, pools = [], [], []
    t = burn_in
    while t < len(draws):
        pool = star_pool(draws[t][0])
        pred = set(top2_stars(model_fn(draws[:t], pool)))
        m = len(pred & set(draws[t][2]))
        pts.append(m); excess.append(m - star_baseline(pool)); pools.append(pool)
        t += step
    return pts, excess, pools

def bootstrap_ci(points, n_boot=10_000, seed=0):
    rng = random.Random(seed)
    n = len(points)
    means = sorted(sum(rng.choices(points, k=n))/n for _ in range(n_boot))
    return means[int(0.025*n_boot)], means[int(0.975*n_boot)]

def hypergeom_pmf(N=50, K=5, k_draw=5):
    """P(X=k) pour X = |grille aléatoire ∩ tirage|."""
    tot = math.comb(N, k_draw)
    return [math.comb(K, k) * math.comb(N-K, k_draw-k) / tot for k in range(k_draw+1)]

def null_distribution(groups, n_models, n_sim=5000, seed=0):
    """C1 — Distribution sous H0 (grilles indépendantes des tirages) de l'edge moyen :
       (a) d'un modèle seul ; (b) du MAX parmi n_models modèles indépendants
       (max-statistic = correction des tests multiples).
       groups = [(n_points, N, K, k_draw), ...] : chaque groupe de points a sa loi
       hypergéométrique (numéros : un seul groupe ; étoiles : un groupe par pool).
       Exact sous H0 : chaque point est hypergéométrique quel que soit le modèle."""
    rng = random.Random(seed)
    specs = []
    n_total = 0
    for n_pts, N, K, k in groups:
        pmf = hypergeom_pmf(N, K, k)
        base = sum(j * p for j, p in enumerate(pmf))
        specs.append((n_pts, list(range(len(pmf))), pmf, base)); n_total += n_pts
    single, maxes = [], []
    for _ in range(n_sim):
        best = -9
        for m in range(n_models):
            tot = 0.0
            for n_pts, ks, pmf, base in specs:
                tot += sum(rng.choices(ks, weights=pmf, k=n_pts)) - base * n_pts
            e = tot / n_total
            if m == 0: single.append(e)
            best = max(best, e)
        maxes.append(best)
    single.sort(); maxes.sort()
    return {"single": single, "max": maxes}

def p_value_from_null(observed, sorted_null):
    """P(null >= observed), plancher 1/(n+1)."""
    n = len(sorted_null)
    return max(1, n - bisect.bisect_left(sorted_null, observed)) / (n + 1)

def backtest_all(draws, burn_in=150, step=1, seed=0, n_sim=5000):
    """Backtest des 6 selectors numéros + null exact + max-statistic."""
    out = {}
    for name in SELECTORS:
        pts = walk_forward(CATALOG[name]["fn"], draws, burn_in, step)
        avg = sum(pts)/len(pts)
        lo, hi = bootstrap_ci(pts, seed=seed)
        out[name] = {"points": pts, "n": len(pts), "avg": avg, "edge": avg - BASELINE,
                     "ci": (lo - BASELINE, hi - BASELINE)}
    n_pts = out[SELECTORS[0]]["n"]
    null = null_distribution([(n_pts, 50, 5, 5)], len(SELECTORS), n_sim=n_sim, seed=seed)
    for name, r in out.items():
        r["p_raw"] = p_value_from_null(r["edge"], null["single"])
        r["p_adj"] = p_value_from_null(r["edge"], null["max"])   # corrigé multiple testing
        r["significant"] = r["p_adj"] < 0.05
    best = max(out.values(), key=lambda r: r["edge"])["edge"]
    meta = {"burn_in": burn_in, "step": step, "n_points": n_pts, "n_models": len(SELECTORS),
            "n_sim": n_sim, "best_edge": best,
            "p_global": p_value_from_null(best, null["max"]),
            "null_max_q95": null["max"][int(0.95*len(null["max"]))]}
    return out, meta

def backtest_stars(draws, burn_in=150, step=1, seed=0, n_sim=5000):
    """C5 — même protocole pour les étoiles, baseline et null indexés sur le pool (9/11/12)."""
    out = {}
    pools = None
    for name, fn in STAR_CATALOG.items():
        pts, excess, pools = walk_forward_stars(fn, draws, burn_in, step)
        edge = sum(excess)/len(excess)
        lo, hi = bootstrap_ci(excess, seed=seed)
        out[name] = {"points": pts, "n": len(pts), "avg": sum(pts)/len(pts), "edge": edge,
                     "ci": (lo, hi)}
    n_pts = len(pools)
    groups = [(pools.count(p), p, 2, 2) for p in sorted(set(pools))]
    null = null_distribution(groups, len(STAR_CATALOG), n_sim=n_sim, seed=seed)
    for name, r in out.items():
        r["p_raw"] = p_value_from_null(r["edge"], null["single"])
        r["p_adj"] = p_value_from_null(r["edge"], null["max"])
        r["significant"] = r["p_adj"] < 0.05
    best = max(out.values(), key=lambda r: r["edge"])["edge"]
    meta = {"n_points": n_pts, "n_models": len(STAR_CATALOG), "best_edge": best,
            "p_global": p_value_from_null(best, null["max"])}
    return out, meta

def verdict(bt, meta):
    if any(r["significant"] for r in bt.values()):
        return ("Au moins un modèle reste significatif après correction des tests multiples "
                f"(p global = {meta['p_global']:.3f}) — à examiner avec prudence : un seul échantillon.")
    return ("Aucun modèle ne se distingue du hasard sur cet échantillon "
            f"(p global = {meta['p_global']:.2f}) — le choix des porteurs est méthodologique, pas inférentiel.")

# ---------------------------------------------------------------- MONTE CARLO

P_GE1_MATCH = 1 - (math.comb(45,5)/math.comb(50,5))  # 0.4234, identique pour toute grille

def monte_carlo(draws, n=50_000, seed=0):
    rng = random.Random(seed)
    res = []
    for _ in range(n):
        g = set(rng.sample(ALL_NUMS, 5))
        tot = sum(len(g & set(nums)) for _, nums, _ in draws)
        res.append(tot/len(draws))
    res.sort()
    return res

def mc_percentile(grid, draws, mc_sorted):
    avg = sum(len(set(grid) & set(n)) for _, n, _ in draws)/len(draws)
    return avg, 100.0*bisect.bisect_left(mc_sorted, avg)/len(mc_sorted)

def mc_histogram(mc_sorted, bins=30):
    lo, hi = mc_sorted[0], mc_sorted[-1]
    w = (hi - lo) / bins or 1
    counts = [0]*bins
    for v in mc_sorted:
        i = min(bins-1, int((v - lo) / w)); counts[i] += 1
    return {"lo": lo, "hi": hi, "width": w, "counts": counts}

# ---------------------------------------------------------------- GÉNÉRATION

def best_grid(model_name, draws, pool=16, avoid=None, max_ov=2, min_as=60):
    scores = CATALOG[model_name]["fn"](draws)
    cand = sorted(ALL_NUMS, key=lambda n: -scores[n])[:pool]
    best, key = None, None
    for combo in itertools.combinations(cand, 5):
        if not hard_ok(combo): continue
        a = anti_share_score(combo)
        if a < min_as: continue
        if avoid and any(overlap(combo, g) > max_ov for g in avoid): continue
        k = (sum(scores[n] for n in combo), a)
        if key is None or k > key: best, key = combo, k
    return tuple(sorted(best)) if best else None

def stars_for(draws, model="Étoiles — lag", pool=12):
    return top2_stars(STAR_CATALOG[model](draws, pool))

def n_grids(jackpot_meur):
    return 2 + max(0, math.floor((jackpot_meur - 50) / 50))

def consensus_grid(bt, draws):
    """C4 — dégénère (None) dès qu'aucun modèle n'est significatif après correction.
       Sinon pondère par max(edge,0)+eps sur les seuls modèles significatifs."""
    sig = {k: r for k, r in bt.items() if r.get("significant")}
    if not sig:
        return None
    eps = 0.01
    agg = {x: 0.0 for x in ALL_NUMS}
    for name, r in sig.items():
        w = max(r["edge"], 0) + eps
        sc = CATALOG[name]["fn"](draws)
        mx = max(sc.values()) or 1
        for x in ALL_NUMS: agg[x] += w * sc[x]/mx
    return top5(agg)

def rank_selectors(bt, ineligible_first=None):
    """Classement méthodologique (edge décroissant) ; le porteur #1 du run précédent
       est inéligible comme #1 (rotation narrative) — il redescend en 2e position."""
    order = sorted(bt, key=lambda k: -bt[k]["edge"])
    if ineligible_first and order and order[0] == ineligible_first and len(order) > 1:
        order[0], order[1] = order[1], order[0]
    return order

# ---------------------------------------------------------------- DIAGNOSTIC

def chi2_uniformity(draws):
    c = Counter()
    for _, n, _ in draws: c.update(n)
    exp = len(draws)*5/50
    chi2 = sum((c.get(x, 0)-exp)**2/exp for x in ALL_NUMS)
    dof = 49
    z = ((chi2/dof)**(1/3) - (1-2/(9*dof))) / math.sqrt(2/(9*dof))
    p = 1 - 0.5*(1+math.erf(z/math.sqrt(2)))
    return chi2, max(0.0, min(1.0, p))

# ---------------------------------------------------------------- CALENDRIER / SEED

def next_draw_date(today):
    """Prochain tirage (mardi=1, vendredi=4), aujourd'hui inclus."""
    d = today
    while d.weekday() not in (1, 4):
        d += timedelta(days=1)
    return d

def seed_from_draw_date(d):
    return int(d.replace("-", ""))

# ---------------------------------------------------------------- CHECKLIST

FORBIDDEN = ["prometteur", "tendance favorable", "momentum favorable", "numéro gagnant",
             "va sortir", "bonne chance"]
DISCLAIMER = ("Claude ne prédit pas les tirages. Le hasard est sans mémoire. "
              "Aucune analyse ne garantit un gain. EV nette structurellement négative "
              "(~−1,42 €/grille). Les edges backtestés et percentiles Monte-Carlo peuvent "
              "être du bruit statistique — méthodologie documentée, pas un oracle.")
EQUIVALENCE = ("Toutes les grilles ci-dessus ont exactement la même probabilité de gain : "
               "1/139 838 160 au rang 1. Le pipeline choisit comment jouer, jamais mieux jouer.")

def checklist(html_text, chat_text, fingerprint, seed):
    fails = []
    if html_text.count("Claude ne prédit pas les tirages") < 1: fails.append("disclaimer HTML absent")
    if chat_text.count("Claude ne prédit pas les tirages") < 2: fails.append("disclaimer chat <2 occurrences")
    low = (html_text + chat_text).lower()
    for w in FORBIDDEN:
        if w in low: fails.append(f"lexique interdit: {w}")
    if EQUIVALENCE[:40] not in html_text: fails.append("phrase d'équivalence absente")
    if str(fingerprint["n"]) not in html_text: fails.append("empreinte dataset absente")
    if str(seed) not in html_text: fails.append("seed absente")
    return (len(fails) == 0, fails)
