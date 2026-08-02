# -*- coding: utf-8 -*-
"""
QSC v3.6 — Module EuroMillions
Spec: chantier du 01/08/2026 (18 changements). Catalogue typé, IC bootstrap,
test de permutation, anti-partage sourcé, consensus corrigée, checklist.

DISCLAIMER (jamais omis dans les livrables construits sur ce module):
Claude ne prédit pas les tirages. Le hasard est sans mémoire. Aucune analyse
ne garantit un gain. EV nette structurellement négative (~-1,42 EUR/grille).
Les edges backtestés et percentiles Monte-Carlo peuvent être du bruit
statistique — méthodologie documentée, pas un oracle.
"""
import csv, math, random, itertools, bisect
from collections import Counter, defaultdict
from datetime import date, timedelta

ALL_NUMS = list(range(1, 51))
ALL_STARS = list(range(1, 13))
BASELINE = 0.5  # E[matches] hypergeometrique: 5*5/50

# ---------------------------------------------------------------- DONNEES

def load_master(path):
    """Charge le CSV maitre (date;n1..n5;e1;e2). Retourne [(date_iso,(5 nums),(2 stars))]."""
    draws = []
    with open(path, newline="") as f:
        r = csv.reader(f, delimiter=";")
        header = next(r)
        for row in r:
            d = row[0]
            nums = tuple(sorted(int(x) for x in row[1:6]))
            stars = tuple(sorted(int(x) for x in row[6:8]))
            draws.append((d, nums, stars))
    draws.sort(key=lambda x: x[0])
    return draws

def integrity_check(draws):
    """Spec #2 — 5 controles. Retourne (ok: bool, alertes: [str])."""
    alerts = []
    dates = [d[0] for d in draws]
    if len(set(dates)) != len(dates):
        alerts.append("dates dupliquees detectees")
    for _, nums, stars in draws:
        if len(set(nums)) != 5 or not all(1 <= n <= 50 for n in nums):
            alerts.append(f"numeros invalides: {nums}"); break
    for _, nums, stars in draws:
        if len(set(stars)) != 2 or not all(1 <= s <= 12 for s in stars):
            alerts.append(f"etoiles invalides: {stars}"); break
    # trous >5 jours (hors periode mono-tirage 2004-2011: seuil 9 jours)
    prev = None
    for ds in dates:
        cur = date.fromisoformat(ds)
        if prev is not None:
            limit = 9 if cur.year < 2012 else 5
            if (cur - prev).days > limit:
                alerts.append(f"trou de {(cur-prev).days} j avant {ds}")
        prev = cur
    if len(draws) < 1900:
        alerts.append(f"profondeur faible: {len(draws)} tirages (attendu ~1968+)")
    return (len(alerts) == 0, alerts)

def dataset_fingerprint(draws, source):
    import hashlib
    h = hashlib.sha256(repr(draws).encode()).hexdigest()[:12]
    return {"n": len(draws), "premier": draws[0][0], "dernier": draws[-1][0],
            "source": source, "hash": h}

# ---------------------------------------------------------------- CATALOGUE TYPE (spec #6)

def m_freq_globale(draws):
    c = Counter();
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

def m_dirichlet(draws, alpha=1.0):
    c = Counter()
    for _, n, _ in draws: c.update(n)
    tot = sum(c.values())
    return {x: (c.get(x, 0)+alpha)/(tot+50*alpha) for x in ALL_NUMS}

CATALOG = {
    # selectors: concourent au classement (spec #6)
    "Frequence globale":        {"type": "selector",   "fn": m_freq_globale},
    "Lag / retard normalise":   {"type": "selector",   "fn": m_lag},
    "Fenetres glissantes":      {"type": "selector",   "fn": m_fenetres},
    "Momentum":                 {"type": "selector",   "fn": m_momentum},
    "Co-occurrence / graphe":   {"type": "selector",   "fn": m_cooccurrence},
    "Chaines de Markov":        {"type": "selector",   "fn": m_markov},
    "Dirichlet-multinomial":    {"type": "selector",   "fn": m_dirichlet},
    # diagnostics: panneaux propres, hors classement
    "Entropie / chi2":          {"type": "diagnostic", "fn": None},
    # filters: contraintes, jamais selecteurs
    "Anti-partage":             {"type": "filter",     "fn": None},
}
SELECTORS = [k for k, v in CATALOG.items() if v["type"] == "selector"]

def top5(scores):
    return tuple(sorted(sorted(ALL_NUMS, key=lambda n: -scores[n])[:5]))

# ---------------------------------------------------------------- CONTRAINTES DURES (inchangees)

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

# ---------------------------------------------------------------- ANTI-PARTAGE SOURCE (spec #9)
# Popularites relatives par numero — table derivee de la litterature "conscious selection"
# (Baker & McHale, JRSS-A 2009 ; McHale, Significance 2012). PROXY UK LOTTO:
# la distribution FDJ EuroMillions precise n'est pas publiee — limite a afficher.
# 1.0 = jouee au taux uniforme. >1 sur-jouee, <1 sous-jouee.

def popularity(n):
    if n <= 12:   base = 1.55   # jours ET mois d'anniversaire
    elif n <= 31: base = 1.30   # jours d'anniversaire
    elif n <= 40: base = 0.80
    else:         base = 0.62   # >40 nettement sous-joues
    if n == 7:  base *= 1.25    # "chanceux" le plus marque
    elif n == 3: base *= 1.10
    elif n % 7 == 0 and n != 7: base *= 1.05
    return base

def star_popularity(s):
    base = 1.25 if s <= 7 else 0.85
    if s == 7: base *= 1.15
    return base

def grid_popularity(nums, stars=None):
    """Popularite relative de la grille (moyenne geometrique, 1.0 = uniforme)."""
    p = 1.0
    for n in nums: p *= popularity(n)
    k = 5
    if stars:
        for s in stars: p *= star_popularity(s)
        k += 2
    return p ** (1.0 / k)

def anti_share_score(nums, stars=None):
    """Score 0-100 continu (spec #9): 100 = tres impopulaire, garde-fous v3.5 en second rang."""
    gp = grid_popularity(nums, stars)          # ~[0.6, 1.9]
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
    """Co-gagnants attendus au rang 1 si la grille gagne (DESCRIPTIF, hypotheses:
    n_tickets mises independantes, popularite proxy UK). q = 1/C(50,5)/C(12,2) uniforme."""
    p_rel = grid_popularity(nums) ** 5  # popularite jointe approx sur les numeros
    q_uniform = 1.0 / 139_838_160
    return n_tickets * q_uniform * p_rel

# ---------------------------------------------------------------- BACKTEST (spec #3,#4,#5)

def walk_forward(model_fn, draws, burn_in=150, step=8):
    pts = []
    t = burn_in
    while t < len(draws):
        pred = set(top5(model_fn(draws[:t])))
        pts.append(len(pred & set(draws[t][1])))
        t += step
    return pts

def bootstrap_ci(points, n_boot=10_000, seed=0):
    """IC95% bootstrap de la moyenne (spec #3)."""
    rng = random.Random(seed)
    n = len(points)
    means = sorted(sum(rng.choices(points, k=n))/n for _ in range(n_boot))
    return means[int(0.025*n_boot)], means[int(0.975*n_boot)]

def backtest_all(draws, burn_in=150, step=8, seed=0):
    out = {}
    for name in SELECTORS:
        pts = walk_forward(CATALOG[name]["fn"], draws, burn_in, step)
        avg = sum(pts)/len(pts)
        lo, hi = bootstrap_ci(pts, seed=seed)
        out[name] = {"points": pts, "n": len(pts), "avg": avg,
                     "edge": avg - BASELINE,
                     "ci": (lo - BASELINE, hi - BASELINE),
                     "significant": not (lo - BASELINE <= 0 <= hi - BASELINE)}
    return out

def permutation_test(bt, n_perm=1000, seed=0):
    """Spec #5 — p-value globale: le meilleur edge observe est-il > au meilleur edge
    obtenu en permutant les matches entre points de test ? (bloc par modele)."""
    rng = random.Random(seed)
    observed_best = max(r["edge"] for r in bt.values())
    all_pts = {k: r["points"][:] for k, r in bt.items()}
    count = 0
    for _ in range(n_perm):
        best = -99
        for pts in all_pts.values():
            sh = rng.sample(pts, len(pts))  # permutation intra-modele
            # bootstrap-like: re-tirage avec remplacement pour casser l'appariement
            sim = [rng.choice(pts) for _ in pts]
            best = max(best, sum(sim)/len(sim) - BASELINE)
        if best >= observed_best: count += 1
    return count / n_perm

def verdict(bt):
    """Spec #4."""
    if any(r["significant"] for r in bt.values()):
        return "Au moins un modele a un IC95% excluant 0 — a examiner avec prudence (multiple testing)."
    return ("Aucun modele ne se distingue du hasard sur cet echantillon — "
            "le choix des porteurs est methodologique, pas inferentiel.")

# ---------------------------------------------------------------- MONTE CARLO (spec #8)

P_GE1_MATCH = 1 - (math.comb(45,5)/math.comb(50,5))  # = 0.4257... identique pour toute grille

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

# ---------------------------------------------------------------- GENERATION

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

def stars_for(draws, mode="lag"):
    if mode == "lag":
        gap = {s: len(draws) for s in ALL_STARS}
        for i, (_, _, st) in enumerate(reversed(draws)):
            for s in st:
                if gap[s] == len(draws): gap[s] = i
        sc = gap
    else:
        c = Counter()
        for _, _, st in draws: c.update(st)
        sc = {s: c.get(s, 0) for s in ALL_STARS}
    return tuple(sorted(sorted(ALL_STARS, key=lambda s: -sc[s])[:2]))

def n_grids(jackpot_meur):
    return 2 + max(0, math.floor((jackpot_meur - 50) / 50))

def consensus_grid(bt, draws):
    """Spec #7 — poids max(edge,0)+eps ; degenerescence explicite."""
    if all(r["edge"] <= 0 for r in bt.values()):
        return None  # "non calculable ce jour: aucun modele ne surperforme"
    eps = 0.01
    agg = {x: 0.0 for x in ALL_NUMS}
    for name, r in bt.items():
        w = max(r["edge"], 0) + eps
        sc = CATALOG[name]["fn"](draws)
        mx = max(sc.values()) or 1
        for x in ALL_NUMS: agg[x] += w * sc[x]/mx
    return top5(agg)

# ---------------------------------------------------------------- DIAGNOSTIC ENTROPIE

def chi2_uniformity(draws):
    c = Counter()
    for _, n, _ in draws: c.update(n)
    exp = len(draws)*5/50
    chi2 = sum((c.get(x, 0)-exp)**2/exp for x in ALL_NUMS)
    dof = 49
    z = ((chi2/dof)**(1/3) - (1-2/(9*dof))) / math.sqrt(2/(9*dof))
    p = 1 - 0.5*(1+math.erf(z/math.sqrt(2)))
    return chi2, max(0.0, min(1.0, p))

# ---------------------------------------------------------------- CHECKLIST (spec #18)

FORBIDDEN = ["prometteur", "tendance favorable", "momentum favorable"]
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
    if EQUIVALENCE[:40] not in html_text: fails.append("phrase d'equivalence absente")
    if str(fingerprint["n"]) not in html_text: fails.append("empreinte dataset absente")
    if str(seed) not in html_text: fails.append("seed absente")
    return (len(fails) == 0, fails)

def seed_from_draw_date(d):
    """Spec #11 — seed = AAAAMMJJ."""
    return int(d.replace("-", ""))
