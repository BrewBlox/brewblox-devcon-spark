from configparser import ConfigParser
from pathlib import Path

from invoke import Context, task

from brewblox_devcon_spark.models import ServiceFirmwareIni

ROOT = Path(__file__).parent.resolve()
FW_BASE_URL = 'https://brewblox.blob.core.windows.net/firmware'


def parse_ini() -> ServiceFirmwareIni:
    parser = ConfigParser()
    parser.read((ROOT / 'firmware.ini').resolve())
    config = ServiceFirmwareIni(parser['FIRMWARE'].items())
    return config


@task
def compile_proto(ctx: Context):
    out_dir = ROOT / 'brewblox_devcon_spark/codec/proto-compiled'

    with ctx.cd(ROOT):
        ctx.run(f'rm -rf {out_dir}/*_pb2.py')
        ctx.run(' '.join([
            'python3 -m grpc_tools.protoc',
            '-I=./brewblox-proto/proto',
            f'--python_out="{out_dir}"',
            ' ./brewblox-proto/proto/**.proto',
        ]))


@task
def download_firmware(ctx: Context):
    fw_dir = ROOT / 'firmware'
    ini = parse_ini()

    fw_date = ini['firmware_date']
    fw_version = ini['firmware_version']
    fw_file = 'brewblox-release.tar.gz'
    url = f'{FW_BASE_URL}/{fw_date}-{fw_version}/{fw_file}'
    print(f'Downloading firmware release {fw_date}-{fw_version}')

    with ctx.cd(ROOT):
        # Clear firmware dir
        ctx.run(f'mkdir -p {fw_dir}')
        ctx.run(f'rm -rf {fw_dir}/*')

        # Download and extract firmware files
        ctx.run(f'curl -sSfO "{url}"')
        ctx.run(f'tar -xzvf {fw_file} -C {fw_dir}')
        ctx.run(f'rm {fw_file}')

        # Simulators are executable files
        ctx.run(f'chmod +x {fw_dir}/*.sim')


@task(post=[compile_proto, download_firmware])
def update_firmware(ctx: Context, release='develop'):
    url = f'{FW_BASE_URL}/{release}/firmware.ini'

    with ctx.cd(ROOT):
        ctx.run(f'curl -sSf -o firmware.ini "{url}"')

    ini = parse_ini()
    fw_date = ini['firmware_date']
    fw_version = ini['firmware_version']
    proto_version = ini['proto_version']

    print(f'Updating to firmware release {fw_date}-{fw_version}')

    with ctx.cd(ROOT / 'brewblox-proto'):
        ctx.run('git fetch')
        ctx.run(f'git checkout --quiet "{proto_version}"')


@task
def build(ctx: Context):
    with ctx.cd(ROOT):
        ctx.run('rm -rf dist')
        ctx.run('poetry build --format sdist')
        ctx.run('poetry export --without-hashes -f requirements.txt -o dist/requirements.txt')
