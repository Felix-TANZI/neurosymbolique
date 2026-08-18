chambre(312). chambre(407). chambre(512).
etage(312, 3). etage(407, 4). etage(512, 5).

sale(312).

reservation(r1).
prefere_etage_eleve(r1).

{ affectation(R, C) : chambre(C) } = 1 :- reservation(R).

:- affectation(_, C), sale(C).

penalite(R, P) :- affectation(R, C), prefere_etage_eleve(R), etage(C, E), P = 10 - E.

#minimize { P, R : penalite(R, P) }.