FROM brewblox/firmware-particle:latest

WORKDIR /app

COPY ./firmware/* ./

RUN rm ./*.sim && bash inspect

# Example calls:

# docker run -it --rm --privileged -v /dev:/dev brewblox/firmware-flasher:edge trigger-dfu
# docker run -it --rm --privileged -v /dev:/dev brewblox/firmware-flasher:edge flash
# docker run -it --rm --privileged -v /dev:/dev brewblox/firmware-flasher:edge flash-bootloader
# docker run -it --rm --privileged -v /dev:/dev brewblox/firmware-flasher:edge wifi
# docker run -it --rm --privileged -v /dev:/dev brewblox/firmware-flasher:edge particle
