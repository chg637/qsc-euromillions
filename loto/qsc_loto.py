# -*- coding: utf-8 -*-
"""
QSC Loto v1.0 — Module Loto FDJ (5 numéros sur 49 + 1 numéro Chance sur 10, règle en vigueur
depuis le 06/10/2008 ; tirages lundi, mercredi, samedi).

Transposition directe du protocole QSC EuroMillions v3.9 :
  - six selectors backtestés en walk-forward (step 1), null hypergéométrique exacte, max-statistic ;
  - popularité des numéros ESTIMÉE sur les gagnants par rang FDJ (ratio gagnants à 3 numéros /
    gagnants à 2 numéros, toutes classes Chance confondues), popularité du numéro Chance estimée
    sur le ratio (k numéros + Chance) / (k numéros sans Chance), rangs 3/4, 5/6, 7/8 (règle 2017+) ;
  - univers de sélection = décile le moins populaire des C(49,5) = 1 906 884 grilles, hors motifs
    sur-joués ; le porteur ne fait que départager dedans ; numéro Chance dans le tiers le moins joué ;
  - consensus stricte (dégénère sans modèle significatif), rotation narrative, registre append-only.

Rangs FDJ. Règle 2008-2017 (6 rangs) : 1 = 5+C, 2 = 5, 3 = 4 (avec ou sans C), 4 = 3, 5 = 2, 6 = C seul.
Règle 2017+ (9 rangs) : 1 = 5+C, 2 = 5, 3 = 4+C, 4 = 4, 5 = 3+C, 6 = 3, 7 = 2+C, 8 = 2, 9 = C seul.
Les gagnants « 3 numéros » et « 2 numéros » existent dans les deux règles → 2 800+ tirages pour les
numéros ; les ratios avec/sans Chance n'existent que depuis 2017 → ~1 500 tirages pour la Chance.

DISCLAIMER (jamais omis dans les livrables construits sur ce module) :
Claude ne prédit pas les tirages. Le hasard est sans mémoire. Aucune analyse ne garantit un gain.
EV nette structurellement négative. Les edges backtestés peuvent être du bruit statistique —
méthodologie documentée, pas un oracle.
"""
import csv, math, random, itertools, bisect, hashlib, os
from collections import Counter, defaultdict
from datetime import date, timedelta

VERSION = "1.0"
GAME = "Loto"
N_POOL, K_PICK = 49, 5
ALL_NUMS = list(range(1, N_POOL + 1))
ALL_CHANCE = list(range(1, 11))
BASELINE = K_PICK * K_PICK / N_POOL          # E[matches] grille aléatoire = 25/49 ≈ 0,510
CHANCE_BASELINE = 1 / 10
N_COMBOS = math.comb(N_POOL, K_PICK)          # 1 906 884
P_RANG1 = 1 / (N_COMBOS * 10)                 # 1/19 068 840
PRIX_GRILLE = 2.20
DRAW_WEEKDAYS = (0, 2, 5)                     # lundi, mercredi, samedi

# ---------------------------------------------------------------- DONNÉES

def load_master(path):
    """CSV date;n1..n5;chance → [(date_iso, (5 nums), chance)]."""
    draws = []
    with open(path, newline="", encoding="utf-8") as f:
        r = csv.reader(f, delimiter=";"); next(r)
        for row in r:
            if not row or not row[0].strip(): continue
            draws.append((row[0], tuple(sorted(int(x) for x in row[1:6])), int(row[6])))
    draws.sort(key=lambda x: x[0])
    return draws

def save_master(path, draws):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter=";", lineterminator="\n")
        w.writerow(["date", "n1", "n2", "n3", "n4", "n5", "chance"])
        for d, nums, ch in sorted(draws): w.writerow([d, *nums, ch])

def integrity_check(draws):
    alerts = []
    dates = [d[0] for d in draws]
    if len(set(dates)) != len(dates): alerts.append("dates dupliquées détectées")
    for _, nums, ch in draws:
        if len(set(nums)) != 5 or not all(1 <= n <= N_POOL for n in nums):
            alerts.append(f"numéros invalides: {nums}"); break
        if not 1 <= ch <= 10:
            alerts.append(f"numéro Chance invalide: {ch}"); break
    prev = None
    for ds in dates:
        cur = date.fromisoformat(ds)
        if prev is not None and (cur - prev).days > 5:
            alerts.append(f"trou de {(cur-prev).days} j avant {ds}")
        prev = cur
    if len(draws) < 2500: alerts.append(f"profondeur faible: {len(draws)} tirages")
    return (len(alerts) == 0, alerts)

def dataset_fingerprint(draws, source):
    h = hashlib.sha256(repr(draws).encode()).hexdigest()[:12]
    return {"n": len(draws), "premier": draws[0][0], "dernier": draws[-1][0], "source": source, "hash": h}

# ---------------------------------------------------------------- CATALOGUE — NUMÉROS

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
    "Fréquence globale":      {"type": "selector", "fn": m_freq_globale},
    "Lag / retard normalisé": {"type": "selector", "fn": m_lag},
    "Fenêtres glissantes":    {"type": "selector", "fn": m_fenetres},
    "Momentum":               {"type": "selector", "fn": m_momentum},
    "Co-occurrence / graphe": {"type": "selector", "fn": m_cooccurrence},
    "Chaînes de Markov":      {"type": "selector", "fn": m_markov},
    "Entropie / chi2":        {"type": "diagnostic", "fn": None},
    "Anti-partage":           {"type": "filter", "fn": None},
}
SELECTORS = [k for k, v in CATALOG.items() if v["type"] == "selector"]

def top5(scores):
    return tuple(sorted(sorted(ALL_NUMS, key=lambda n: -scores[n])[:5]))

# ---------------------------------------------------------------- CATALOGUE — NUMÉRO CHANCE

def c_freq(draws):
    c = Counter(ch for _, _, ch in draws)
    return {x: c.get(x, 0) for x in ALL_CHANCE}

def c_lag(draws):
    gap = {x: len(draws) for x in ALL_CHANCE}
    for i, (_, _, ch) in enumerate(reversed(draws)):
        if gap[ch] == len(draws): gap[ch] = i
    return {x: float(gap[x]) for x in ALL_CHANCE}

def c_fenetres(draws, windows=(10, 20, 30)):
    sc = {x: 0.0 for x in ALL_CHANCE}
    for w in windows:
        c = Counter(ch for _, _, ch in draws[-w:]); tot = sum(c.values()) or 1
        for x in ALL_CHANCE: sc[x] += c.get(x, 0) / tot / len(windows)
    return sc

CHANCE_CATALOG = {"Chance — fréquence": c_freq, "Chance — lag": c_lag, "Chance — fenêtres": c_fenetres}

def top1_chance(scores):
    return max(scores, key=lambda s: scores[s])

def overlap(a, b):
    return len(set(a) & set(b))

# ---------------------------------------------------------------- POPULARITÉ (table injectable)
# Repli : même forme que le proxy UK Lotto (1-49), normalisé. En production, run_loto.py injecte la
# table estimée par popularite_loto.py sur les gagnants par rang FDJ.

def popularity_proxy_uk(n):
    if n <= 12:   base = 1.55
    elif n <= 31: base = 1.30
    elif n <= 40: base = 0.80
    else:         base = 0.62
    if n == 7:  base *= 1.25
    elif n == 3: base *= 1.10
    elif n % 7 == 0 and n != 7: base *= 1.05
    return base

def chance_popularity_proxy(c):
    return {7: 1.35, 3: 1.15, 1: 1.1, 5: 1.05, 9: 1.0, 2: 0.95, 4: 0.95, 6: 0.95, 8: 0.85, 10: 0.8}[c]

def _normalize(table, keys):
    m = sum(table[k] for k in keys) / len(keys)
    return {k: table[k] / m for k in keys}

POP = {"source": "proxy (repli)", "nums": None, "chance": None, "meta": {}}
_UNIVERSE_CACHE = {}
_POP_RANK_CACHE = {}

def set_popularity(table=None):
    global POP
    if table is None:
        POP = {"source": "proxy UK Lotto adapté 1-49 (repli)",
               "nums": _normalize({n: popularity_proxy_uk(n) for n in ALL_NUMS}, ALL_NUMS),
               "chance": _normalize({c: chance_popularity_proxy(c) for c in ALL_CHANCE}, ALL_CHANCE), "meta": {}}
    else:
        nums = {int(k): float(v) for k, v in table["nums"].items()}
        chance = {int(k): float(v) for k, v in table["chance"].items()}
        if set(nums) != set(ALL_NUMS) or set(chance) != set(ALL_CHANCE):
            raise ValueError("table de popularité incomplète")
        POP = {"source": table.get("source", "table fournie"), "nums": _normalize(nums, ALL_NUMS),
               "chance": _normalize(chance, ALL_CHANCE), "meta": table.get("meta", {})}
    _UNIVERSE_CACHE.clear(); _POP_RANK_CACHE.clear()

set_popularity(None)

def popularity(n): return POP["nums"][n]
def chance_popularity(c): return POP["chance"][c]

def shape_penalty(nums):
    s = sorted(nums); pen = 0
    if all(n <= 31 for n in s): pen += 15
    if sum(1 for n in s if n % 5 == 0) >= 3: pen += 10
    runs = max(len(list(g)) for _, g in itertools.groupby(enumerate(s), lambda t: t[1]-t[0]))
    if runs >= 3: pen += 15
    diffs = {s[i+1]-s[i] for i in range(4)}
    if len(diffs) == 1: pen += 15
    if len({n % 10 for n in s}) == 1: pen += 10
    return pen

def _sorted_log_pops():
    if "logs" not in _POP_RANK_CACHE:
        lp = {n: math.log(popularity(n)) for n in ALL_NUMS}
        _POP_RANK_CACHE["logs"] = sorted(lp[a]+lp[b]+lp[c]+lp[d]+lp[e]
                                         for a, b, c, d, e in itertools.combinations(ALL_NUMS, 5))
    return _POP_RANK_CACHE["logs"]

def anti_share_score(nums, chance=None):
    """Percentile d'impopularité parmi les C(49,5) grilles (100 = la moins jouée), moins pénalités."""
    logs = _sorted_log_pops()
    l = sum(math.log(popularity(n)) for n in nums)
    pct = 100.0 * (1.0 - bisect.bisect_right(logs, l + 1e-12) / len(logs))
    return max(0.0, min(100.0, pct - shape_penalty(nums)))

def relative_popularity(nums, chance=None):
    p = 1.0
    for n in nums: p *= popularity(n)
    if chance: p *= chance_popularity(chance)
    return p

def expected_cowinners(nums, chance=None, n_tickets=6_000_000):
    """Co-gagnants attendus au rang 1 si la grille gagne (descriptif ; ~6 M de grilles par tirage)."""
    return n_tickets * P_RANG1 * relative_popularity(nums, chance)

IMPOP_QUANTILE = 0.10
CHANCE_QUANTILE = 0.30        # les 3 numéros Chance les moins joués

def impopular_universe(quantile=IMPOP_QUANTILE):
    if quantile in _UNIVERSE_CACHE: return _UNIVERSE_CACHE[quantile]
    lp = {n: math.log(popularity(n)) for n in ALL_NUMS}
    combos = list(itertools.combinations(ALL_NUMS, 5))
    logs = [lp[a]+lp[b]+lp[c]+lp[d]+lp[e] for a, b, c, d, e in combos]
    thr = sorted(logs)[int(quantile * len(logs))]
    keep = [(l, g) for l, g in zip(logs, combos) if l <= thr and shape_penalty(g) == 0]
    keep.sort()
    res = ([g for _, g in keep], math.exp(thr / 5), len(combos))
    _UNIVERSE_CACHE[quantile] = res
    return res

def chance_universe(quantile=CHANCE_QUANTILE):
    order = sorted(ALL_CHANCE, key=lambda c: chance_popularity(c))
    return order[:max(3, math.ceil(quantile * len(order)))]

# ---------------------------------------------------------------- BACKTEST

def walk_forward(model_fn, draws, burn_in=150, step=1):
    pts = []; t = burn_in
    while t < len(draws):
        pred = set(top5(model_fn(draws[:t]))); pts.append(len(pred & set(draws[t][1]))); t += step
    return pts

def walk_forward_chance(model_fn, draws, burn_in=150, step=1):
    pts = []; t = burn_in
    while t < len(draws):
        pts.append(1 if top1_chance(model_fn(draws[:t])) == draws[t][2] else 0); t += step
    return pts

def bootstrap_ci(points, n_boot=10_000, seed=0):
    rng = random.Random(seed); n = len(points)
    means = sorted(sum(rng.choices(points, k=n))/n for _ in range(n_boot))
    return means[int(0.025*n_boot)], means[int(0.975*n_boot)]

def hypergeom_pmf(N=N_POOL, K=K_PICK, k_draw=K_PICK):
    tot = math.comb(N, k_draw)
    return [math.comb(K, k) * math.comb(N-K, k_draw-k) / tot for k in range(k_draw+1)]

def null_distribution(groups, n_models, n_sim=5000, seed=0):
    """groups = [(n_points, pmf)] : loi exacte de chaque point sous H0 ; max-statistic sur n_models."""
    rng = random.Random(seed); specs = []; n_total = 0
    for n_pts, pmf in groups:
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
    n = len(sorted_null)
    return max(1, n - bisect.bisect_left(sorted_null, observed)) / (n + 1)

def backtest_all(draws, burn_in=150, step=1, seed=0, n_sim=5000):
    out = {}
    for name in SELECTORS:
        pts = walk_forward(CATALOG[name]["fn"], draws, burn_in, step)
        avg = sum(pts)/len(pts); lo, hi = bootstrap_ci(pts, seed=seed)
        out[name] = {"points": pts, "n": len(pts), "avg": avg, "edge": avg - BASELINE, "ci": (lo - BASELINE, hi - BASELINE)}
    n_pts = out[SELECTORS[0]]["n"]
    null = null_distribution([(n_pts, hypergeom_pmf())], len(SELECTORS), n_sim=n_sim, seed=seed)
    for name, r in out.items():
        r["p_raw"] = p_value_from_null(r["edge"], null["single"])
        r["p_adj"] = p_value_from_null(r["edge"], null["max"]); r["significant"] = r["p_adj"] < 0.05
    best = max(out.values(), key=lambda r: r["edge"])["edge"]
    meta = {"burn_in": burn_in, "step": step, "n_points": n_pts, "n_models": len(SELECTORS), "n_sim": n_sim,
            "best_edge": best, "p_global": p_value_from_null(best, null["max"]),
            "null_max_q95": null["max"][int(0.95*len(null["max"]))]}
    return out, meta

def backtest_chance(draws, burn_in=150, step=1, seed=0, n_sim=5000):
    out = {}
    for name, fn in CHANCE_CATALOG.items():
        pts = walk_forward_chance(fn, draws, burn_in, step)
        avg = sum(pts)/len(pts); lo, hi = bootstrap_ci(pts, seed=seed)
        out[name] = {"points": pts, "n": len(pts), "avg": avg, "edge": avg - CHANCE_BASELINE,
                     "ci": (lo - CHANCE_BASELINE, hi - CHANCE_BASELINE)}
    n_pts = out[list(CHANCE_CATALOG)[0]]["n"]
    null = null_distribution([(n_pts, [0.9, 0.1])], len(CHANCE_CATALOG), n_sim=n_sim, seed=seed)
    for name, r in out.items():
        r["p_raw"] = p_value_from_null(r["edge"], null["single"])
        r["p_adj"] = p_value_from_null(r["edge"], null["max"]); r["significant"] = r["p_adj"] < 0.05
    best = max(out.values(), key=lambda r: r["edge"])["edge"]
    return out, {"n_points": n_pts, "n_models": len(CHANCE_CATALOG), "best_edge": best,
                 "p_global": p_value_from_null(best, null["max"])}

def verdict(bt, meta):
    if any(r["significant"] for r in bt.values()):
        return ("Au moins un modèle reste significatif après correction des tests multiples "
                f"(p global = {meta['p_global']:.3f}) — à examiner avec prudence : un seul échantillon.")
    return ("Aucun modèle ne se distingue du hasard sur cet échantillon "
            f"(p global = {meta['p_global']:.2f}) — le choix des porteurs est méthodologique, pas inférentiel.")

# ---------------------------------------------------------------- GÉNÉRATION

def best_grid(model_name, draws, avoid=None, max_ov=2, universe=None):
    grids = universe if universe is not None else impopular_universe()[0]
    scores = CATALOG[model_name]["fn"](draws)
    best, key = None, None
    for combo in grids:
        if avoid and any(overlap(combo, g) > max_ov for g in avoid): continue
        k = sum(scores[n] for n in combo)
        if key is None or k > key: best, key = combo, k
    return tuple(sorted(best)) if best else None

def best_chance(model_name, draws, avoid=None, universe=None):
    cands = universe if universe is not None else chance_universe()
    sc = CHANCE_CATALOG[model_name](draws)
    avoid = set(avoid or [])
    pool = [c for c in cands if c not in avoid] or cands
    return max(pool, key=lambda c: sc.get(c, 0))

def n_grids(jackpot_meur, plancher=0, defaut=3):
    """Loto : 3 grilles par défaut (une par porteur du podium), +1 par tranche de 10 M€ au-delà de 10 M€.
       `plancher` ne fait que relever."""
    regle = defaut + max(0, math.floor((jackpot_meur - 10) / 10))
    return max(regle, int(plancher or 0))

def consensus_grid(bt, draws):
    sig = {k: r for k, r in bt.items() if r.get("significant")}
    if not sig: return None
    agg = {x: 0.0 for x in ALL_NUMS}
    for name, r in sig.items():
        w = max(r["edge"], 0) + 0.01; sc = CATALOG[name]["fn"](draws); mx = max(sc.values()) or 1
        for x in ALL_NUMS: agg[x] += w * sc[x]/mx
    return top5(agg)

def rank_selectors(bt, ineligible_first=None):
    order = sorted(bt, key=lambda k: -bt[k]["edge"])
    if ineligible_first and order and order[0] == ineligible_first and len(order) > 1:
        order[0], order[1] = order[1], order[0]
    return order

# ---------------------------------------------------------------- DIAGNOSTIC / CALENDRIER

def chi2_uniformity(draws):
    c = Counter()
    for _, n, _ in draws: c.update(n)
    exp = len(draws)*5/N_POOL
    chi2 = sum((c.get(x, 0)-exp)**2/exp for x in ALL_NUMS); dof = N_POOL - 1
    z = ((chi2/dof)**(1/3) - (1-2/(9*dof))) / math.sqrt(2/(9*dof))
    p = 1 - 0.5*(1+math.erf(z/math.sqrt(2)))
    return chi2, max(0.0, min(1.0, p))

def next_draw_date(today):
    d = today
    while d.weekday() not in DRAW_WEEKDAYS: d += timedelta(days=1)
    return d

def seed_from_draw_date(d):
    return int(d.replace("-", ""))

# ---------------------------------------------------------------- CHECKLIST

FORBIDDEN = ["prometteur", "tendance favorable", "momentum favorable", "numéro gagnant", "va sortir", "bonne chance"]
DISCLAIMER = ("Claude ne prédit pas les tirages. Le hasard est sans mémoire. Aucune analyse ne garantit un gain. "
              "EV nette structurellement négative. Les edges backtestés peuvent être du bruit statistique — "
              "méthodologie documentée, pas un oracle.")
EQUIVALENCE = ("Toutes les grilles ci-dessus ont exactement la même probabilité de gain : 1/19 068 840 au rang 1. "
               "Le pipeline choisit comment jouer, jamais mieux jouer.")

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
