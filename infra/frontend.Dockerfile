FROM node:26.10.0-bookworm-slim@sha256:662933cf47f013bc8e4beb31a6116448427a82057ba7c42c97e4c5ba766504c2 AS frontend
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

FROM nginx:1.31.6-alpine@sha256:adad2ae9204d0fd7a34f40299bc838c3782be1293b10005eac4315ff5a1abf4e AS gateway-base
USER nginx
ENTRYPOINT ["nginx"]
CMD ["-g", "daemon off;", "-c", "/etc/nginx/fillable.conf"]

FROM gateway-base AS gateway-dev
COPY infra/nginx.dev.conf /etc/nginx/fillable.conf

FROM gateway-base AS gateway-prod
COPY infra/nginx.prod.conf /etc/nginx/fillable.conf
COPY --from=build /app/dist/ /usr/share/nginx/html/
