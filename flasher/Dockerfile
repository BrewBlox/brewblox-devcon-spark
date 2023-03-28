FROM ghcr.io/brewblox/firmware-particle:latest

WORKDIR /app

COPY ./firmware/* ./

RUN rm ./*.sim && bash inspect
