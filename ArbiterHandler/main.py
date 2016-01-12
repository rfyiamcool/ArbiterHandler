import argparse
import logging
import sys

from base import ForkBase


def main():

    parser = argparse.ArgumentParser()
    parser.add_argument('-l', '--log-level', metavar='log_level',
                        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                        default='WARNING', help='log level')
    parser.add_argument('-n', '--num-workers', metavar='num_workers', type=int,
                        default=1, help='initial number of worker processes')
    parser.add_argument('worker',
                        help='worker spec, e.g. mypackage.mymodule:worker')
    parser.add_argument('worker_args', metavar='worker_arg', nargs='*',
                        help='args passed to the worker function via sys.argv')
    args = parser.parse_args()

    logging.basicConfig(level=getattr(logging, args.log_level))

    manager = core.Forkd(args.worker, num_workers=args.num_workers)
    sys.argv[:] = [args.worker] + args.worker_args
    manager.run()


if __name__ == '__main__':
    main()
