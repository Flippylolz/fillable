FROM mcr.microsoft.com/playwright:v1.64.0-noble@sha256:06a9939e57531807f8d5fd76ce44b53165ffb7d7501d87ab10e285c20b1e971f
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci && chown pwuser:pwuser /app
COPY --chown=pwuser:pwuser frontend/ ./
COPY --chown=pwuser:pwuser fixtures/docx/v1/client-intake-uk-v1.docx /fixtures/upload.docx
COPY --chown=pwuser:pwuser fixtures/docx/v1/working-review.json /fixtures/working-review.json
USER pwuser
CMD ["npx", "playwright", "test"]
