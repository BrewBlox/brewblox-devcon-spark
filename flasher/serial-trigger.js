const SerialPort = require('serialport');
const fs = require('fs');

const deviceMatch = /usb-Particle_(P1|Photon)/;
const defaultPath = '/dev/ttyACM0';
const deviceDir = '/dev/serial/by-id';

const modes = {
    dfu: 14400,
    listen: 28800,
}
const neutralBaudRate = 9600;

const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));

const toggle = async (path, baudRate) => {
    const serial = new SerialPort(path, { baudRate, autoOpen: false });
    serial.on('error', e => { throw e });
    const opened = new Promise(resolve => serial.on('open', resolve));
    const closed = new Promise(resolve => serial.on('close', resolve));

    serial.open();
    await opened
    serial.close();
    await closed
}

async function main() {
    const arg = process.argv[2] || '';

    if (modes[arg] === undefined) {
        throw new Error(`Invalid mode argument '${arg}'. [dfu | listen]`);
    }

    const devicePath = fs.existsSync(deviceDir)
        ? fs.readdirSync(deviceDir)
            .map(f => `${deviceDir}/${f}`)
            .find(f => f && deviceMatch.test(f))
        : undefined;

    const path = devicePath || defaultPath;
    console.log(`Triggering ${arg} on port ${path}`);

    if (arg === 'dfu') {
        await toggle(path, modes.dfu);
    }
    if (arg === 'listen') {
        await toggle(path, modes.listen);
        await toggle(path, neutralBaudRate);
        await sleep(3000);
    }
}

process.on('unhandledRejection', (error) => {
    console.error(error);
});

main();
