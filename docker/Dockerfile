FROM python:3.7 as base

COPY ./dist /app/dist
COPY ./requirements.txt /app/requirements.txt

ENV PIP_EXTRA_INDEX_URL=https://www.piwheels.org/simple
ENV PIP_FIND_LINKS=/wheeley

RUN set -ex \
    && pip3 install wheel \
    && pip3 wheel --wheel-dir=/wheeley -r /app/requirements.txt \
    && pip3 wheel --wheel-dir=/wheeley /app/dist/*

FROM python:3.7-slim
EXPOSE 5000
WORKDIR /app

ARG service_info=UNKNOWN
ENV SERVICE_INFO=${service_info}
ENV BOOST_V=1.67.0

COPY --from=base /wheeley /wheeley
COPY ./firmware-bin /app/firmware-bin

RUN set -ex \
    && pip3 install --no-index --find-links=/wheeley brewblox-devcon-spark \
    && rm -rf /wheeley \
    && pip3 freeze \
    && apt-get update -q \
    && apt-get install -yq \
    libboost-system${BOOST_V} \
    libboost-program-options${BOOST_V} \
    libboost-random${BOOST_V} \
    libboost-thread${BOOST_V}

ENTRYPOINT ["python3", "-m", "brewblox_devcon_spark"]
