FROM brewblox/brewblox-service:latest as base

COPY ./dist /build/dist

RUN pip3 install wheel \
    && pip3 wheel /build/dist/* --wheel-dir=/wheeley

FROM python:3.6-slim
EXPOSE 5000
WORKDIR /app

COPY --from=base /wheeley /wheeley
COPY ./config /app/config

RUN ls /wheeley \
    && pip3 install --no-index --find-links=/wheeley brewblox-devcon-spark \
    && rm -rf /wheeley \
    && pip3 freeze

ENTRYPOINT ["python3", "-m", "brewblox_devcon_spark"]
