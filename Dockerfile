# Image du noyau de raisonnement.
#
# Le modele d'interpretation est telecharge lors de la construction et non au
# demarrage: un conteneur qui telechargerait 450 Mo a chaque relance dependrait
# de la disponibilite du depot distant pour fonctionner.
#
# Java est requis par le raisonneur ontologique HermiT, qu'Owlready2 invoque
# pour verifier la coherence du schema.

FROM python:3.13-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/opt/modeles/cache

RUN apt-get update \
    && apt-get install --no-install-recommends -y \
        default-jre-headless \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /application

# Les dependances sont installees avant le code: une modification du code
# n'invalide alors pas la couche des dependances, dont l'installation est
# longue.
COPY noyau/pyproject.toml ./
RUN pip install --upgrade pip \
    && pip install torch --index-url https://download.pytorch.org/whl/cpu \
    && pip install .

COPY noyau/src/ ./src/
COPY noyau/scripts/ ./scripts/

# Les connaissances sont placees a la racine, la ou le code les cherche.
# Elles demeurent editables sans reconstruction: un volume peut les recouvrir.
COPY connaissances/ /connaissances/

# Les profils d'etablissement decrivent les configurations simulees. Ils
# relevent, comme les connaissances, de l'exploitation et non du code.
COPY simulation/ /simulation/

# Le modele preentraine est place dans l'image. Son telechargement au
# demarrage rendrait le conteneur tributaire d'un service externe.
RUN python -c "\
from transformers import AutoModel, AutoTokenizer; \
AutoTokenizer.from_pretrained('camembert-base'); \
AutoModel.from_pretrained('camembert-base')"

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=90s --retries=3 \
    CMD curl --fail http://localhost:8000/sante || exit 1

CMD ["uvicorn", "src.api:application", "--host", "0.0.0.0", "--port", "8000"]