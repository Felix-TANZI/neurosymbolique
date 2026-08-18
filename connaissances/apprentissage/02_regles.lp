chambre(312).
chambre(407).
chambre(512).

etage(312, 3).
etage(407, 4).
etage(512, 5).

etage_eleve(C) :- chambre(C), etage(C, E), E >= 4.