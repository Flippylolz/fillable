FROM node:26.12.1-bookworm-slim@sha256:28147155d47dc31abe0a46e0d12b59b2fb3d0a2dcc5dc65fce76a074180b16fe AS frontend
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

FROM nginx:1.31.8-alpine@sha256:1ef7ca94d7879df82421428ce13bd1eaa412404953859cf7a5b6512c25e67a60 AS gateway-base
USER nginx
ENTRYPOINT ["nginx"]
CMD ["-g", "daemon off;", "-c", "/etc/nginx/fillable.conf"]

FROM gateway-base AS gateway-dev
COPY infra/nginx.dev.conf /etc/nginx/fillable.conf

FROM gateway-base AS gateway-prod
COPY infra/nginx.prod.conf /etc/nginx/fillable.conf
COPY --from=build /app/dist/ /usr/share/nginx/html/
