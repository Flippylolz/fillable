FROM mcr.microsoft.com/playwright:v1.64.1-noble@sha256:7852dc5a7d72f5fe458a597d690f6c42fbc8e9e26ddfa95f8e6ef552558d9bbf
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci && chown pwuser:pwuser /app
COPY --chown=pwuser:pwuser frontend/ ./
COPY --chown=pwuser:pwuser fixtures/docx/v1/client-intake-uk-v1.docx /fixtures/upload.docx
COPY --chown=pwuser:pwuser fixtures/docx/v1/working-review.json /fixtures/working-review.json
USER pwuser
CMD ["npx", "playwright", "test"]
