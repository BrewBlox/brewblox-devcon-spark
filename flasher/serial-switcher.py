#!/usr/bin/env python

import argparse
from time import sleep

import serial

parser = argparse.ArgumentParser()
parser.add_argument('-p', '--port',
                    help='Serial port. [%(default)s]',
                    default='/dev/ttyACM0')
parser.add_argument('-b', '--baud-rate',
                    help='Active baud rate. [%(default)s]',
                    default=14400,
                    type=int)
parser.add_argument('--neutral-baud-rate',
                    help='Neutral baud rate. [%(default)s]',
                    default=9600,
                    type=int)


args = parser.parse_args()

try:
    ser = serial.Serial(args.port, args.baud_rate)
    ser.close()
    ser = serial.Serial(args.port, args.neutral_baud_rate)
    ser.close()
    sleep(3)

except Exception:
    pass
