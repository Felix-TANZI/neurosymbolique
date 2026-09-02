"""Mesure de la memoire disponible et de celle requise par la specialisation.

Le script etablit si la machine dispose de la memoire necessaire, et ou celle-ci
est consommee. Une correction fondee sur une hypothese non verifiee risquerait
de traiter un symptome plutot que sa cause.

Emploi:
    python -m scripts.mesurer_memoire
"""

import gc
import os
import sys

import torch

from src.neuronal.modele_preentraine import (
    ConfigurationPreentrainee,
    PerteConjointeAlignee,
    creer_modele_preentraine,
)


def memoire_du_processus() -> float:
    """Restitue la memoire occupee par le processus, en megaoctets."""
    try:
        import psutil

        return psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024
    except ImportError:
        return -1.0


def memoire_de_la_machine() -> tuple[float, float]:
    """Restitue la memoire totale et disponible, en megaoctets."""
    try:
        import psutil

        memoire = psutil.virtual_memory()
        return memoire.total / 1024 / 1024, memoire.available / 1024 / 1024
    except ImportError:
        return -1.0, -1.0


def afficher(etape: str) -> None:
    """Affiche la memoire occupee a une etape donnee."""
    processus = memoire_du_processus()
    _, disponible = memoire_de_la_machine()
    print(f"  {etape:<44} processus {processus:8.0f} Mo | libre {disponible:8.0f} Mo")


def main() -> int:
    """Mesure la consommation aux etapes successives de la specialisation."""
    totale, disponible = memoire_de_la_machine()

    if totale < 0:
        print("psutil est absent. Installez-le: pip install psutil")
        return 1

    print(f"Memoire de la machine: {totale:.0f} Mo")
    print(f"Memoire disponible   : {disponible:.0f} Mo\n")

    print("Consommation par etape:")
    afficher("demarrage")

    configuration = ConfigurationPreentrainee(
        nombre_d_intentions=15, nombre_d_etiquettes=15, couches_gelees=10
    )
    modele = creer_modele_preentraine(configuration)
    afficher("modele charge")

    perte = PerteConjointeAlignee(2.0)
    optimiseur = torch.optim.AdamW(
        [p for p in modele.parameters() if p.requires_grad], lr=2e-5
    )
    afficher("optimiseur constitue")

    indices = torch.randint(0, 32000, (16, 32))
    masque = torch.ones(16, 32, dtype=torch.long)
    intentions = torch.randint(0, 15, (16,))
    etiquettes = torch.randint(0, 15, (16, 32))

    for pas in range(1, 4):
        optimiseur.zero_grad(set_to_none=True)
        totale_perte, _, _ = perte(
            modele(indices, masque), intentions, etiquettes, masque
        )
        totale_perte.backward()
        optimiseur.step()
        afficher(f"apres {pas} pas d'entrainement")

    copie = {nom: valeur.clone() for nom, valeur in modele.state_dict().items()}
    afficher("une copie des parametres conservee")

    seconde = {nom: valeur.clone() for nom, valeur in modele.state_dict().items()}
    afficher("deux copies conservees")

    del copie, seconde
    gc.collect()
    afficher("copies liberees")

    poids = sum(
        valeur.numel() * valeur.element_size()
        for valeur in modele.state_dict().values()
    ) / 1024 / 1024
    print(f"\nUne copie des parametres occupe {poids:.0f} Mo")

    _, restante = memoire_de_la_machine()
    print(f"Memoire libre en fin de mesure: {restante:.0f} Mo")

    return 0


if __name__ == "__main__":
    sys.exit(main())