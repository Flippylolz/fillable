FROM node:24.14.0-bookworm-slim@sha256:d8e448a56fc63242f70026718378bd4b00f8c82e78d20eefb199224a4d8e33d8
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci && chown node:node /app
COPY --chown=node:node frontend/ ./
USER node
CMD ["npm", "run", "dev"]
