# Independent visual QA only; never part of the application runtime.
FROM python:3.13.12-slim-trixie@sha256:f1927c75e81efd1e091dbd64b6c0ecaa5630b38635a3d1c04034ac636e1f94c8
RUN apt-get update && apt-get install -y --no-install-recommends \
    libreoffice-writer=4:25.2.3-2+deb13u6 \
    poppler-utils=25.03.0-5+deb13u4 \
    fonts-liberation=1:2.1.5-3 \
    fonts-noto-color-emoji=2.051-0+deb13u1 \
    && rm -rf /var/lib/apt/lists/*
ENV HOME=/tmp
USER 10001
WORKDIR /tmp
