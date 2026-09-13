#!/usr/bin/env bash
# Deploiement du systeme neuro-symbolique.
#
# Le script est idempotent: il peut etre relance sans effet de bord. La base et
# le modele demeurent dans des volumes, qu'une reconstruction ne touche pas.

set -euo pipefail

echo "Construction des images"
docker compose build

echo "Demarrage des services"
docker compose up -d

echo "Attente du noyau"
for tentative in $(seq 1 30); do
    if docker compose exec -T noyau curl --fail --silent http://localhost:8000/sante > /dev/null 2>&1; then
        echo "Noyau disponible"
        break
    fi
    if [ "$tentative" -eq 30 ]; then
        echo "Le noyau n'a pas repondu dans le delai imparti"
        docker compose logs --tail 50 noyau
        exit 1
    fi
    sleep 5
done

# L'etablissement n'est constitue que s'il n'existe pas: une reconstitution
# effacerait les decisions consignees et l'etat courant.
if ! docker compose exec -T noyau test -f /donnees/operations.sqlite3; then
    echo "Constitution de l'etablissement"
    docker compose exec -T noyau python -m scripts.constituer \
        --profil urbain --jour 2026-08-12
fi

echo "Adresse publique du tunnel"
docker compose logs tunnel 2>&1 | grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' | tail -1

docker compose ps