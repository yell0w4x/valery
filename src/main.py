import telegram
from dependency_injector.wiring import inject, Provide
from dependency_injector.providers import Configuration

import ioc

from os.path import dirname, realpath, abspath, join, basename, splitext
from argparse import ArgumentParser
from pathlib import Path
import logging
import sys
import os
import glob


logger = logging.getLogger(__name__)


class Color:
    off = '\033[0m'
    black = '\033[0;30m'
    red = '\033[0;31m'
    green = '\033[0;32m'
    yellow = '\033[0;33m'
    blue = '\033[0;34m'
    purple = '\033[0;35m'
    cyan = '\033[0;36m'
    white = '\033[0;37m'

c = Color


@inject
def run(args, app_service=Provide[ioc.Container.app_service]):
    if 'handler' in args:
        args.handler(app_service, **vars(args))
        exit(0)

    app_service.run()


app_dir = Path(dirname(__file__)).resolve()
config_fn = app_dir.parent.joinpath('config/config.yaml')


def cli(args=sys.argv[1:]):
    parser = ArgumentParser()
    parser.add_argument('-c', '--config', default=str(config_fn), help='Config file (default: %(default)s')
    parser.add_argument('--log-level', default=os.environ.get('VALERY_LOG_LEVEL', 'INFO'), help='App log level (default: %(default)s')
    parser.add_argument('--deps-log-level', default=os.environ.get('VALERY_DEPS_LOG_LEVEL', 'WARNING'), help='App deps log level (default: %(default)s')
    parser.add_argument('--no-color', action='store_true', default=False, help='Use no color for log output')

    return parser.parse_args(args)


def setup_loggers(log_level, deps_log_level, log_format):
    logging.basicConfig(level=log_level, format=log_format)
    ours = list(splitext(basename(fn))[0] for fn in glob.glob(join(app_dir, '*.py'))) + ['__main__']
    for name in logging.root.manager.loggerDict:
        if name in ours:
            continue
        logging.getLogger(name).setLevel(deps_log_level)


def main():
    args = cli()

    log_format = ('[%(asctime)s]:%(levelname)-5s:: %(message)s -- {%(filename)s:%(lineno)d:(%(funcName)s)}' 
                  if args.no_color else
                  f'[{c.white}%(asctime)s{c.off}]:{c.yellow}%(levelname)-5s{c.off}::{c.green} %(message)s {c.white}-- {c.yellow}{{{c.blue}%(filename)s{c.off}:{c.cyan}%(lineno)d{c.off}:({c.purple}%(funcName)s{c.off}){c.yellow}}}{c.off}')
    setup_loggers(args.log_level, args.deps_log_level, log_format)

    container = ioc.Container()
    config_fn = realpath(abspath(args.config))
    container.config.from_yaml(config_fn, required=True)
    container.wire(modules=[__name__])
    run(args)


if __name__ == '__main__':
    main()
