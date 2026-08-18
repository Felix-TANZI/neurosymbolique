% Situation de test : la 312 subit un degat des eaux, R-4471 doit etre relogee.

a_affecter(r4471).
nombre_personnes(r4471, 2).
categorie_contractee(r4471, 1).
exigence_obligatoire(r4471, lit_double).
exigence_souhaitee(r4471, balcon).
etage_souhaite(r4471, 4).

chambre(c312). etat_proprete(c312, prete). etat_technique(c312, bloquee).
etat_occupation(c312, libre). capacite(c312, 2). categorie(c312, 1).
etage(c312, 3). dispose_de(c312, lit_double).

chambre(c405). etat_proprete(c405, a_controler). etat_technique(c405, operationnelle).
etat_occupation(c405, libre). capacite(c405, 2). categorie(c405, 1).
etage(c405, 4). dispose_de(c405, lit_double). dispose_de(c405, balcon).

chambre(c407). etat_proprete(c407, prete). etat_technique(c407, operationnelle).
etat_occupation(c407, libre). capacite(c407, 2). categorie(c407, 1).
etage(c407, 4). dispose_de(c407, lit_double).

chambre(c512). etat_proprete(c512, prete). etat_technique(c512, operationnelle).
etat_occupation(c512, libre). capacite(c512, 4). categorie(c512, 4).
etage(c512, 5). dispose_de(c512, lit_double). dispose_de(c512, balcon).

chambre(c201). etat_proprete(c201, prete). etat_technique(c201, operationnelle).
etat_occupation(c201, libre). capacite(c201, 1). categorie(c201, 1).
etage(c201, 2). dispose_de(c201, lit_simple).

poids(souhait_non_satisfait, 3).
poids(surclassement, 1).
poids(hors_secteur, 2).
poids(etage_non_souhaite, 1).