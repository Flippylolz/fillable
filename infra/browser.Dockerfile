FROM mcr.microsoft.com/playwright:v1.65.0-noble@sha256:6e3fb709361521eb27161606e6da6d2674e5e89fa16516cb37d6fdd91372273d
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci && chown pwuser:pwuser /app
COPY --chown=pwuser:pwuser frontend/ ./
COPY --chown=pwuser:pwuser fixtures/docx/v1/client-intake-uk-v1.docx /fixtures/upload.docx
COPY --chown=pwuser:pwuser fixtures/docx/v1/working-review.json /fixtures/working-review.json
USER pwuser
CMD ["npx", "playwright", "test"]
