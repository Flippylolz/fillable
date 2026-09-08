# Independent visual QA only; never part of the application runtime.
FROM python:3.14.7-slim-trixie@sha256:cad9a2c871761c413caa6fdd6441c783451e740a48aaeba60ae62a8b53525ef6
RUN apt-get update && apt-get install -y --no-install-recommends \
    libreoffice-writer=4:25.2.3-2+deb13u6 \
    poppler-utils=25.03.0-5+deb13u4 \
    fonts-liberation=1:2.1.5-3 \
    fonts-noto-color-emoji=2.051-0+deb13u1 \
    && rm -rf /var/lib/apt/lists/*
ENV HOME=/tmp
USER 10001
WORKDIR /tmp
