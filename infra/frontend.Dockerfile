FROM node:26.12.0-bookworm-slim@sha256:298992629d69bbd5b2b03ad57094d8e4fcb3a8eeb7c4e25d29de656519568913 AS frontend
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci && chown node:node /app
COPY --chown=node:node frontend/ ./
COPY --chown=node:node fixtures/docx/v1/working-review.json /fixtures/docx/v1/working-review.json
USER node
CMD ["npm", "run", "dev"]

FROM frontend AS build
ARG VITE_APP_COMMIT_SHA
ENV VITE_APP_COMMIT_SHA=$VITE_APP_COMMIT_SHA
RUN npm run build

FROM nginx:1.31.7-alpine@sha256:892bb2152464f0c5d8972593a5f5afaf8054552580b699d95f8ff4af08c2d33d AS gateway-base
USER nginx
ENTRYPOINT ["nginx"]
CMD ["-g", "daemon off;", "-c", "/etc/nginx/fillable.conf"]

FROM gateway-base AS gateway-dev
COPY infra/nginx.dev.conf /etc/nginx/fillable.conf

FROM gateway-base AS gateway-prod
COPY infra/nginx.prod.conf /etc/nginx/fillable.conf
COPY --from=build /app/dist/ /usr/share/nginx/html/
