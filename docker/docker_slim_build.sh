#! /bin/bash
set -ex

BOOST_V=1.67.0
ARCH="$(dpkg --print-architecture)"

# Pip
pip3 install --no-index --find-links=/wheeley brewblox-devcon-spark
pip3 freeze

# Apt
apt-get update
apt-get install -y --no-install-recommends \
    socat \
    usbutils \
    libboost-system${BOOST_V} \
    libboost-program-options${BOOST_V} \
    libboost-random${BOOST_V} \
    libboost-thread${BOOST_V}

# Cleanup
rm -rf /wheeley
rm -rf /var/lib/apt/lists/*

case "${ARCH}" in
    "amd64")
        rm /app/firmware-bin/binaries/brewblox-{arm32,arm64}.sim
        ;;
    "armhf")
        rm /app/firmware-bin/binaries/brewblox-{amd64,arm64}.sim
        ;;
    "arm64")
        rm /app/firmware-bin/binaries/brewblox-{amd64,arm32}.sim
        ;;
    *)
        echo "Unknown architecture: ${ARCH}"
        ;;
esac