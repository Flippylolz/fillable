# Independent visual QA only; never part of the application runtime.
FROM python:3.15.0rc3-slim-trixie@sha256:a3af3d230522dd52f7f2191b39e1892912dbcb0c8dee22afdec3dc83baf0f549
RUN apt-get update && apt-get install -y --no-install-recommends \
    libreoffice-writer=4:25.2.3-2+deb13u7 \
    poppler-utils=25.03.0-5+deb13u4 \
    fonts-liberation=1:2.1.5-3 \
    fonts-noto-color-emoji=2.051-0+deb13u1 \
    && rm -rf /var/lib/apt/lists/*
ENV HOME=/tmp
USER 10001
WORKDIR /tmp
