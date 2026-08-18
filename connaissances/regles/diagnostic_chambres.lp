% Analyse d'admissibilite du service de gestion des chambres
%
% Ce programme etablit, pour chaque paire reservation-chambre, si la chambre
% est admissible et, a defaut, pour quels motifs elle est ecartee. Il ne
% comporte aucun choix ni aucune contrainte: son resultat est un constat sur
% la situation, toujours calculable, y compris lorsqu'aucune affectation n'est
% possible.
%
% Ce fichier est edite par un administrateur habilite, sans modification ni
% recompilation du code source. Tout motif ajoute ici doit correspondre a une
% contrainte dure de decision_chambres.lp.

#defined chevauchent/2.
#defined occupation_existante/2.
#defined exigence_obligatoire/2.
#defined dispose_de/2.

rejet(R, C, non_prete) :-
    a_affecter(R), chambre(C),
    etat_proprete(C, Etat), Etat != prete.

rejet(R, C, bloquee) :-
    a_affecter(R), chambre(C),
    etat_technique(C, bloquee).

rejet(R, C, non_libre) :-
    a_affecter(R), chambre(C),
    etat_occupation(C, Etat), Etat != libre.

rejet(R, C, sejour_en_conflit) :-
    a_affecter(R), chambre(C),
    occupation_existante(C, R2), chevauchent(R, R2).

rejet(R, C, equipement_absent(E)) :-
    a_affecter(R), chambre(C),
    exigence_obligatoire(R, E),
    not dispose_de(C, E).

rejet(R, C, capacite_insuffisante) :-
    a_affecter(R), chambre(C),
    capacite(C, Cap), nombre_personnes(R, N), N > Cap.

rejet(R, C, categorie_inferieure) :-
    a_affecter(R), chambre(C),
    categorie(C, RangObtenu), categorie_contractee(R, RangDu),
    RangObtenu < RangDu.

rejet_quelconque(R, C) :- rejet(R, C, _).

% Une chambre est admissible lorsqu'aucun motif ne l'ecarte.
admissible(R, C) :- a_affecter(R), chambre(C), not rejet_quelconque(R, C).

#show rejet/3.
#show admissible/2.