FROM brewblox/firmware-particle:latest

WORKDIR /app

COPY ./binaries/* ./
COPY ./serial-switcher.py ./
COPY ./flash ./
COPY ./flash-bootloader ./
COPY ./wifi ./
COPY ./inspect ./

RUN apk add --no-cache usbutils bash \
    && echo 'python serial-switcher.py $@' > ./trigger-dfu && chmod +x ./trigger-dfu \
    && echo 'python serial-switcher.py -b 28800 $@' > ./trigger-listening && chmod +x ./trigger-listening \
    && echo './node_modules/.bin/particle $@' > ./particle && chmod +x ./particle \
    && chmod +x ./inspect \
    && ./inspect

ENTRYPOINT [ "bash" ]

# Example calls:

# docker run -it --rm --privileged brewblox/firmware-flasher:local trigger-dfu
# docker run -it --rm --privileged brewblox/firmware-flasher:local flash
# docker run -it --rm --privileged brewblox/firmware-flasher:local trigger-listening
# docker run -it --rm --privileged brewblox/firmware-flasher:local flash-bootloader
# docker run -it --rm --privileged brewblox/firmware-flasher:local wifi
# docker run -it --rm --privileged brewblox/firmware-flasher:local particle
