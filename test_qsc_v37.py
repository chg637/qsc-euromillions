# -*- coding: utf-8 -*-
"""Tests unitaires QSC v3.7 — invariants v3.6 conservés + null exact, max-stat, pool étoiles, consensus stricte."""
import math, random
from datetime import date
import qsc_v37 as q

def run():
    T = []
    def t(name, cond): T.append((name, bool(cond)))

    # --- contraintes dures (cas limites)
    t("somme=95 acceptée",      q.hard_ok((3, 8, 17, 28, 39)))
    t("somme=155 acceptée",     q.hard_ok((15, 21, 32, 41, 46)))
    t("somme=94 rejetée",       not q.hard_ok((3, 8, 17, 28, 38)))
    t("somme=156 rejetée",      not q.hard_ok((12, 20, 34, 42, 48)))
    t("écart=3 exact accepté",  q.hard_ok((10, 13, 26, 33, 45)))
    t("écart=2 rejeté",         not q.hard_ok((10, 12, 25, 33, 45)))
    t("4 pairs rejeté",         not q.hard_ok((10, 14, 22, 30, 41)))
    t("1 pair rejeté",          not q.hard_ok((9, 15, 22, 33, 45)))
    t("4 bas rejeté",           not q.hard_ok((5, 9, 15, 22, 49)))
    t("4 hauts rejeté",         not q.hard_ok((9, 28, 34, 40, 44)))
    t("overlap=2",              q.overlap((1,2,3,4,5), (4,5,6,7,8)) == 2)

    # --- anti-partage
    t("grille anniversaires pénalisée",
      q.anti_share_score((3, 7, 12, 19, 27)) < q.anti_share_score((14, 33, 38, 43, 49)))
    t("grille impopulaire >=60", q.anti_share_score((14, 33, 38, 43, 49)) >= 60)
    t("consécutifs pénalisés",
      q.anti_share_score((32, 33, 34, 41, 48)) < q.anti_share_score((14, 33, 38, 43, 49)))
    t("popularité 7 > popularité 45", q.popularity(7) > q.popularity(45))
    t("co-gagnants décroît avec impopularité",
      q.expected_cowinners((3,7,12,19,27)) > q.expected_cowinners((14,33,38,43,49)))

    # --- nombre de grilles
    for j, expected in [(30,2),(80,2),(89,2),(130,3),(160,4),(220,5),(250,6)]:
        t(f"n_grids({j})={expected}", q.n_grids(j) == expected)

    # --- intégrité
    good = [("2026-01-02",(1,5,10,20,30),(2,5)), ("2026-01-06",(2,6,11,21,31),(3,6))]
    ok, alerts = q.integrity_check(good)
    t("intégrité mini-dataset", ok or (len(alerts)==1 and "profondeur" in alerts[0]))
    dup = good + [("2026-01-06",(2,6,11,21,31),(3,6))]
    t("doublon détecté", "dupliquées" in " ".join(q.integrity_check(dup)[1]))
    bad = [("2026-01-02",(1,5,10,20,51),(2,5))]
    t("numéro hors bornes détecté", any("invalides" in a for a in q.integrity_check(bad)[1]))

    # --- constantes
    t("P(>=1 match)=42.34%", abs(q.P_GE1_MATCH - 0.42336) < 0.001)
    t("baseline numéros=0.5", q.BASELINE == 0.5)
    pmf = q.hypergeom_pmf()
    t("pmf hypergéo somme 1", abs(sum(pmf) - 1) < 1e-12)
    t("pmf hypergéo espérance 0.5", abs(sum(k*p for k,p in enumerate(pmf)) - 0.5) < 1e-12)

    # --- C3 catalogue : Dirichlet retiré, 6 selectors
    t("6 selectors", len(q.SELECTORS) == 6)
    t("Dirichlet absent", not any("Dirichlet" in k for k in q.CATALOG))
    t("anti-partage est filter", q.CATALOG["Anti-partage"]["type"] == "filter")
    t("entropie est diagnostic", q.CATALOG["Entropie / chi2"]["type"] == "diagnostic")

    # --- C1 null exact + max-statistic
    null = q.null_distribution([(1000, 50, 5, 5)], 6, n_sim=400, seed=1)
    m_single = sum(null["single"])/len(null["single"])
    t("null single centrée ~0", abs(m_single) < 0.01)
    t("null max > null single (correction multiple)",
      null["max"][int(0.95*400)] > null["single"][int(0.95*400)])
    t("p-value edge nul ~0.5", 0.3 < q.p_value_from_null(0.0, null["single"]) < 0.7)
    t("p-value edge énorme -> plancher", q.p_value_from_null(1.0, null["max"]) <= 1/400)
    t("p-value edge très négatif -> 1", q.p_value_from_null(-1.0, null["max"]) > 0.99)

    # --- C1 : sur données synthétiques purement aléatoires, aucun modèle significatif (seed fixe)
    rng = random.Random(7)
    synth = []
    d0 = date(2016, 9, 27)
    for i in range(600):
        synth.append((str(d0.fromordinal(d0.toordinal()+3*i)),
                      tuple(sorted(rng.sample(q.ALL_NUMS, 5))), tuple(sorted(rng.sample(q.ALL_STARS, 2)))))
    bt, meta = q.backtest_all(synth, burn_in=100, step=4, n_sim=300, seed=3)
    t("données aléatoires : p_global non significatif", meta["p_global"] > 0.05)
    t("consensus dégénère si rien de significatif (C4)", q.consensus_grid(bt, synth) is None)
    fake = {k: dict(r, significant=(k == q.SELECTORS[0]), edge=0.05) for k, r in bt.items()}
    t("consensus calculable si un modèle significatif", q.consensus_grid(fake, synth) is not None)

    # --- C5 pool étoiles
    t("pool 9 avant 2011-05-10", q.star_pool("2011-05-06") == 9)
    t("pool 11 en 2011-05-10", q.star_pool("2011-05-10") == 11)
    t("pool 12 depuis 2016-09-27", q.star_pool("2016-09-27") == 12)
    t("baseline étoiles pool 12 = 1/3", abs(q.star_baseline(12) - 1/3) < 1e-12)
    t("s_lag pool 9 ne propose jamais >9", max(q.s_lag(synth[:50], 9)) == 9)
    pts, exc, pools = q.walk_forward_stars(q.s_freq, synth, burn_in=100, step=50)
    t("walk_forward_stars aligne points/pools", len(pts) == len(exc) == len(pools))

    # --- rotation narrative
    order = q.rank_selectors({"A": {"edge": 0.3}, "B": {"edge": 0.2}, "C": {"edge": 0.1}}, ineligible_first="A")
    t("porteur #1 précédent redescend en 2e", order[:2] == ["B", "A"])

    # --- calendrier / seed
    t("next_draw vendredi 2026-09-04 -> lui-même", q.next_draw_date(date(2026,9,4)) == date(2026,9,4))
    t("next_draw samedi 2026-09-05 -> mardi 08", q.next_draw_date(date(2026,9,5)) == date(2026,9,8))
    t("seed 2026-09-08 -> 20260908", q.seed_from_draw_date("2026-09-08") == 20260908)

    # --- checklist
    fp = {"n": 1968}
    html = q.DISCLAIMER + q.EQUIVALENCE + " 1968 seed 20260908"
    chat = q.DISCLAIMER + " ... " + q.DISCLAIMER
    t("checklist passe", q.checklist(html, chat, fp, 20260908)[0])
    t("checklist bloque lexique interdit", not q.checklist(html + " numéro gagnant", chat, fp, 20260908)[0])

    passed = sum(1 for _, ok in T if ok)
    for name, ok in T:
        print(("PASS" if ok else "FAIL"), name)
    print(f"\n{passed}/{len(T)} tests OK")
    return passed == len(T)

if __name__ == "__main__":
    import sys
    sys.exit(0 if run() else 1)
