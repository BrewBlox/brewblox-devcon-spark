from configparser import ConfigParser
from contextlib import suppress
from pathlib import Path

from invoke import Context, task
from invoke.exceptions import UnexpectedExit

from brewblox_devcon_spark.models import FirmwareConfig

ROOT = Path(__file__).parent.resolve()
FW_BASE_URL = 'https://brewblox.blob.core.windows.net/firmware'


def get_fw_config() -> FirmwareConfig:  # pragma: no cover
    """
    Globally cached getter for firmware config.
    When first called, config is parsed from the firmware.ini file.
    """
    parser = ConfigParser()
    parser.read(ROOT / 'firmware.ini')
    raw = dict(parser['FIRMWARE'].items())
    config = FirmwareConfig(**raw)
    return config


@task
def compile_proto(ctx: Context):
    out_dir = ROOT / 'brewblox_devcon_spark/codec/proto-compiled'

    with ctx.cd(ROOT):
        ctx.run('poetry install --sync')
        ctx.run(f'rm -rf {out_dir}/*_pb2.py')
        ctx.run(' '.join([
            'python3 -m grpc_tools.protoc',
            '-I=./brewblox-proto/proto',
            f'--python_out="{out_dir}"',
            ' ./brewblox-proto/proto/**.proto',
        ]))


@task
def download_firmware(ctx: Context):
    fw_config = get_fw_config()
    fw_dir = ROOT / 'firmware'

    fw_date = fw_config.firmware_date
    fw_version = fw_config.firmware_version
    fw_file = 'brewblox-release.tar.gz'
    url = f'{FW_BASE_URL}/{fw_date}-{fw_version}/{fw_file}'
    print(f'Downloading firmware release {fw_date}-{fw_version}')

    with ctx.cd(ROOT):
        # Clear firmware dir
        ctx.run(f'mkdir -p {fw_dir}')/v
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

    fw_config = get_fw_config()
    fw_date = fw_config.firmware_date
    fw_version = fw_config.firmware_version
    proto_sha = fw_config.proto_sha

    print(f'Updating to firmware release {fw_date}-{fw_version}')

    with ctx.cd(ROOT / 'brewblox-proto'):
        ctx.run('git fetch')
        ctx.run(f'git checkout --quiet "{proto_sha}"')


@task
def testclean(ctx: Context):
    """
    Cleans up leftover test containers, networks, and simulators.
    Container cleanup is normally done in test fixtures.
    This is skipped if debugged tests are stopped halfway.
    """
    result = ctx.run('docker ps -aq --filter "name=pytest"', hide='stdout')
    containers = result.stdout.strip().replace('\n', ' ')
    if containers:
        ctx.run(f'docker rm -f {containers}')
    ctx.run('docker network prune -f')

    with suppress(UnexpectedExit):
        # returns 1 if nothing killed
        ctx.run('sudo pkill -ef -9 brewblox-amd64.sim')


@task
def build(ctx: Context):
    with ctx.cd(ROOT):
        ctx.run('rm -rf dist')
        ctx.run('poetry build --format sdist')
        ctx.run('poetry export --without-hashes -f requirements.txt -o dist/requirements.txt')


@task(pre=[build])
def image(ctx: Context, tag='local'):
    with ctx.cd(ROOT):
        ctx.run(f'docker build -t ghcr.io/brewblox/brewblox-devcon-spark:{tag} -f Dockerfile.service .')


@task(pre=[build])
def image_armv7(ctx: Context, tag='local'):
    with ctx.cd(ROOT):
        ctx.run(
            f'docker buildx build --platform=linux/arm/v7 -t ghcr.io/brewblox/brewblox-devcon-spark:{tag} -f Dockerfile.service .')
