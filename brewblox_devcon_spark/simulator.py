"""
Launches the firmware simulator in a subprocess
"""


import os
import subprocess


def start():
    print(os.getcwd())
    subprocess.Popen(
        ['./brewblox-amd', '--device_id=123456789012345678901234'],
        cwd=f'{os.getcwd()}/binaries')
