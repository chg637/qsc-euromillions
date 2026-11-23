# -*- coding: utf-8 -*-
"""Alias de transition : test_qsc_v40.py est devenu test_euromillions.py. Lance ce dernier.
Garde les anciens appels (prompts des tâches planifiées). À supprimer une fois ceux-ci migrés."""
import os, runpy
runpy.run_path(os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_euromillions.py"), run_name="__main__")
