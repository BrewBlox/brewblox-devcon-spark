const SerialPort = require('serialport');
const fs = require('fs');

const deviceMatch = /usb-Particle_(P1|Photon)/;
const defaultPath = '/dev/ttyACM0';
const deviceDir = '/dev/serial/by-id';

const baudRate = 14400;

async function main() {
    const devicePath = fs.existsSync(deviceDir)
        ? fs.readdirSync(deviceDir)
            .map(f => `${deviceDir}/${f}`)
            .find(f => f && deviceMatch.test(f))
        : undefined;

    const path = devicePath ?? defaultPath;
    console.log(`Triggering dfu on port ${path}`);

    const serial = new SerialPort(path, { baudRate, autoOpen: false });
    serial.on('error', e => { throw e });
    const opened = new Promise(resolve => serial.on('open', resolve));
    const closed = new Promise(resolve => serial.on('close', resolve));

    serial.open();
    await opened
    serial.close();
    await closed
}

process.on('unhandledRejection', (error) => {
    console.error(error);
});

main();
