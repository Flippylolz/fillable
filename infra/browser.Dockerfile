FROM mcr.microsoft.com/playwright:v1.64.1-noble@sha256:47b510dd9230bf0b9bfc9b20102241e577ea7a99334ab4c3ca19f19770e9b8ea
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci && chown pwuser:pwuser /app
COPY --chown=pwuser:pwuser frontend/ ./
COPY --chown=pwuser:pwuser fixtures/docx/v1/client-intake-uk-v1.docx /fixtures/upload.docx
COPY --chown=pwuser:pwuser fixtures/docx/v1/working-review.json /fixtures/working-review.json
USER pwuser
CMD ["npx", "playwright", "test"]
