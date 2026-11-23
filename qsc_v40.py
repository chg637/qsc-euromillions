# -*- coding: utf-8 -*-
"""
Alias de transition : qsc_v40 est devenu qsc_euromillions (le nom du module ne porte plus la version,
elle vit dans qsc_euromillions.VERSION).

`import qsc_v40` renvoie le MÊME objet module que `import qsc_euromillions` (pas une copie), donc
l'état partagé (table de popularité, caches) reste unique. Garde les anciens appels qui nomment
encore qsc_v40 : prompts des tâches planifiées, scripts locaux. À supprimer une fois ceux-ci migrés.
"""
import sys
import qsc_euromillions
sys.modules[__name__] = qsc_euromillions
