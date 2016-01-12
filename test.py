#coding:utf-8
from datetime import datetime
import logging
import os
import sys
import time

from ArbiterHandler import BaseHandler


def task():
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    pid = os.getpid()
    logger = logging.getLogger('worker')
    for i in xrange(10000):
        logger.info('current worker process pid is %s'%pid)
        time.sleep(1)

def main():
    logging.basicConfig(level=logging.INFO)
    ruler = BaseHandler(task, num_workers=1)
    ruler.run(ctl=True)

if __name__ == '__main__':
    main()
