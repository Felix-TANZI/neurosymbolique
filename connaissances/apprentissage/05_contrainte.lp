chambre(312).
chambre(407).
chambre(512).

sale(312).
en_maintenance(407).

reservation(r1).

{ affectation(R, C) : chambre(C) } = 1 :- reservation(R).

:- affectation(_, C), sale(C).
:- affectation(_, C), en_maintenance(C).