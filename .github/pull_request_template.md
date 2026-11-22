## Quoi

<!-- Un changement par PR. Dire ce qui change et pourquoi. -->

## Touche-t-il à la méthode ?

- [ ] Non : le test golden passe sans mise à jour des références
- [ ] Oui : références golden mises à jour (`python3 tests/test_golden.py --update`) et diff relu, expliqué ci-dessous

## Vérifications

- [ ] `python3 qsc.py test` passe en local
- [ ] Aucun fichier de données ou de sortie édité à la main (`output/`, `*_MASTER.csv`, `*_PRIZES.csv`)
- [ ] `qsc_core.py` ou `qsc_games.py` touché : relecture à deux
