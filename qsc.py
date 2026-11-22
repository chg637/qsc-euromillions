#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
qsc.py : point d'entrée unique du protocole QSC (EuroMillions et Loto).

    python3 qsc.py jeux                      liste les jeux connus
    python3 qsc.py run <jeu> [options]       run du tirage du jour (options passées au run du jeu)
    python3 qsc.py update <jeu> [options]    mise à jour des tirages (options passées au script du jeu)
    python3 qsc.py test [<jeu>|golden]       tests du jeu, ou du golden ; sans argument : tout

<jeu> : euromillions ou loto (voir qsc_games.py).

Ce n'est qu'un aiguilleur : il lance les scripts existants avec le même interpréteur et dans le
même dossier que les workflows (racine pour l'EuroMillions, loto/ pour le Loto), et renvoie leur
code de sortie. Les options et les chemins par défaut sont donc strictement ceux des scripts :
`python3 qsc.py run loto --today 2026-11-20` équivaut à `cd loto && python3 run_loto.py --today 2026-11-20`.
"""
import os, subprocess, sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
import qsc_games

# jeu -> (dossier de travail, script run, script update, test). Chemins relatifs à ROOT.
ROUTES = {
    "euromillions": (".",    "run_qsc.py",  "update_master.py", "test_euromillions.py"),
    "loto":         ("loto", "run_loto.py", "update_loto.py",   "test_loto.py"),
}
assert set(ROUTES) == set(qsc_games.JEUX), "ROUTES et qsc_games.JEUX doivent lister les mêmes jeux"


def lancer(jeu, script, args):
    wd = os.path.join(ROOT, ROUTES[jeu][0])
    return subprocess.run([sys.executable, os.path.join(wd, script), *args], cwd=wd).returncode


def usage(code=2):
    print(__doc__.strip(), file=sys.stderr if code else sys.stdout)
    return code


def main(argv):
    if not argv or argv[0] in ("-h", "--help", "help"):
        return usage(0 if argv else 2)
    cmd, rest = argv[0], argv[1:]
    if cmd == "jeux":
        for k, g in qsc_games.JEUX.items():
            print(f"{k:13s} {g.nom:13s} {g.k_pick} numéros parmi {g.n_pool} + {g.bonus} ({g.bonus_pool})  "
                  f"{g.prix_grille:.2f} €/grille  tirages {','.join('lun mar mer jeu ven sam dim'.split()[d] for d in g.draw_weekdays)}")
        return 0
    if cmd in ("run", "update"):
        if not rest or rest[0] not in ROUTES:
            print(f"jeu attendu parmi : {', '.join(ROUTES)}", file=sys.stderr); return 2
        jeu = rest[0]
        return lancer(jeu, ROUTES[jeu][1 if cmd == "run" else 2], rest[1:])
    if cmd == "test":
        cible = rest[0] if rest else "tout"
        if cible not in (*ROUTES, "golden", "tout"):
            print(f"cible attendue parmi : {', '.join(ROUTES)}, golden", file=sys.stderr); return 2
        jeux = list(ROUTES) if cible == "tout" else [cible] if cible in ROUTES else []
        rcs = [lancer(j, ROUTES[j][3], []) for j in jeux]
        if cible in ("tout", "golden"):
            rcs.append(subprocess.run([sys.executable, os.path.join(ROOT, "tests", "test_golden.py")], cwd=ROOT).returncode)
        return 0 if all(rc == 0 for rc in rcs) else 1
    return usage()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
