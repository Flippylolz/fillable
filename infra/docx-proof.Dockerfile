# Independent visual QA only; never part of the application runtime.
FROM python:3.13.12-slim-bookworm@sha256:a58daefb915e1e03ad48f3ca4df8832065412c5c35cacb9d39f4229184de12b6
RUN apt-get update && apt-get install -y --no-install-recommends \
    libreoffice-writer=4:7.4.7-1+deb12u14 \
    poppler-utils=22.12.0-2+deb12u3 \
    fonts-liberation=1:1.07.4-11 \
    && rm -rf /var/lib/apt/lists/*
ENV HOME=/tmp
USER 10001
WORKDIR /tmp
