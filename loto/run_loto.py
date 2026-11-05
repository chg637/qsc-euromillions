# -*- coding: utf-8 -*-
"""
run_loto.py — Pipeline QSC Loto v1.0, exécuté par GitHub Actions les jours de tirage (lun/mer/sam).

Étapes : chargement + intégrité → rapprochement du run précédent (registre append-only)
→ popularité estimée sur les gagnants par rang FDJ → backtest numéros / Chance (step 1, null exacte,
max-stat) → chi² → jackpot → rotation narrative → sélection dans l'univers impopulaire → consensus
→ latest.json / latest.html / history/<date>.json → checklist.

Usage : python3 run_loto.py [--jackpot 8] [--today 2026-10-14] [--n-grilles 3]
Sortie : 0 si checklist verte, 4 sinon.
"""
import argparse, csv, json, os, sys, html as H
from datetime import date
import qsc_loto as q
import popularite_loto as P

REG_FIELDS = ["run_date", "draw_date", "grid", "model", "nums", "chance", "seed",
              "real_nums", "real_chance", "match_nums", "match_chance"]

def load_registre(path):
    if not os.path.exists(path): return []
    with open(path, newline="", encoding="utf-8") as f: return list(csv.DictReader(f, delimiter=";"))

def save_registre(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=REG_FIELDS, delimiter=";", lineterminator="\n"); w.writeheader()
        for r in rows: w.writerow(r)

def reconcile(rows, draws):
    by_date = {d: (n, c) for d, n, c in draws}; done = []
    for r in rows:
        if r["match_nums"] == "" and r["draw_date"] in by_date:
            rn, rc = by_date[r["draw_date"]]
            gn = {int(x) for x in r["nums"].split("-")}
            r["real_nums"] = "-".join(map(str, rn)); r["real_chance"] = str(rc)
            r["match_nums"] = str(len(gn & set(rn))); r["match_chance"] = "1" if int(r["chance"]) == rc else "0"
            done.append(r)
    return done

def cumul(rows):
    played = [r for r in rows if r["match_nums"] != ""]; n = len(played)
    mn = sum(int(r["match_nums"]) for r in played); mc = sum(int(r["match_chance"]) for r in played)
    return {"grilles": n, "match_nums": mn, "attendu_nums": round(q.BASELINE * n, 2), "ecart_nums": round(mn - q.BASELINE * n, 2),
            "match_chance": mc, "attendu_chance": round(q.CHANCE_BASELINE * n, 2), "ecart_chance": round(mc - q.CHANCE_BASELINE * n, 2),
            "meilleur": max((int(r["match_nums"]) for r in played), default=0)}

def estimate_jackpot(meta, override):
    if override is not None:
        return {"meur": float(override), "source": "fourni", "note": "montant officiel fourni au run"}
    last = (meta or {}).get("last_draw") or {}
    jp = last.get("jackpot_eur")
    if jp and not last.get("has_winner"):
        return {"meur": round(jp / 1e6 + 1, 0), "source": "estimation",
                "note": f"jackpot du {last['date']} ({jp/1e6:.0f} M€) non gagné : +1 M€ au tirage suivant"}
    return {"meur": 2.0, "source": "estimation", "note": "jackpot remis à 2 M€ après un gagnant (ou source muette)"}

def popularity_report(table):
    nums = {n: round(q.popularity(n), 4) for n in q.ALL_NUMS}
    ch = {c: round(q.chance_popularity(c), 4) for c in q.ALL_CHANCE}
    meta = (table or {}).get("meta", {})
    r = {"source": q.POP["source"], "estimee": table is not None, "nums": nums, "chance": ch,
         "nums_min": min(nums, key=nums.get), "nums_max": max(nums, key=nums.get),
         "chance_tries": sorted(ch, key=ch.get),
         "tranches": {f"{lo}-{hi}": round(sum(nums[n] for n in range(lo, hi+1)) / (hi-lo+1), 3)
                      for lo, hi in [(1, 12), (13, 31), (32, 40), (41, 49)]}}
    if table is not None:
        mn, mc = meta.get("numeros", {}), meta.get("chance", {})
        r.update({"n_tirages_nums": mn.get("n_draws"), "n_tirages_chance": mc.get("n_draws"), "periode": mn.get("periode"),
                  "r2_nums": round(mn.get("r2", 0), 3),
                  "se_moyen_nums": round(sum(mn["se"].values()) / 49, 4) if mn.get("se") else None,
                  "se_moyen_chance": round(sum(mc["se"].values()) / 10, 4) if mc.get("se") else None})
    return r

CSS = """
:root{--bg:#0b0f14;--pan:#121821;--line:#1f2a36;--tx:#d7dee7;--mut:#8593a3;--acc:#5aa9ff;--ok:#31c48d;--warn:#f5a524;--bad:#ef5350}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--tx);font:14px/1.45 -apple-system,Segoe UI,Roboto,sans-serif;padding:16px}
h1{font-size:18px;margin:0 0 4px}h2{font-size:14px;color:var(--mut);text-transform:uppercase;letter-spacing:.08em;margin:22px 0 8px}
.warn{background:#2a1d0a;border:1px solid #5a3d0f;color:#ffd58a;padding:10px 12px;border-radius:6px;font-size:13px;margin:10px 0}
.grid{display:grid;gap:10px;grid-template-columns:repeat(auto-fit,minmax(260px,1fr))}
.card{background:var(--pan);border:1px solid var(--line);border-radius:8px;padding:12px}
.nums{font:600 22px/1 ui-monospace,Menlo,monospace;letter-spacing:.04em;margin:6px 0}.nums b{color:var(--ok)}
table{width:100%;border-collapse:collapse;font-size:13px}th,td{padding:5px 6px;border-bottom:1px solid var(--line);text-align:left;white-space:nowrap}
th{color:var(--mut);font-weight:500}.r{text-align:right}.wrap{overflow-x:auto}
.b{display:inline-block;padding:1px 7px;border-radius:10px;font-size:11px;font-weight:600}
.b.ns{background:#1c2733;color:var(--mut)}.b.sig{background:#0f3d2b;color:var(--ok)}.b.ok{background:#0f3d2b;color:var(--ok)}.b.ko{background:#4a1616;color:var(--bad)}
.k{color:var(--mut);font-size:12px}.mono{font-family:ui-monospace,Menlo,monospace}.foot{color:var(--mut);font-size:12px;margin-top:20px}
"""

def fmt_nums(nums): return " ".join(f"{n:02d}" for n in nums)
def fmt_int(n): return f"{n:,}".replace(",", " ")

def bars(table, keys, w):
    mx = max(table[k] for k in keys); mn = min(table[k] for k in keys); out = []
    for k in keys:
        v = table[k]; h = 46 * (v - mn) / (mx - mn or 1) + 4
        col = "#ef5350" if v > 1.05 else ("#31c48d" if v < 0.95 else "#8593a3")
        out.append(f'<div title="{k} : ×{v:.2f}" style="display:inline-block;width:{w}px;margin:0 1px;text-align:center;font-size:9px;color:#8593a3;vertical-align:bottom">'
                   f'<div style="height:50px;display:flex;align-items:flex-end"><div style="width:100%;height:{h:.0f}px;background:{col};border-radius:2px 2px 0 0"></div></div>{k}</div>')
    return "".join(out)

def popularity_html(p):
    nums = {int(k): v for k, v in p["nums"].items()}; ch = {int(k): v for k, v in p["chance"].items()}
    if p["estimee"]:
        src = (f'{H.escape(p["source"])} — {p["n_tirages_nums"]} tirages pour les numéros ({p["periode"][0]} → {p["periode"][1]}), '
               f'{p["n_tirages_chance"]} pour la Chance (règle 2017+), R² {p["r2_nums"]:.2f}, incertitude ±{p["se_moyen_nums"]:.3f} par numéro, ±{p["se_moyen_chance"]:.3f} par Chance. '
               f'Tranches : 1-12 ×{p["tranches"]["1-12"]:.2f} · 13-31 ×{p["tranches"]["13-31"]:.2f} · 32-40 ×{p["tranches"]["32-40"]:.2f} · 41-49 ×{p["tranches"]["41-49"]:.2f}. '
               f'Numéro le plus joué : {p["nums_max"]} (×{nums[p["nums_max"]]:.2f}), le moins joué : {p["nums_min"]} (×{nums[p["nums_min"]]:.2f}). '
               f'Chance de la moins à la plus jouée : {" ".join(str(c) for c in p["chance_tries"])}.')
    else:
        src = f'{H.escape(p["source"])} — table estimée indisponible ce run : proxy de repli.'
    return (f'<div class="card" style="margin-top:10px"><div class="k"><b>Popularité des numéros et du numéro Chance</b> (×1,00 = moyenne ; rouge = plus joué, vert = moins joué). {src}</div>'
            f'<div style="margin-top:8px;white-space:nowrap;overflow-x:auto">{bars(nums, q.ALL_NUMS, 12)}</div>'
            f'<div style="margin-top:6px;white-space:nowrap">{bars(ch, q.ALL_CHANCE, 22)}</div></div>')

def build_html(R):
    fp, bt, sb = R["dataset"], R["backtest"]["numeros"], R["backtest"]["chance"]
    badge = lambda r: '<span class="b sig">sig.</span>' if r["significant"] else '<span class="b ns">ns</span>'
    rows_bt = "".join(f'<tr><td>{i+1}</td><td>{H.escape(k)}</td><td class="r mono">{r["edge"]:+.3f}</td><td class="r mono">[{r["ci"][0]:+.3f} ; {r["ci"][1]:+.3f}]</td>'
                      f'<td class="r mono">{r["p_raw"]:.2f}</td><td class="r mono">{r["p_adj"]:.2f}</td><td>{badge(r)}</td></tr>'
                      for i, (k, r) in enumerate(sorted(bt.items(), key=lambda x: -x[1]["edge"])))
    rows_sb = "".join(f'<tr><td>{H.escape(k)}</td><td class="r mono">{r["edge"]:+.3f}</td><td class="r mono">[{r["ci"][0]:+.3f} ; {r["ci"][1]:+.3f}]</td><td class="r mono">{r["p_adj"]:.2f}</td><td>{badge(r)}</td></tr>'
                      for k, r in sorted(sb.items(), key=lambda x: -x[1]["edge"]))
    cards = "".join(f'<div class="card"><div class="k">G{g["id"]} · porteur : {H.escape(g["model"])} · Chance : {H.escape(g["chance_model"])}</div>'
                    f'<div class="nums">{fmt_nums(g["nums"])} <b>Chance {g["chance"]}</b></div>'
                    f'<div class="k">somme {g["sum"]} · pairs {g["even"]}/5 · bas {g["low"]}/5 · impopularité {g["anti_share"]:.0f}e percentile · '
                    f'joueurs attendus ×{g["rel_popularity"]:.2f} vs grille moyenne · co-gagnants attendus au rang 1 : {g["cowinners"]:.3f}</div></div>'
                    for g in R["grilles"])
    c = R["registre"]["cumul"]; rec = R["registre"]["rapproche"]
    rec_html = ("".join(f'<tr><td>{r["draw_date"]}</td><td>G{r["grid"]} · {H.escape(r["model"])}</td><td class="mono">{r["nums"]} C{r["chance"]}</td>'
                        f'<td class="mono">{r["real_nums"]} C{r["real_chance"]}</td><td class="r"><b>{r["match_nums"]}</b> num · Chance {"oui" if r["match_chance"]=="1" else "non"}</td></tr>' for r in rec)
                or '<tr><td colspan="5" class="k">aucune grille à rapprocher ce run</td></tr>')
    chk = R["checklist"]; jp = R["jackpot"]
    alerts = "".join(f"<li>{H.escape(a)}</li>" for a in fp["alertes"]) or "<li>aucune alerte</li>"
    return f"""<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>QSC Loto v{q.VERSION} — tirage du {R['draw_date']}</title><style>{CSS}</style></head><body>
<h1>QSC Loto v{q.VERSION} — tirage du {R['draw_date_fr']}</h1>
<div class="k">run {R['run_date']} · seed <span class="mono">{R['seed']}</span> · dataset {fp['n']} tirages ({fp['premier']} → {fp['dernier']}) · hash <span class="mono">{fp['hash']}</span> · checklist {'<span class="b ok">verte</span>' if chk['ok'] else '<span class="b ko">KO</span>'}</div>
<div class="warn">⚠️ {q.DISCLAIMER}</div>
<h2>Grilles proposées — {len(R['grilles'])} (jackpot {jp['meur']:.0f} M€, {jp['source']} : {H.escape(jp['note'])})</h2>
<div class="grid">{cards}</div>
<p class="k">{q.EQUIVALENCE}</p>
<p class="k"><b>Sélection</b> : univers = les {100*R['selection']['quantile']:.0f} % de grilles les moins jouées ({fmt_int(R['selection']['univers_grilles'])} sur {fmt_int(R['selection']['total_grilles'])}, popularité moyenne ≤ {R['selection']['seuil_gp']:.3f} vs 1,00), hors motifs sur-joués ; numéro Chance parmi {', '.join(str(c) for c in R['selection']['chance_univers'])} (les moins joués). Le porteur départage à l'intérieur de cet univers. Cela ne change pas la probabilité de gagner, seulement le partage attendu si la grille gagne.</p>
{popularity_html(R['popularite'])}
<p class="k">Consensus pondérée : {H.escape(R['consensus']['message'])}</p>
<h2>Backtest numéros — walk-forward burn-in {R['backtest']['meta']['burn_in']}, step {R['backtest']['meta']['step']}, {R['backtest']['meta']['n_points']} points</h2>
<div class="wrap"><table><tr><th>#</th><th>Modèle</th><th class="r">Écart vs {q.BASELINE:.3f}</th><th class="r">IC95% bootstrap</th><th class="r">p brut</th><th class="r">p corrigé*</th><th></th></tr>{rows_bt}</table></div>
<p class="k">* p corrigé = max-statistic sur {R['backtest']['meta']['n_models']} modèles ({R['backtest']['meta']['n_sim']} simulations sous H0 hypergéométrique exact, 5 parmi 49). Seuil du meilleur modèle : écart ≥ {R['backtest']['meta']['null_max_q95']:+.3f}. <b>Verdict :</b> {H.escape(R['backtest']['verdict'])}</p>
<h2>Backtest numéro Chance (baseline 1/10)</h2>
<div class="wrap"><table><tr><th>Modèle</th><th class="r">Écart vs 0,100</th><th class="r">IC95%</th><th class="r">p corrigé</th><th></th></tr>{rows_sb}</table></div>
<p class="k">p global Chance = {R['backtest']['chance_meta']['p_global']:.2f}. {H.escape(R['backtest']['chance_verdict'])}</p>
<h2>Diagnostics</h2>
<div class="grid">
<div class="card"><div class="k">χ² d'uniformité (49 numéros, ddl 48)</div><div class="nums">{R['chi2']['stat']:.1f}</div><div class="k">p ≈ {R['chi2']['p']:.2f} — {'aucun biais matériel' if R['chi2']['p'] > 0.05 else 'écart à l uniforme : vérifier le dataset'}</div></div>
<div class="card"><div class="k">Intégrité dataset</div><ul class="k" style="margin:6px 0 0 16px;padding:0">{alerts}</ul></div>
</div>
<h2>Tableau de bord cumulatif — protocole vs hasard</h2>
<div class="grid">
<div class="card"><div class="k">Grilles jouées (registre)</div><div class="nums">{c['grilles']}</div></div>
<div class="card"><div class="k">Numéros trouvés / attendus</div><div class="nums">{c['match_nums']} / {c['attendu_nums']}</div><div class="k">écart {c['ecart_nums']:+}</div></div>
<div class="card"><div class="k">Chance trouvée / attendue</div><div class="nums">{c['match_chance']} / {c['attendu_chance']}</div><div class="k">écart {c['ecart_chance']:+}</div></div>
<div class="card"><div class="k">Meilleure grille</div><div class="nums">{c['meilleur']} num.</div></div>
</div>
<h2>Rapprochement du run précédent</h2>
<div class="wrap"><table><tr><th>Tirage</th><th>Grille</th><th>Jouée</th><th>Réel</th><th class="r">Résultat</th></tr>{rec_html}</table></div>
<h2>Lexique</h2>
<p class="k"><b>Écart backtesté</b> : matches moyens du top-5 du modèle moins {q.BASELINE:.3f} (espérance d'une grille aléatoire, 5 parmi 49). <b>p corrigé</b> : probabilité, sous pur hasard, qu'au moins un des modèles atteigne cet écart (max-statistic). <b>Porteur</b> : modèle qui départage les grilles à l'intérieur de l'univers impopulaire — un choix de méthode, pas un signal. <b>Impopularité (percentile)</b> : part des {fmt_int(q.N_COMBOS)} grilles plus jouées que celle-ci d'après la table estimée sur les gagnants par rang FDJ, moins pénalités de forme. <b>Joueurs attendus ×k</b> : facteur sur le nombre de joueurs de cette grille (numéro Chance inclus) par rapport à un joueur uniforme. <b>Rotation narrative</b> : le porteur #1 d'un run est inéligible comme #1 au run suivant.</p>
<div class="warn">⚠️ {q.DISCLAIMER}</div>
<div class="foot">QSC Loto v{q.VERSION} · généré par GitHub Actions · source données : historique officiel FDJ · checklist : {'OK' if chk['ok'] else 'KO — ' + '; '.join(chk['fails'])}</div>
</body></html>"""

def build_chat(R):
    g = "\n".join(f"G{x['id']} ({x['model']}) : {fmt_nums(x['nums'])} Chance {x['chance']}" for x in R["grilles"])
    c = R["registre"]["cumul"]; p = R["popularite"]
    pop = (f" — {p['n_tirages_nums']} tirages, tranche 1-12 ×{p['tranches']['1-12']:.2f}, 41-49 ×{p['tranches']['41-49']:.2f} ; Chance les moins joués : {', '.join(str(x) for x in p['chance_tries'][:3])}.\n"
           if p["estimee"] else " (repli : table estimée indisponible ce run).\n")
    return (f"⚠️ {q.DISCLAIMER}\n\n"
            f"QSC Loto v{q.VERSION} — tirage du {R['draw_date_fr']} · {R['dataset']['n']} tirages · seed {R['seed']}\n"
            f"Jackpot {R['jackpot']['meur']:.0f} M€ ({R['jackpot']['source']}) → {len(R['grilles'])} grilles ({PRIX} €)\n\n{g}\n\n"
            f"{q.EQUIVALENCE}\n"
            f"Sélection : univers des {100*R['selection']['quantile']:.0f} % de grilles les moins jouées, Chance parmi les moins joués ; le porteur départage, il ne prédit pas.\n"
            f"Popularité : {p['source']}" + pop +
            f"Backtest : {R['backtest']['verdict']}\n"
            f"Cumul protocole vs hasard : {c['match_nums']} numéros trouvés sur {c['grilles']} grilles (attendu {c['attendu_nums']}, écart {c['ecart_nums']:+}).\n\n"
            f"⚠️ {q.DISCLAIMER}")

PRIX = None

def main():
    global PRIX
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default="loto_MASTER.csv")
    ap.add_argument("--prizes", default="loto_PRIZES.csv")
    ap.add_argument("--out", default="output")
    ap.add_argument("--jackpot", type=float, default=os.environ.get("JACKPOT_MEUR") or None)
    ap.add_argument("--today", default=None)
    ap.add_argument("--n-grilles", type=int, default=int(os.environ.get("N_GRILLES") or 0))
    ap.add_argument("--n-sim", type=int, default=5000)
    a = ap.parse_args()
    os.makedirs(os.path.join(a.out, "history"), exist_ok=True)
    today = date.fromisoformat(a.today) if a.today else date.today()
    draw_date = q.next_draw_date(today); draw_iso = draw_date.isoformat(); seed = q.seed_from_draw_date(draw_iso)
    jours = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
    draw_fr = f"{jours[draw_date.weekday()]} {draw_date.day:02d}/{draw_date.month:02d}/{draw_date.year}"

    draws = q.load_master(a.csv)
    ok, alerts = q.integrity_check(draws)
    fp = q.dataset_fingerprint(draws, "csv"); fp["integrite"] = ok; fp["alertes"] = alerts
    if draws[-1][0] >= draw_iso:
        print(f"Le tirage {draw_iso} est déjà dans le dataset : rien à générer.", file=sys.stderr); sys.exit(0)
    meta_p = os.path.join(a.out, "fdj_meta.json")
    fdj_meta = json.load(open(meta_p, encoding="utf-8")) if os.path.exists(meta_p) else None

    reg_path = os.path.join(a.out, "registre.csv"); rows = load_registre(reg_path)
    rapproche = reconcile(rows, draws); cum = cumul(rows)

    prev_first = None
    hist_files = sorted(f for f in os.listdir(os.path.join(a.out, "history")) if f < f"{draw_iso}.json")
    if hist_files:
        prev = json.load(open(os.path.join(a.out, "history", hist_files[-1]), encoding="utf-8"))
        prev_first = prev.get("porteurs", [None])[0]

    pop_table = P.estimate(a.prizes, draws); q.set_popularity(pop_table)
    pop_info = popularity_report(pop_table)
    with open(os.path.join(a.out, "popularite.json"), "w", encoding="utf-8") as f: json.dump(pop_info, f, ensure_ascii=False, indent=1)

    bt, meta = q.backtest_all(draws, n_sim=a.n_sim, seed=seed)
    sb, smeta = q.backtest_chance(draws, n_sim=a.n_sim, seed=seed)
    chi2, pchi = q.chi2_uniformity(draws)

    jp = estimate_jackpot(fdj_meta, a.jackpot); n = q.n_grids(jp["meur"], plancher=a.n_grilles)
    PRIX = f"{n * q.PRIX_GRILLE:.2f}".replace(".", ",")
    order = q.rank_selectors(bt, ineligible_first=prev_first)
    ch_order = sorted(sb, key=lambda k: -sb[k]["edge"])
    universe, gp_thr, n_total = q.impopular_universe(); ch_univ = q.chance_universe()
    grids, avoid, avoid_ch = [], [], []
    for i in range(n):
        model = order[i % len(order)]
        g = q.best_grid(model, draws, avoid=avoid, max_ov=2, universe=universe) or q.best_grid(model, draws, avoid=avoid, max_ov=3, universe=universe)
        if g is None:
            print(f"Aucune grille admissible pour {model} (grille {i+1}/{n}) : réduis n_grilles.", file=sys.stderr); sys.exit(5)
        avoid.append(g)
        cm = ch_order[i % len(ch_order)]
        ch = q.best_chance(cm, draws, avoid=avoid_ch, universe=ch_univ); avoid_ch.append(ch)
        grids.append({"id": i+1, "model": model, "nums": list(g), "chance_model": cm, "chance": ch,
                      "sum": sum(g), "even": sum(1 for x in g if x % 2 == 0), "low": sum(1 for x in g if x <= 24),
                      "anti_share": round(q.anti_share_score(g), 1), "rel_popularity": round(q.relative_popularity(g, ch), 3),
                      "cowinners": round(q.expected_cowinners(g, ch), 3)})
    selection = {"regle": "univers = décile le moins joué des C(49,5) hors motifs pénalisés ; le porteur départage à l'intérieur",
                 "quantile": q.IMPOP_QUANTILE, "univers_grilles": len(universe), "total_grilles": n_total, "seuil_gp": round(gp_thr, 4),
                 "chance_univers": ch_univ, "max_recouvrement": 2, "popularite_source": q.POP["source"]}
    cons = q.consensus_grid(bt, draws)
    consensus = {"grid": list(cons) if cons else None,
                 "message": (f"{fmt_nums(cons)} (pondérée sur les seuls modèles significatifs)" if cons else
                             "non calculable ce jour : aucun modèle ne surperforme le hasard après correction — la consensus dégénère volontairement.")}
    deja = {(r["draw_date"], str(r["grid"])) for r in rows}
    for g in grids:
        if (draw_iso, str(g["id"])) in deja: continue
        rows.append({"run_date": today.isoformat(), "draw_date": draw_iso, "grid": g["id"], "model": g["model"],
                     "nums": "-".join(map(str, g["nums"])), "chance": g["chance"], "seed": seed,
                     "real_nums": "", "real_chance": "", "match_nums": "", "match_chance": ""})
    save_registre(reg_path, rows)

    slim = lambda d: {k: {kk: vv for kk, vv in v.items() if kk != "points"} for k, v in d.items()}
    R = {"version": q.VERSION, "jeu": q.GAME, "run_date": today.isoformat(), "draw_date": draw_iso, "draw_date_fr": draw_fr, "seed": seed,
         "dataset": fp, "jackpot": jp, "n_grilles": n, "n_grilles_regle_jackpot": q.n_grids(jp["meur"]), "n_grilles_plancher": a.n_grilles or None,
         "porteurs": order, "porteur_precedent_inéligible": prev_first, "selection": selection, "popularite": pop_info,
         "grilles": grids, "consensus": consensus,
         "backtest": {"meta": meta, "numeros": slim(bt), "verdict": q.verdict(bt, meta), "chance": slim(sb), "chance_meta": smeta,
                      "chance_verdict": ("Au moins un modèle Chance significatif après correction — prudence." if any(r["significant"] for r in sb.values())
                                         else "Aucun modèle Chance ne se distingue du hasard : choix méthodologique par rotation.")},
         "chi2": {"stat": round(chi2, 2), "p": round(pchi, 3)}, "registre": {"rapproche": rapproche, "cumul": cum},
         "disclaimer": q.DISCLAIMER, "equivalence": q.EQUIVALENCE}
    R["checklist"] = {"ok": True, "fails": []}
    html_text = build_html(R); chat = build_chat(R)
    okc, fails = q.checklist(html_text, chat, fp, seed)
    R["checklist"] = {"ok": okc, "fails": fails}; html_text = build_html(R); R["chat_summary"] = chat
    with open(os.path.join(a.out, "latest.html"), "w", encoding="utf-8") as f: f.write(html_text)
    with open(os.path.join(a.out, "latest.json"), "w", encoding="utf-8") as f: json.dump(R, f, ensure_ascii=False, indent=1)
    with open(os.path.join(a.out, "history", f"{draw_iso}.json"), "w", encoding="utf-8") as f: json.dump(R, f, ensure_ascii=False, indent=1)
    print(chat); print(f"\nchecklist : {'OK' if okc else 'KO ' + str(fails)}")
    sys.exit(0 if okc else 4)

if __name__ == "__main__":
    main()
