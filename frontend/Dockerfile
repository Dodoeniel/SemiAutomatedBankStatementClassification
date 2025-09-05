# Build
FROM node:20 AS build
WORKDIR /app

# package.json aus vue_project kopieren
COPY vue_project/package*.json ./
RUN npm ci

# Restliche Dateien
COPY vue_project/ ./
RUN npm run build

# Serve als statisches Site
FROM nginx:alpine
COPY --from=build /app/dist/ /usr/share/nginx/html

# Nginx Config für SPA
RUN printf "server { \
  listen 80; \
  server_name _; \
  root /usr/share/nginx/html; \
  index index.html; \
  location / { try_files \$uri /index.html; } \
  }" > /etc/nginx/conf.d/default.conf