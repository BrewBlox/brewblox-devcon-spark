FROM brewblox/brewblox-service:latest

RUN mkdir -p /pkg
COPY ./pkg/* /pkg/

EXPOSE 5000

RUN pip3 install /pkg/* || true \
    && pip3 install brewblox-devcon-spark \
    && pip3 show brewblox-devcon-spark

ENTRYPOINT ["python3", "-m", "brewblox_devcon_spark"]
