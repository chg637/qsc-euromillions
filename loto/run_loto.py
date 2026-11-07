# -*- coding: utf-8 -*-
"""
run_loto.py — Pipeline QSC Loto v2.0, exécuté par GitHub Actions les jours de tirage (lun/mer/sam).

Étapes : chargement + intégrité → rapprochement du run précédent (registre append-only, en euros)
→ popularité estimée sur les gagnants par rang FDJ → backtest numéros / Chance (DIAGNOSTIC : step 1,
null exacte, max-stat) → chi² → jackpot officiel (fdj.fr, repli estimation) → nombre de grilles
(1 par défaut, paliers 100/150/200 M€, borné par le budget annuel de 520 € tous jeux confondus)
→ tirage uniforme dans l'univers impopulaire (A1) → latest.json / latest.html / history/<date>.json
→ checklist.

Usage : python3 run_loto.py [--jackpot 8] [--today 2026-10-14] [--n-grilles 1] [--no-fdj]
Sortie : 0 si checklist verte, 4 sinon (le livrable est quand même écrit, marqué KO).
"""
import argparse, csv, json, math, os, re, statistics, sys, urllib.request, html as H
from datetime import date
import qsc_loto as q
import popularite_loto as P

REG_FIELDS = ["run_date", "draw_date", "grid", "model", "nums", "chance", "seed", "jackpot_meur",
              "real_nums", "real_chance", "match_nums", "match_chance",
              "rang", "gain_eur", "gagnants_rang", "gagnants_attendus_rang"]
MODEL = "uniforme-univers-R7"
AUTRE_PRIX = 2.50            # prix d'une grille EuroMillions (budget commun)

# ------------------------------------------------------------------ registre (A4 : en euros)

def load_registre(path):
    if not os.path.exists(path): return []
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f, delimiter=";"))
    for r in rows:                       # lignes de la v1.0 : colonnes absentes → vides
        for k in REG_FIELDS: r.setdefault(k, "")
    return rows

def save_registre(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=REG_FIELDS, delimiter=";", lineterminator="\n", extrasaction="ignore")
        w.writeheader()
        for r in rows: w.writerow(r)

def load_amounts(api_dir):
    """Montants par rang (euros) conservés par update_loto.py : {date: {rang: euros}}."""
    out = {}
    if not os.path.isdir(api_dir): return out
    for fn in sorted(os.listdir(api_dir)):
        if not fn.endswith(".json"): continue
        try:
            for it in json.load(open(os.path.join(api_dir, fn), encoding="utf-8")):
                out[it["date"]] = {int(k): float(v) for k, v in it["rapports"].items()}
        except Exception as e:
            print(f"api_cache {fn} illisible : {e}", file=sys.stderr)
    return out

def reconcile(rows, draws, prizes, amounts):
    """Remplit numéros/Chance trouvés, puis rang, gain réel et gagnants observés/attendus quand les
       gagnants ET les montants du tirage sont connus (sinon la ligne reste ouverte et sera reprise
       au run suivant). Retourne les lignes rapprochées ce run."""
    by_date = {d: (n, c) for d, n, c in draws}
    done = []
    for r in rows:
        if r["match_nums"] == "" and r["draw_date"] in by_date:
            rn, rc = by_date[r["draw_date"]]
            gn = {int(x) for x in r["nums"].split("-")}
            r["real_nums"] = "-".join(map(str, rn)); r["real_chance"] = str(rc)
            r["match_nums"] = str(len(gn & set(rn))); r["match_chance"] = "1" if int(r["chance"]) == rc else "0"
            done.append(r)
        if r["match_nums"] != "" and r["rang"] == "" and r["draw_date"] in prizes and r["draw_date"] in amounts:
            pz = prizes[r["draw_date"]]
            if pz["era"] != 9: continue          # règle 2008-2017 : rangs différents, hors périmètre du registre
            rg = q.rang_of(int(r["match_nums"]), int(r["match_chance"]))
            r["rang"] = str(rg)
            r["gain_eur"] = amounts[r["draw_date"]].get(rg, 0.0) if rg else 0.0
            if rg:
                N = q.ventes_estimees(pz["w"])
                r["gagnants_rang"] = pz["w"].get(rg, "")
                r["gagnants_attendus_rang"] = round(N * q.p_of_rank()[rg], 1) if N else ""
    return done

def depense_registre(rows, annee, prix, hors_tirage=None):
    """Dépense de l'année pour un registre : une grille inscrite = une grille jouée. Les grilles du tirage
       `hors_tirage` ne comptent pas (un re-run ne compte pas deux fois ses grilles)."""
    return prix * sum(1 for r in rows if r["draw_date"][:4] == str(annee) and r["draw_date"] != hors_tirage)

def cumul(rows, annee, autre_depense=0.0):
    played = [r for r in rows if r["match_nums"] != ""]
    n = len(played)
    mn = sum(int(r["match_nums"]) for r in played); mc = sum(int(r["match_chance"]) for r in played)
    ic_n = 1.96 * math.sqrt(n * _var_matches()) if n else 0.0
    ic_c = 1.96 * math.sqrt(n * q.CHANCE_BASELINE * (1 - q.CHANCE_BASELINE)) if n else 0.0
    gains = sum(float(r["gain_eur"] or 0) for r in played)
    mise = q.PRIX_GRILLE * n
    en_euros = [r for r in played if r["rang"] != ""]
    obs = sum(float(r["gagnants_rang"]) for r in en_euros if r["gagnants_rang"] not in ("", None))
    att = sum(float(r["gagnants_attendus_rang"]) for r in en_euros if r["gagnants_attendus_rang"] not in ("", None))
    depense_loto = q.PRIX_GRILLE * sum(1 for r in rows if r["draw_date"][:4] == str(annee))
    return {"grilles": n, "match_nums": mn, "attendu_nums": round(q.BASELINE * n, 2),
            "ecart_nums": round(mn - q.BASELINE * n, 2), "ic95_nums": round(ic_n, 2),
            "match_chance": mc, "attendu_chance": round(q.CHANCE_BASELINE * n, 2),
            "ecart_chance": round(mc - q.CHANCE_BASELINE * n, 2), "ic95_chance": round(ic_c, 2),
            "meilleur": max((int(r["match_nums"]) for r in played), default=0),
            "mise_eur": round(mise, 2), "gains_eur": round(gains, 2), "solde_eur": round(gains - mise, 2),
            "grilles_en_euros": len(en_euros), "rangs_atteints": sum(1 for r in en_euros if int(r["rang"] or 0) > 0),
            "gagnants_observes": round(obs, 1), "gagnants_attendus": round(att, 1),
            "taux_partage": round(obs / att, 3) if att else None,
            "depense_loto_annee_eur": round(depense_loto, 2), "depense_autres_jeux_eur": round(autre_depense, 2),
            "depense_annee_eur": round(depense_loto + autre_depense, 2), "budget_eur": q.BUDGET_EUR, "annee": annee}

def _var_matches():
    """Variance du nombre de numéros en commun entre une grille et un tirage (hypergéométrique 5 parmi 49)."""
    N, K, n = q.N_POOL, q.K_PICK, q.K_PICK
    return n * (K / N) * (1 - K / N) * (N - n) / (N - 1)

# ------------------------------------------------------------------ jackpot (A3)

FDJ_URL = "https://www.fdj.fr/jeux-de-tirage/loto"
MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre",
        "octobre", "novembre", "décembre"]

def jackpot_fdj(draw_date, timeout=20):
    """Montant officiel du prochain tirage lu sur la page Loto de fdj.fr (titre « LOTO® : 13 M€ ce samedi
       7 novembre 2026 »). None si la page est inaccessible, illisible, hors plage 2-200 M€, ou si elle ne
       porte pas la date du tirage visé (page encore sur le tirage précédent)."""
    try:
        req = urllib.request.Request(FDJ_URL, headers={"User-Agent": "Mozilla/5.0 (qsc-loto/2.0)"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            page = r.read().decode("utf-8", "replace")
    except Exception as e:
        print(f"fdj.fr inaccessible : {e}", file=sys.stderr); return None
    return parse_jackpot_page(page, draw_date)

def parse_jackpot_page(page, draw_date):
    titre = re.search(r"<title>(.*?)</title>", page, re.S)
    zone = titre.group(1) if titre else page[:5000]
    date_txt = f"{draw_date.day} {MOIS[draw_date.month - 1]} {draw_date.year}"
    if not re.search(re.escape(date_txt).replace(r"\ ", r"\s+"), zone):
        print(f"fdj.fr : la page ne porte pas le tirage du {date_txt}", file=sys.stderr); return None
    m = (re.search(r"LOTO\W{0,3}\s*:\s*(\d+(?:[.,]\d+)?)\s*M\s*€", zone)
         or re.search(r"[Jj]ackpot\s+LOTO\W{0,3}\s*de\s*(\d+(?:[.,]\d+)?)\s*M\s*€", page)
         or re.search(r"(\d+(?:[.,]\d+)?)\s*millions?\s*€", page))
    if not m: return None
    v = float(m.group(1).replace(",", "."))
    return v if 2 <= v <= 200 else None

def estimate_jackpot(meta, override, draw_date, use_fdj=True):
    if override is not None:
        return {"meur": float(override), "source": "fourni", "note": "montant officiel fourni au run"}
    last = (meta or {}).get("last_draw") or {}
    jp = last.get("jackpot_eur")
    est = round(jp / 1e6 + 1, 0) if (jp and not last.get("has_winner")) else 2.0
    if use_fdj:
        off = jackpot_fdj(draw_date)
        if off is not None:
            return {"meur": off, "source": "fdj.fr", "note": f"montant officiel lu sur fdj.fr (estimation : {est:.0f} M€)"}
    if jp and not last.get("has_winner"):
        return {"meur": est, "source": "estimation",
                "note": f"fdj.fr indisponible — jackpot du {last['date']} ({jp/1e6:.0f} M€) non gagné : +1 M€ au tirage suivant"}
    return {"meur": 2.0, "source": "estimation", "note": "fdj.fr indisponible — jackpot remis à 2 M€ après un gagnant (ou source muette)"}

def ev_bas_recent(amounts, n=20):
    """EV des rangs 2 à 9 d'après les montants médians des n derniers tirages connus ; défaut si cache vide."""
    dates = sorted(amounts)[-n:]
    if not dates: return q.EV_RANGS_BAS_DEFAUT, False
    med = {r: statistics.median(amounts[d].get(r, 0.0) for d in dates) for r in range(2, 10)}
    return q.ev_rangs_bas(med), True

# ------------------------------------------------------------------ popularité

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
def fmt_eur(x): return f"{x:,.2f} €".replace(",", " ").replace(".", ",")

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
    rows_bt = "".join(f'<tr><td>{H.escape(k)}</td><td class="r mono">{r["edge"]:+.3f}</td><td class="r mono">[{r["ci"][0]:+.3f} ; {r["ci"][1]:+.3f}]</td>'
                      f'<td class="r mono">{r["p_raw"]:.2f}</td><td class="r mono">{r["p_adj"]:.2f}</td><td>{badge(r)}</td></tr>'
                      for k, r in sorted(bt.items(), key=lambda x: -x[1]["edge"]))
    rows_sb = "".join(f'<tr><td>{H.escape(k)}</td><td class="r mono">{r["edge"]:+.3f}</td><td class="r mono">[{r["ci"][0]:+.3f} ; {r["ci"][1]:+.3f}]</td><td class="r mono">{r["p_adj"]:.2f}</td><td>{badge(r)}</td></tr>'
                      for k, r in sorted(sb.items(), key=lambda x: -x[1]["edge"]))
    cards = "".join(f'<div class="card"><div class="k">G{g["id"]} · tirage uniforme dans l&rsquo;univers impopulaire</div>'
                    f'<div class="nums">{fmt_nums(g["nums"])} <b>Chance {g["chance"]}</b></div>'
                    f'<div class="k">somme {g["sum"]} · pairs {g["even"]}/5 · bas {g["low"]}/5 · impopularité {g["anti_share"]:.0f}e percentile · '
                    f'joueurs attendus ×{g["rel_popularity"]:.2f} vs grille moyenne · co-gagnants attendus au rang 1 : {g["cowinners"]:.3f} · '
                    f'EV nette théorique {fmt_eur(g["ev_nette"])}</div></div>'
                    for g in R["grilles"]) or '<div class="card"><div class="k">Aucune grille ce run : budget annuel atteint.</div></div>'
    c = R["registre"]["cumul"]; rec = R["registre"]["rapproche"]
    rec_html = ("".join(f'<tr><td>{r["draw_date"]}</td><td>G{r["grid"]}</td><td class="mono">{r["nums"]} C{r["chance"]}</td>'
                        f'<td class="mono">{r["real_nums"]} C{r["real_chance"]}</td><td class="r"><b>{r["match_nums"]}</b> num · Chance {"oui" if r["match_chance"]=="1" else "non"}</td>'
                        f'<td class="r">{("rang " + str(r["rang"]) + " · " + fmt_eur(float(r["gain_eur"] or 0))) if str(r.get("rang", "")) not in ("", "0") else "—"}</td></tr>' for r in rec)
                or '<tr><td colspan="6" class="k">aucune grille à rapprocher ce run</td></tr>')
    chk = R["checklist"]; jp = R["jackpot"]
    alerts = "".join(f"<li>{H.escape(a)}</li>" for a in fp["alertes"]) or "<li>aucune alerte</li>"
    plancher_html = ""
    if R.get("n_grilles_plancher"):
        plancher_html = ('<p class="k">Nombre de grilles relevé par l&rsquo;input <span class="mono">n_grilles</span> = '
                         f'{R["n_grilles_plancher"]} ; la règle jackpot seule en donnait {R["n_grilles_regle_jackpot"]}. '
                         'Le plancher change combien on joue, jamais la probabilité de gain de chaque grille.</p>')
    tp = c["taux_partage"]; ms = R["mise"]
    return f"""<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>QSC Loto v{q.VERSION} — tirage du {R['draw_date']}</title><style>{CSS}</style></head><body>
<h1>QSC Loto v{q.VERSION} — tirage du {R['draw_date_fr']}</h1>
<div class="k">run {R['run_date']} · seed <span class="mono">{R['seed']}</span> · dataset {fp['n']} tirages ({fp['premier']} → {fp['dernier']}) · hash <span class="mono">{fp['hash']}</span> · checklist {'<span class="b ok">verte</span>' if chk['ok'] else '<span class="b ko">KO</span>'}</div>
<div class="warn">⚠️ {q.DISCLAIMER}</div>
<h2>Grilles — {len(R['grilles'])} (jackpot {jp['meur']:.0f} M€, {jp['source']} : {H.escape(jp['note'])})</h2>
{plancher_html}
<div class="grid">{cards}</div>
<p class="k">{q.EQUIVALENCE}</p>
<p class="k"><b>Sélection v{q.VERSION}</b> : univers = les {100*R['selection']['quantile']:.0f} % de grilles les moins jouées ({fmt_int(R['selection']['univers_grilles'])} sur {fmt_int(R['selection']['total_grilles'])}, popularité moyenne ≤ {R['selection']['seuil_gp']:.3f} vs 1,00), hors motifs sur-joués ; numéro Chance parmi {', '.join(str(x) for x in R['selection']['chance_univers'])} (les moins joués). Les grilles sont tirées <b>uniformément</b> dans cet univers (seed {R['seed']}) : aucun modèle ne les choisit, parce qu'aucun modèle ne fait mieux que le hasard (voir diagnostic). Cela ne change pas la probabilité de gagner, seulement le partage attendu si la grille gagne.</p>
<p class="k"><b>Mise</b> : règle {H.escape(ms['regle'])} ; budget {fmt_eur(c['budget_eur'])} par an tous jeux confondus, dépensé {fmt_eur(c['depense_annee_eur'])} en {c['annee']} (dont {fmt_eur(c['depense_autres_jeux_eur'])} en EuroMillions, grilles de ce run comprises), reste {fmt_eur(max(0, c['budget_eur'] - c['depense_annee_eur']))}.</p>
{popularity_html(R['popularite'])}
<h2>Tableau de bord cumulatif — protocole vs hasard</h2>
<div class="grid">
<div class="card"><div class="k">Grilles jouées (registre)</div><div class="nums">{c['grilles']}</div></div>
<div class="card"><div class="k">Numéros trouvés / attendus</div><div class="nums">{c['match_nums']} / {c['attendu_nums']}</div><div class="k">écart {c['ecart_nums']:+} · IC95 % ±{c['ic95_nums']}</div></div>
<div class="card"><div class="k">Chance trouvée / attendue</div><div class="nums">{c['match_chance']} / {c['attendu_chance']}</div><div class="k">écart {c['ecart_chance']:+} · IC95 % ±{c['ic95_chance']}</div></div>
<div class="card"><div class="k">Mise / gains</div><div class="nums">{fmt_eur(c['mise_eur'])} / {fmt_eur(c['gains_eur'])}</div><div class="k">solde {fmt_eur(c['solde_eur'])} · {c['rangs_atteints']} rang(s) atteint(s) sur {c['grilles_en_euros']} grilles en euros</div></div>
<div class="card"><div class="k">Partage observé (rangs atteints)</div><div class="nums">{('×' + format(tp, '.2f')) if tp is not None else '—'}</div><div class="k">gagnants observés {fmt_int(round(c['gagnants_observes']))} / attendus sous jeu uniforme {fmt_int(round(c['gagnants_attendus']))} — &lt; 1 = les grilles jouées sont moins partagées que la moyenne</div></div>
<div class="card"><div class="k">Meilleure grille</div><div class="nums">{c['meilleur']} num.</div></div>
</div>
<h2>Rapprochement du run précédent</h2>
<div class="wrap"><table><tr><th>Tirage</th><th>Grille</th><th>Jouée</th><th>Réel</th><th class="r">Résultat</th><th class="r">Rang · gain</th></tr>{rec_html}</table></div>
<h2>Diagnostic — les modèles ne font pas mieux que le hasard (walk-forward burn-in {R['backtest']['meta']['burn_in']}, step {R['backtest']['meta']['step']}, {R['backtest']['meta']['n_points']} points)</h2>
<div class="wrap"><table><tr><th>Modèle</th><th class="r">Écart vs {q.BASELINE:.3f}</th><th class="r">IC95% bootstrap</th><th class="r">p brut</th><th class="r">p corrigé*</th><th></th></tr>{rows_bt}</table></div>
<p class="k">* p corrigé = max-statistic sur {R['backtest']['meta']['n_models']} modèles ({R['backtest']['meta']['n_sim']} simulations sous H0 hypergéométrique exact, 5 parmi 49). Seuil du meilleur modèle : écart ≥ {R['backtest']['meta']['null_max_q95']:+.3f}. <b>Verdict :</b> {H.escape(R['backtest']['verdict'])} Ce tableau est publié pour mémoire : il ne pilote plus la sélection depuis la v2.0.</p>
<div class="wrap"><table><tr><th>Modèle Chance (baseline 1/10)</th><th class="r">Écart vs 0,100</th><th class="r">IC95%</th><th class="r">p corrigé</th><th></th></tr>{rows_sb}</table></div>
<p class="k">p global Chance = {R['backtest']['chance_meta']['p_global']:.2f}.</p>
<div class="grid">
<div class="card"><div class="k">χ² d'uniformité (49 numéros, ddl 48)</div><div class="nums">{R['chi2']['stat']:.1f}</div><div class="k">p ≈ {R['chi2']['p']:.2f} — {'aucun biais matériel' if R['chi2']['p'] > 0.05 else 'écart à l uniforme : vérifier le dataset'}</div></div>
<div class="card"><div class="k">Intégrité dataset</div><ul class="k" style="margin:6px 0 0 16px;padding:0">{alerts}</ul></div>
</div>
<h2>Lexique</h2>
<p class="k"><b>Univers impopulaire</b> : les 10 % de grilles les moins jouées d'après la table de popularité estimée sur les gagnants par rang FDJ. <b>Impopularité (percentile)</b> : part des {fmt_int(q.N_COMBOS)} grilles plus jouées que celle-ci, moins les pénalités de forme. <b>Joueurs attendus ×k</b> : facteur sur le nombre de joueurs de cette grille (numéro Chance inclus) par rapport à un joueur uniforme. <b>EV nette théorique</b> : espérance de gain d'une grille (rang 1 avec partage Poisson aux ventes estimées, rangs 2 à 9 aux montants médians récents) moins {q.PRIX_GRILLE:.2f} € ; négative sauf près du maximum historique de 30 M€ où elle est proche de zéro (sensible aux ventes). <b>Partage observé</b> : sur les rangs atteints par les grilles jouées, gagnants réels divisés par les gagnants attendus si tout le monde jouait au hasard ; seule mesure du levier anti-partage, il faut des dizaines de rangs atteints pour qu'elle dise quelque chose. <b>Écart backtesté</b> : matches moyens du top-5 d'un modèle moins {q.BASELINE:.3f} ; <b>p corrigé</b> : probabilité, sous pur hasard, qu'au moins un des modèles atteigne cet écart (max-statistic).</p>
<div class="warn">⚠️ {q.DISCLAIMER}</div>
<div class="foot">QSC Loto v{q.VERSION} · généré par GitHub Actions · source données : historique officiel FDJ · jackpot : {jp['source']} · checklist : {'OK' if chk['ok'] else 'KO — ' + '; '.join(chk['fails'])}</div>
</body></html>"""

def build_chat(R):
    g = "\n".join(f"G{x['id']} : {fmt_nums(x['nums'])} Chance {x['chance']}  (joueurs attendus ×{x['rel_popularity']:.2f}, EV nette {x['ev_nette']:+.2f} €)" for x in R["grilles"]) \
        or "Aucune grille ce run : budget annuel atteint."
    c = R["registre"]["cumul"]; p = R["popularite"]; tp = c["taux_partage"]
    pop = (f" — {p['n_tirages_nums']} tirages, tranche 1-12 ×{p['tranches']['1-12']:.2f}, 41-49 ×{p['tranches']['41-49']:.2f} ; Chance les moins joués : {', '.join(str(x) for x in p['chance_tries'][:3])}.\n"
           if p["estimee"] else " (repli : table estimée indisponible ce run).\n")
    return (f"⚠️ {q.DISCLAIMER}\n\n"
            f"QSC Loto v{q.VERSION} — tirage du {R['draw_date_fr']} · {R['dataset']['n']} tirages · seed {R['seed']}\n"
            f"Jackpot {R['jackpot']['meur']:.0f} M€ ({R['jackpot']['source']}) → {len(R['grilles'])} grille(s) ({R['mise']['regle']})"
            + (f" (plancher n_grilles = {R['n_grilles_plancher']})" if R.get("n_grilles_plancher") else "") + f"\n\n{g}\n\n"
            f"{q.EQUIVALENCE}\n"
            f"Sélection : tirage uniforme (seed) parmi les {100*R['selection']['quantile']:.0f} % de grilles les moins jouées, Chance parmi les moins jouées. Aucun modèle ne choisit les numéros : {R['backtest']['verdict']}\n"
            f"Popularité : {p['source']}" + pop +
            f"Budget : {c['depense_annee_eur']:.2f} € dépensés en {c['annee']} sur {c['budget_eur']:.0f} € (dont {c['depense_autres_jeux_eur']:.2f} € en EuroMillions).\n"
            f"Cumul : {c['match_nums']} numéros trouvés sur {c['grilles']} grilles (attendu {c['attendu_nums']}, écart {c['ecart_nums']:+} ± {c['ic95_nums']}) · mise {c['mise_eur']:.2f} €, gains {c['gains_eur']:.2f} €"
            + (f" · partage observé ×{tp:.2f} sur {c['rangs_atteints']} rang(s)" if tp is not None else "") + ".\n\n"
            f"⚠️ {q.DISCLAIMER}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default="loto_MASTER.csv")
    ap.add_argument("--prizes", default="loto_PRIZES.csv")
    ap.add_argument("--out", default="output")
    ap.add_argument("--autre-registre", default=os.path.join("..", "output", "registre.csv"),
                    help="registre EuroMillions, pour le budget annuel commun (absent = 0 €)")
    ap.add_argument("--jackpot", type=float, default=os.environ.get("JACKPOT_MEUR") or None)
    ap.add_argument("--today", default=None)
    ap.add_argument("--n-grilles", type=int, default=int(os.environ.get("N_GRILLES") or 0),
                    help="plancher du nombre de grilles ; ne peut que relever la règle jackpot (le budget borne toujours)")
    ap.add_argument("--no-fdj", action="store_true", help="ne pas interroger fdj.fr (tests, rejeu)")
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

    # registre : rapprochement (en euros) + budget commun
    prizes = P.load_prizes(a.prizes)
    amounts = load_amounts(os.path.join(a.out, "api_cache"))
    reg_path = os.path.join(a.out, "registre.csv"); rows = load_registre(reg_path)
    rapproche = reconcile(rows, draws, prizes, amounts)
    autres = load_registre(a.autre_registre)
    autre_depense = AUTRE_PRIX * sum(1 for r in autres if r["draw_date"][:4] == str(draw_date.year))
    depense = depense_registre(rows, draw_date.year, q.PRIX_GRILLE, hors_tirage=draw_iso) + autre_depense

    # popularité estimée sur les gagnants par rang
    pop_table = P.estimate(a.prizes, draws); q.set_popularity(pop_table)
    pop_info = popularity_report(pop_table)
    with open(os.path.join(a.out, "popularite.json"), "w", encoding="utf-8") as f: json.dump(pop_info, f, ensure_ascii=False, indent=1)

    # diagnostic (ne pilote rien)
    bt, meta = q.backtest_all(draws, n_sim=a.n_sim, seed=seed)
    sb, smeta = q.backtest_chance(draws, n_sim=a.n_sim, seed=seed)
    chi2, pchi = q.chi2_uniformity(draws)

    # jackpot officiel / nombre de grilles sous budget commun
    jp = estimate_jackpot(fdj_meta, a.jackpot, draw_date, use_fdj=not a.no_fdj)
    n = q.n_grids(jp["meur"], plancher=a.n_grilles, depense_annee=depense)
    regle_txt = f"1 grille, +1 à 100, 150 et 200 M€ ({q.n_grids_regle(jp['meur'])} pour {jp['meur']:.0f} M€)"

    # grilles : tirage uniforme dans l'univers impopulaire (A1)
    universe, gp_thr, n_total = q.impopular_universe(); ch_univ = q.chance_universe()
    last_era9 = next((prizes[d] for d in sorted(prizes, reverse=True) if prizes[d]["era"] == 9), None)
    ventes = (q.ventes_estimees(last_era9["w"]) if last_era9 else None) or q.VENTES_DEFAUT
    ev_bas, ev_bas_mesure = ev_bas_recent(amounts)
    grids = []
    for i, (g, ch) in enumerate(q.draw_grids(seed, n, universe=universe, chance_univ=ch_univ)):
        rp = q.relative_popularity(g, ch)
        grids.append({"id": i+1, "nums": list(g), "chance": ch,
                      "sum": sum(g), "even": sum(1 for x in g if x % 2 == 0), "low": sum(1 for x in g if x <= 24),
                      "anti_share": round(q.anti_share_score(g), 1), "rel_popularity": round(rp, 3),
                      "cowinners": round(q.expected_cowinners(g, ch, n_tickets=ventes), 3),
                      "ev_nette": round(q.ev_grille(jp["meur"], rp, ventes=ventes, ev_bas=ev_bas), 3)})
    selection = {"regle": "univers = décile le moins joué des C(49,5) hors motifs pénalisés ; tirage uniforme par seed à l'intérieur, "
                          "recouvrement ≤ 2 numéros, numéros Chance distincts tant que possible",
                 "quantile": q.IMPOP_QUANTILE, "univers_grilles": len(universe), "total_grilles": n_total, "seuil_gp": round(gp_thr, 4),
                 "chance_univers": ch_univ, "max_recouvrement": 2, "popularite_source": q.POP["source"],
                 "ventes_estimees": round(ventes), "ev_rangs_bas": round(ev_bas, 3), "ev_rangs_bas_mesure": ev_bas_mesure}

    # registre : ajout des grilles du jour (idempotent, par (tirage, n° de grille))
    deja = {(r["draw_date"], str(r["grid"])) for r in rows}
    for g in grids:
        if (draw_iso, str(g["id"])) in deja: continue
        rows.append({"run_date": today.isoformat(), "draw_date": draw_iso, "grid": g["id"], "model": MODEL,
                     "nums": "-".join(map(str, g["nums"])), "chance": g["chance"], "seed": seed, "jackpot_meur": jp["meur"],
                     "real_nums": "", "real_chance": "", "match_nums": "", "match_chance": "",
                     "rang": "", "gain_eur": "", "gagnants_rang": "", "gagnants_attendus_rang": ""})
    save_registre(reg_path, rows)
    cum = cumul(rows, draw_date.year, autre_depense=autre_depense)

    slim = lambda d: {k: {kk: vv for kk, vv in v.items() if kk != "points"} for k, v in d.items()}
    R = {"version": q.VERSION, "jeu": q.GAME, "run_date": today.isoformat(), "draw_date": draw_iso, "draw_date_fr": draw_fr, "seed": seed,
         "dataset": fp, "jackpot": jp, "n_grilles": n, "n_grilles_regle_jackpot": q.n_grids_regle(jp["meur"]), "n_grilles_plancher": a.n_grilles or None,
         "mise": {"regle": regle_txt, "budget_eur": q.BUDGET_EUR, "prix_grille": q.PRIX_GRILLE, "depense_annee_avant_run": round(depense, 2),
                  "dont_autres_jeux": round(autre_depense, 2)},
         "selection": selection, "popularite": pop_info, "grilles": grids,
         "backtest": {"role": "diagnostic — ne pilote pas la sélection", "meta": meta, "numeros": slim(bt), "verdict": q.verdict(bt, meta),
                      "chance": slim(sb), "chance_meta": smeta},
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
