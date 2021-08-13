FROM python:3.7 as base

COPY ./dist /app/dist
COPY ./requirements.txt /app/requirements.txt
COPY ./docker_base_build.sh /app/docker_base_build.sh

RUN /bin/bash /app/docker_base_build.sh

FROM python:3.7-slim
EXPOSE 5000
WORKDIR /app

ARG service_info=UNKNOWN
ENV SERVICE_INFO=${service_info}

COPY --from=base /wheeley /wheeley
COPY ./firmware /app/firmware
COPY ./docker_slim_build.sh /app/docker_slim_build.sh

RUN /bin/bash /app/docker_slim_build.sh

ENTRYPOINT ["python3", "-m", "brewblox_devcon_spark"]
