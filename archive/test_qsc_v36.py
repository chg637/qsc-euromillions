# -*- coding: utf-8 -*-
"""Tests unitaires QSC v3.6 (spec #10) — invariants contraintes, filtre, integrite, formule."""
import math
import qsc_v36 as q

def run():
    T = []
    def t(name, cond): T.append((name, bool(cond)))

    # --- contraintes dures (cas limites)
    t("somme=95 acceptee",      q.hard_ok((3, 8, 17, 28, 39)))        # 95, 2 pairs, low=3, ecarts>=3
    t("somme=155 acceptee",     q.hard_ok((15, 21, 32, 41, 46)))      # 155, 2 pairs, low=2
    t("somme=94 rejetee",       not q.hard_ok((3, 8, 17, 28, 38)))
    t("somme=156 rejetee",      not q.hard_ok((12, 20, 34, 42, 48)))
    t("ecart=3 exact accepte",  q.hard_ok((10, 13, 26, 33, 45)))      # min gap 3
    t("ecart=2 rejete",         not q.hard_ok((10, 12, 25, 33, 45)))
    t("4 pairs rejete",         not q.hard_ok((10, 14, 22, 30, 41)))
    t("1 pair rejete",          not q.hard_ok((9, 15, 22, 33, 45)))
    t("4 bas rejete",           not q.hard_ok((5, 9, 15, 22, 49)))
    t("4 hauts rejete",         not q.hard_ok((9, 28, 34, 40, 44)))
    t("overlap=2",              q.overlap((1,2,3,4,5), (4,5,6,7,8)) == 2)

    # --- anti-partage
    t("grille anniversaires penalisee",
      q.anti_share_score((3, 7, 12, 19, 27)) < q.anti_share_score((14, 33, 38, 43, 49)))
    t("grille impopulaire >=60", q.anti_share_score((14, 33, 38, 43, 49)) >= 60)
    t("consecutifs penalises",
      q.anti_share_score((32, 33, 34, 41, 48)) < q.anti_share_score((14, 33, 38, 43, 49)))
    t("popularite 7 > popularite 45", q.popularity(7) > q.popularity(45))
    t("popularite grille bornee", 0.4 < q.grid_popularity((14,33,38,43,49)) < 2.0)
    t("co-gagnants attendus decroit avec impopularite",
      q.expected_cowinners((3,7,12,19,27)) > q.expected_cowinners((14,33,38,43,49)))

    # --- formule nombre de grilles (exemples valides par Charles)
    for j, expected in [(30,2),(80,2),(89,2),(130,3),(160,4),(220,5),(250,6)]:
        t(f"n_grids({j})={expected}", q.n_grids(j) == expected)

    # --- integrite dataset
    good = [("2026-01-02",(1,5,10,20,30),(2,5)), ("2026-01-06",(2,6,11,21,31),(3,6))]
    ok, alerts = q.integrity_check(good)
    t("integrite ok sur mini-dataset", ok or ("profondeur" in alerts[0] and len(alerts)==1))
    dup = good + [("2026-01-06",(2,6,11,21,31),(3,6))]
    t("doublon detecte", "dupliquees" in " ".join(q.integrity_check(dup)[1]))
    bad = [("2026-01-02",(1,5,10,20,51),(2,5))]
    t("numero hors bornes detecte", any("invalides" in a for a in q.integrity_check(bad)[1]))

    # --- constantes statistiques
    t("P(>=1 match)=42.34%", abs(q.P_GE1_MATCH - 0.42336) < 0.001)
    t("baseline=0.5", q.BASELINE == 0.5)

    # --- seed deterministe
    t("seed 2026-08-04 -> 20260804", q.seed_from_draw_date("2026-08-04") == 20260804)

    # --- catalogue type
    t("7 selectors", len(q.SELECTORS) == 7)
    t("anti-partage est filter", q.CATALOG["Anti-partage"]["type"] == "filter")
    t("entropie est diagnostic", q.CATALOG["Entropie / chi2"]["type"] == "diagnostic")

    # --- consensus degenerescence
    fake_bt = {k: {"edge": -0.05} for k in q.SELECTORS}
    t("consensus degenere si tous edges<=0", q.consensus_grid(fake_bt, good) is None)

    passed = sum(1 for _, ok in T if ok)
    for name, ok in T:
        print(("PASS" if ok else "FAIL"), name)
    print(f"\n{passed}/{len(T)} tests OK")
    return passed == len(T)

if __name__ == "__main__":
    import sys
    sys.exit(0 if run() else 1)
