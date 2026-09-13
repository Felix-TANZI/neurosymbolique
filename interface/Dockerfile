# Image de l'interface.
#
# La construction et la diffusion sont separees: l'image finale ne contient
# que les fichiers produits, sans les outils qui les ont produits.

FROM node:20-slim AS construction

WORKDIR /construction

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# L'adresse du noyau est fixee a la construction: l'interface est servie
# statiquement et ne peut lire aucune variable d'environnement a l'execution.
ARG VITE_RACINE_API=/api
ENV VITE_RACINE_API=$VITE_RACINE_API

RUN npm run build


FROM nginx:alpine

COPY --from=construction /construction/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80