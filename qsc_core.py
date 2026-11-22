# -*- coding: utf-8 -*-
"""
qsc_core.py : briques communes du protocole QSC (EuroMillions et Loto).

Extraites des modules de chaque jeu (PR 3/6 du refactor). Règle : aucune constante propre à un
jeu ici. Ce qui dépend du jeu (univers de numéros, paliers de mise) est passé en paramètre, et
chaque module de jeu garde des enveloppes minces qui fournissent ses constantes, donc les noms
et signatures publics de qsc_v40 et qsc_loto ne changent pas.

Volontairement PAS ici (vraies divergences entre les deux jeux, à trancher à part) :
n_grids (tolérance flottante 1e-9 côté Loto seulement), null_distribution et backtest_all
(loi hypergéométrique), walk_forward, shape_penalty, anti_share_score, impopular_universe,
checklist (EQUIVALENCE et FORBIDDEN propres à chaque jeu), chi2_uniformity, integrity_check.
"""
import bisect, hashlib, random
from collections import Counter, defaultdict


# ---------------------------------------------------------------- sans paramètre de jeu

def dataset_fingerprint(draws, source):
    h = hashlib.sha256(repr(draws).encode()).hexdigest()[:12]
    return {"n": len(draws), "premier": draws[0][0], "dernier": draws[-1][0],
            "source": source, "hash": h}

def overlap(a, b):
    return len(set(a) & set(b))

def popularity_proxy_uk(n):
    if n <= 12:   base = 1.55
    elif n <= 31: base = 1.30
    elif n <= 40: base = 0.80
    else:         base = 0.62
    if n == 7:  base *= 1.25
    elif n == 3: base *= 1.10
    elif n % 7 == 0 and n != 7: base *= 1.05
    return base

def _normalize(table, keys):
    m = sum(table[k] for k in keys) / len(keys)
    return {k: table[k] / m for k in keys}

def bootstrap_ci(points, n_boot=10_000, seed=0):
    rng = random.Random(seed)
    n = len(points)
    means = sorted(sum(rng.choices(points, k=n))/n for _ in range(n_boot))
    return means[int(0.025*n_boot)], means[int(0.975*n_boot)]

def p_value_from_null(observed, sorted_null):
    """P(null >= observed), plancher 1/(n+1)."""
    n = len(sorted_null)
    return max(1, n - bisect.bisect_left(sorted_null, observed)) / (n + 1)

def verdict(bt, meta):
    if any(r["significant"] for r in bt.values()):
        return ("Au moins un modèle reste significatif après correction des tests multiples "
                f"(p global = {meta['p_global']:.3f}) — à examiner avec prudence (un seul échantillon) ; la sélection reste uniforme.")
    return ("Aucun modèle ne se distingue du hasard sur cet échantillon "
            f"(p global = {meta['p_global']:.2f}) — les numéros sont tirés au sort dans l'univers impopulaire, aucun modèle ne les choisit.")

def seed_from_draw_date(d):
    return int(d.replace("-", ""))

# ---------------------------------------------------------------- paramétrées par l'univers `nums`

def m_freq_globale(draws, nums):
    c = Counter()
    for _, n, _ in draws: c.update(n)
    return {x: c.get(x, 0) for x in nums}

def m_lag(draws, nums):
    gap = {x: len(draws) for x in nums}
    for i, (_, ns, _) in enumerate(reversed(draws)):
        for x in ns:
            if gap[x] == len(draws): gap[x] = i
    return {x: gap[x] / 10.0 for x in nums}

def m_fenetres(draws, nums, windows=(10, 20, 30)):
    s = {x: 0.0 for x in nums}
    for w in windows:
        c = Counter()
        for _, n, _ in draws[-w:]: c.update(n)
        tot = sum(c.values()) or 1
        for x in nums: s[x] += c.get(x, 0) / tot / len(windows)
    return s

def m_momentum(draws, nums, recent=10, prior=10):
    cr, cp = Counter(), Counter()
    for _, n, _ in draws[-recent:]: cr.update(n)
    for _, n, _ in draws[-(recent+prior):-recent]: cp.update(n)
    return {x: cr.get(x, 0)/recent - cp.get(x, 0)/prior for x in nums}

def m_cooccurrence(draws, nums):
    if not draws: return {x: 0.0 for x in nums}
    last = set(draws[-1][1]); co = defaultdict(float)
    for _, ns, _ in draws:
        inter = set(ns) & last
        if inter:
            for x in ns:
                if x not in last: co[x] += len(inter)
    return {x: co.get(x, 0.0) for x in nums}

def m_markov(draws, nums):
    tc = defaultdict(lambda: defaultdict(int)); occ = defaultdict(int)
    for i in range(len(draws)-1):
        nxt = set(draws[i+1][1])
        for m in draws[i][1]:
            occ[m] += 1
            for n in nxt: tc[m][n] += 1
    s = {x: 0.0 for x in nums}
    if not draws: return s
    for m in draws[-1][1]:
        if occ[m]:
            for x in nums: s[x] += tc[m].get(x, 0) / occ[m]
    return s

def top5(scores, nums):
    return tuple(sorted(sorted(nums, key=lambda n: -scores[n])[:5]))

def n_grids_regle(jackpot_meur, paliers):
    """A2 : 1 grille, +1 par palier franchi (paliers en M€)."""
    return 1 + sum(1 for p in paliers if jackpot_meur >= p)
