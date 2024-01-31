import argparse
import shlex
import sys


def parse_cmd_args(raw_args: list[str]) -> tuple[argparse.Namespace, list[str]]:
    parser = argparse.ArgumentParser()
    parser.add_argument('-n', '--name')
    parser.add_argument('--debug', action='store_true')
    parser.add_argument('--mqtt-protocol')
    parser.add_argument('--mqtt-host')
    parser.add_argument('--mqtt-port')
    parser.add_argument('--history-topic')
    parser.add_argument('--datastore-topic')
    parser.add_argument('--state-topic')

    parser.add_argument('--simulation', action='store_true')
    parser.add_argument('--mock', action='store_true')
    parser.add_argument('--device-host')
    parser.add_argument('--device-serial')
    parser.add_argument('--device-id')
    parser.add_argument('--discovery')
    parser.add_argument('--command-timeout')
    parser.add_argument('--broadcast-interval')
    parser.add_argument('--skip-version-check', action='store_true')
    parser.add_argument('--backup-interval')
    parser.add_argument('--backup-retry-interval')
    parser.add_argument('--time-sync-interval')

    return parser.parse_known_args(raw_args)


if __name__ == '__main__':
    args, unknown = parse_cmd_args(sys.argv[1:])
    if unknown:
        print(f'WARNING: ignoring unknown CMD arguments: {unknown}', file=sys.stderr)
    output = [f'brewblox_spark_{k}={shlex.quote(str(v))}'
              for k, v in vars(args).items()
              if v is not None and v is not False]
    print(*output, sep='\n')
