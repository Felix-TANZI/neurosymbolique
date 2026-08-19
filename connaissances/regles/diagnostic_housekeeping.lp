% Analyse d'admissibilite du service housekeeping
%
% Ce programme etablit, pour chaque paire tache-agent, si l'agent est
% admissible et, a defaut, pour quels motifs il est ecarte. Il ne comporte ni
% choix ni ordonnancement: son resultat est un constat sur la situation,
% toujours calculable.
%
% L'ordonnancement effectif des taches admissibles releve du solveur de
% contraintes, qui opere exclusivement sur les paires declarees ici.
%
% Ce fichier est edite par un administrateur habilite, sans modification ni
% recompilation du code source.

#defined competence/2.
#defined competence_requise/2.
#defined secteur_tache/2.
#defined secteur_agent/2.
#defined echeance/2.
#defined priorite/2.
#defined secteur_reserve/1.

% ---------------------------------------------------------------------
% Deductions intermediaires
% ---------------------------------------------------------------------

% Un agent est en service lorsqu'il est present et dispose de temps restant.
en_service(A) :-
    agent(A),
    disponibilite(A, present),
    minutes_restantes(A, M), M > 0.

% Une competence requise par la tache et absente chez l'agent.
competence_manquante(T, A, C) :-
    tache(T), agent(A),
    competence_requise(T, C),
    not competence(A, C).

% ---------------------------------------------------------------------
% Motifs de rejet
% ---------------------------------------------------------------------

rejet(T, A, agent_absent) :-
    tache(T), agent(A),
    disponibilite(A, absent).

rejet(T, A, agent_en_retard) :-
    tache(T), agent(A),
    disponibilite(A, retard).

rejet(T, A, temps_insuffisant) :-
    tache(T), agent(A),
    duree(T, D),
    minutes_restantes(A, M), D > M.

rejet(T, A, competence_absente(C)) :-
    tache(T), agent(A),
    competence_manquante(T, A, C).

rejet(T, A, secteur_reserve) :-
    tache(T), agent(A),
    secteur_tache(T, S),
    secteur_reserve(S),
    not secteur_agent(A, S).

rejet_quelconque(T, A) :- rejet(T, A, _).

% Un agent est admissible pour une tache lorsqu'aucun motif ne l'ecarte.
admissible(T, A) :- tache(T), en_service(A), not rejet_quelconque(T, A).

% Une tache sans aucun agent admissible ne pourra etre planifiee.
sans_agent(T) :- tache(T), not admissible(T, _) : agent(_).

#show admissible/2.
#show rejet/3.