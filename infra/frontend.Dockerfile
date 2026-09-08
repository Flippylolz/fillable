FROM node:24.14.0-bookworm-slim@sha256:d8e448a56fc63242f70026718378bd4b00f8c82e78d20eefb199224a4d8e33d8 AS frontend
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

FROM nginx:1.31.5-alpine@sha256:72ba65eb42c10344912a84ff42408db7d34f2feb642204570ab8fc5ffd29f1d3 AS gateway-base
USER nginx
ENTRYPOINT ["nginx"]
CMD ["-g", "daemon off;", "-c", "/etc/nginx/fillable.conf"]

FROM gateway-base AS gateway-dev
COPY infra/nginx.dev.conf /etc/nginx/fillable.conf

FROM gateway-base AS gateway-prod
COPY infra/nginx.prod.conf /etc/nginx/fillable.conf
COPY --from=build /app/dist/ /usr/share/nginx/html/
