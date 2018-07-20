FROM brewblox/brewblox-service:rpi-latest

WORKDIR /app

COPY ./dist /app/dist
COPY ./config /app/config

EXPOSE 5000

RUN pip3 install /app/dist/* \
    && pip3 show brewblox-devcon-spark

ENTRYPOINT ["python3", "-m", "brewblox_devcon_spark"]
