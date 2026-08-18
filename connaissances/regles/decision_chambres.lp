% Decision d'affectation du service de gestion des chambres
%
% Ce programme choisit une affectation parmi les chambres admissibles. Les
% contraintes dures eliminent les affectations non conformes: une solution
% violant l'une d'elles n'est jamais engendree. Les preferences souples
% ordonnent les solutions admissibles sans jamais en rendre une admissible.
%
% Ce fichier est edite par un administrateur habilite, sans modification ni
% recompilation du code source.

#defined chevauchent/2.
#defined occupation_existante/2.
#defined exigence_obligatoire/2.
#defined exigence_souhaitee/2.
#defined dispose_de/2.
#defined secteur_prefere/2.
#defined secteur/2.
#defined etage_souhaite/2.

% ---------------------------------------------------------------------
% Espace des affectations possibles
% ---------------------------------------------------------------------

{ affectation(R, C) : chambre(C) } = 1 :- a_affecter(R).

% ---------------------------------------------------------------------
% Deductions intermediaires
% ---------------------------------------------------------------------

disponible(C) :-
    chambre(C),
    etat_proprete(C, prete),
    etat_technique(C, T), T != bloquee,
    etat_occupation(C, libre).

exigence_manquante(R, E) :-
    exigence_obligatoire(R, E),
    affectation(R, C),
    not dispose_de(C, E).

surclassement(R, C) :-
    affectation(R, C),
    categorie(C, RangObtenu),
    categorie_contractee(R, RangDu),
    RangObtenu > RangDu.

% ---------------------------------------------------------------------
% Contraintes dures
% ---------------------------------------------------------------------

% CD-1  Une chambre indisponible ne peut etre affectee.
:- affectation(_, C), not disponible(C).

% CD-2  Deux sejours qui se chevauchent ne peuvent partager une chambre.
:- affectation(R1, C), affectation(R2, C), R1 != R2, chevauchent(R1, R2).

% CD-3  Une chambre deja occupee sur la periode ne peut etre affectee.
:- affectation(R, C), occupation_existante(C, R2), chevauchent(R, R2).

% CD-4  Toute exigence obligatoire doit etre satisfaite.
:- exigence_manquante(_, _).

% CD-5  La capacite doit couvrir le nombre de personnes.
:- affectation(R, C), capacite(C, Cap), nombre_personnes(R, N), N > Cap.

% CD-6  La categorie obtenue ne peut etre inferieure a la categorie contractee.
:- affectation(R, C), categorie(C, RangObtenu),
   categorie_contractee(R, RangDu), RangObtenu < RangDu.

% ---------------------------------------------------------------------
% Preferences souples
% ---------------------------------------------------------------------

penalite(R, souhait_non_satisfait, Poids) :-
    affectation(R, C),
    exigence_souhaitee(R, E),
    not dispose_de(C, E),
    poids(souhait_non_satisfait, Poids).

penalite(R, surclassement, Poids) :-
    surclassement(R, C),
    categorie(C, RangObtenu), categorie_contractee(R, RangDu),
    poids(surclassement, PoidsUnitaire),
    Poids = (RangObtenu - RangDu) * PoidsUnitaire.

penalite(R, hors_secteur, Poids) :-
    affectation(R, C),
    secteur_prefere(R, S),
    secteur(C, Autre), Autre != S,
    poids(hors_secteur, Poids).

penalite(R, etage_non_souhaite, Poids) :-
    affectation(R, C),
    etage_souhaite(R, EtageVoulu),
    etage(C, EtageObtenu), EtageObtenu != EtageVoulu,
    poids(etage_non_souhaite, Poids).

#minimize { P, R, Motif : penalite(R, Motif, P) }.

#show affectation/2.
#show penalite/3.