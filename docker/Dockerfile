# Firmware depends on Boost 1.67
# Bullseye repositories only provide 1.74
FROM python:3.9-buster as base

ENV PIP_EXTRA_INDEX_URL=https://www.piwheels.org/simple
ENV PIP_FIND_LINKS=/wheeley

COPY ./dist /app/dist
COPY ./requirements.txt /app/requirements.txt
COPY ./firmware /app/firmware

RUN set -ex \
    && mkdir /wheeley \
    && pip3 install --upgrade pip wheel setuptools \
    && pip3 wheel --wheel-dir=/wheeley -r /app/requirements.txt \
    && pip3 wheel --wheel-dir=/wheeley /app/dist/* \
    && ARCH="$(dpkg --print-architecture)" \
    && if [ "${ARCH}" = "amd64" ]; then OTHER_SIM='brewblox-{arm32,arm64}.sim'; fi \
    && if [ "${ARCH}" = "armhf" ]; then OTHER_SIM='brewblox-{amd64,arm64}.sim'; fi \
    && if [ "${ARCH}" = "arm64" ]; then OTHER_SIM='brewblox-{amd64,arm32}.sim'; fi \
    && bash -c "rm /app/firmware/${OTHER_SIM}" \
    && rm /app/firmware/*.elf

FROM python:3.9-slim-buster
EXPOSE 5000
WORKDIR /app

ARG service_info=UNKNOWN
ENV SERVICE_INFO=${service_info}
ENV BOOST_V=1.67.0

RUN set -ex \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        socat \
        usbutils \
        libboost-system${BOOST_V} \
        libboost-program-options${BOOST_V} \
        libboost-random${BOOST_V} \
        libboost-thread${BOOST_V} \
    && rm -rf /var/lib/apt/lists/*

COPY --from=base /wheeley /wheeley
COPY --from=base /app/firmware /app/firmware

RUN set -ex \
    && pip3 install --no-index --find-links=/wheeley brewblox-devcon-spark \
    && pip3 freeze \
    && rm -rf /wheeley

ENTRYPOINT ["python3", "-m", "brewblox_devcon_spark"]
