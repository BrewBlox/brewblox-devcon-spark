FROM brewblox/firmware-particle:latest
LABEL org.opencontainers.image.source="https://github.com/BrewBlox/brewblox-devcon-spark"

WORKDIR /app

COPY ./firmware/* ./

RUN rm ./*.sim && bash inspect
