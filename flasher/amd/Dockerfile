FROM brewblox/firmware-particle

WORKDIR /app
ENV PARTICLE_VERSION=1.2.1-rc.2
ENV PARTICLE_RELEASES=https://github.com/particle-iot/firmware/releases/download/v${PARTICLE_VERSION}


RUN apk add --no-cache usbutils curl bash \
    && echo 'python serial-switcher.py' > ./trigger-dfu && chmod +x ./trigger-dfu \
    && echo 'python serial-switcher.py -b 28800' > ./trigger-listening && chmod +x ./trigger-listening \
    \
    && curl -sL -o bootloader-p1.bin ${PARTICLE_RELEASES}/p1-bootloader@${PARTICLE_VERSION}.bin \
    && curl -sL -o system-part1-p1.bin ${PARTICLE_RELEASES}/p1-system-part1@${PARTICLE_VERSION}.bin \
    && curl -sL -o system-part2-p1.bin ${PARTICLE_RELEASES}/p1-system-part2@${PARTICLE_VERSION}.bin \
    \
    && curl -sL -o bootloader-photon.bin ${PARTICLE_RELEASES}/photon-bootloader@${PARTICLE_VERSION}.bin \
    && curl -sL -o system-part1-photon.bin ${PARTICLE_RELEASES}/photon-system-part1@${PARTICLE_VERSION}.bin \
    && curl -sL -o system-part2-photon.bin ${PARTICLE_RELEASES}/photon-system-part2@${PARTICLE_VERSION}.bin \
    && apk del curl


COPY ./binaries/brewblox-p1.bin ./
COPY ./binaries/brewblox-photon.bin ./
COPY ./serial-switcher.py ./
COPY ./flash ./
COPY ./flash-bootloader ./
COPY ./wifi ./


ENTRYPOINT [ "bash" ]

# The container must be restarted after preparing the device
# Example calls:

# docker run -it --rm --privileged brewblox/firmware-flasher:local trigger-dfu
# docker run -it --rm --privileged brewblox/firmware-flasher:local flash
# docker run -it --rm --privileged brewblox/firmware-flasher:local trigger-listening
# docker run -it --rm --privileged brewblox/firmware-flasher:local flash-bootloader
# docker run -it --rm --privileged brewblox/firmware-flasher:local wifi
