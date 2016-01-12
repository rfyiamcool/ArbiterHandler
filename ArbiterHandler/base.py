#coding:utf-8
import errno
import fcntl
import logging
import os
import signal
import sys

SIGNAL_IDS = {
    'SIGCHLD': 'C',
    'SIGHUP':  'H',
    'SIGINT':  'I',
    'SIGQUIT': 'Q',
    'SIGUSR1': '1',
    'SIGUSR2': '2',
    'SIGTERM': 'T',
    'SIGTTIN': 'ADD',
    'SIGTTOU': 'REDUCE',
}
SIGNAL_IDS_REV = dict((v, k) for (k, v) in SIGNAL_IDS.iteritems())

WORKER_QUIT = 'Q'

class BaseHandler(object):

    def __init__(self, worker_func, num_workers=1):
        self.worker_func = worker_func
        self.num_workers = num_workers
        self._status = None
        self._signal_pipe = None
        self._workers = {}
        self._log = logging.getLogger('forkd')

    def run(self,ctl=True):
        self._status = 'starting'
        self._setup()
        self._spawn_workers()
        self._status = 'running'
        self._loop()
        self._status = 'ended'

    def _shutdown(self):
        if self._status == 'shutdown':
            return
        self._log.info('[%s] shutting down', os.getpid())
        self._status = 'shutdown'
        self.num_workers = 0
        self._shutdown_workers()

    def _shutdown_workers(self):
        for pid in self._workers:
            self._shutdown_worker(pid)

    def _shutdown_worker(self, pid):
        worker = self._workers[pid]
        print 69,pid
        if worker['status'] != 'running':
            return
        worker['status'] = 'shutdown'
        os.write(worker['pipe'][1], WORKER_QUIT)
        os.kill(pid,9)

    def _loop(self):
        f = os.fdopen(self._signal_pipe[0], 'r')
        while self._workers:
            try:
                msg = f.readline()
                if not msg:
                    break
                # Parse message
                signal_id, from_pid = msg.strip().split()
                from_pid = int(from_pid)
                # Call signal handler.
                handler = getattr(self, '_' + SIGNAL_IDS_REV[signal_id])
                handler(from_pid)
            except IOError, e:
                if e.errno != errno.EINTR:
                    self._log.info('IOError %x: %s', e.errno, unicode(e))
                    raise
            except Exception:
                self._log.exception('Unexpected exception in master process loop')
                raise

    def _setup(self):
        self._signal_pipe = os.pipe()
        for name in SIGNAL_IDS:
            self._signal(name)

    def _spawn_workers(self):
        for i in range(max(self.num_workers - len(self._workers), 0)):
            pid, pipe = self._spawn_worker()
            self._workers[pid] = {'pipe': pipe, 'status': 'running'}
            self._log.info('[%s] started worker %s', os.getpid(), pid)

    def _respawn_workers(self):
        self._log.info('[%s] respawning workers', os.getpid())
        for pid, worker in self._workers.iteritems():
            if worker['status'] == 'running':
                self._shutdown_worker(pid)

    def _spawn_worker(self):
        worker_pipe = os.pipe()
        fcntl.fcntl(worker_pipe[0], fcntl.F_SETFL, fcntl.fcntl(worker_pipe[0], fcntl.F_GETFL) | os.O_NONBLOCK)

        pid = os.fork()
        if pid:
            return pid, worker_pipe

        pid = os.getpid()
        self._log.debug('[%s] worker running', pid)

        worker = _resolve_worker(self.worker_func)()

        while True:
            try:
                ch = os.read(worker_pipe[0], 1)
            except OSError, e:
                if e.errno != errno.EAGAIN:
                    raise
            else:
                if ch == WORKER_QUIT:
                    self._log.debug('[%s] received QUIT', pid)
                    break
            try:
                worker.next()
            except StopIteration:
                break
            except Exception, e:
                self._log.exception('[%s] exception in worker', pid)
                sys.exit(-1)

        self._log.debug('[%s] worker ending', pid)
        sys.exit(0)

    def _add_worker(self):
        self.num_workers += 1
        self._log.info('[%s] adding worker, num_workers=%d', os.getpid(), self.num_workers)
        self._spawn_workers()

    def _remove_worker(self):
        if self.num_workers <= 1:
            return
        self.num_workers -= 1
        self._log.info('[%s] removing worker, num_workers=%d', os.getpid(), self.num_workers)
        for pid, worker in self._workers.iteritems():
            if worker['status'] == 'running':
                self._shutdown_worker(pid)
                break

    def _signal(self, signame):
        signal_id = SIGNAL_IDS[signame]
        def handler(signo, frame):
            self._log.debug('[%d] signal: %s', os.getpid(), signame)
            os.write(self._signal_pipe[1], '%s %s\n' % (signal_id, os.getpid()))
        signal.signal(getattr(signal, signame), handler)

    def _SIGCHLD(self, from_pid):
        self._log.debug('[%s] SIGCHLD', os.getpid())
        while self._workers:
            pid, status = os.waitpid(-1, os.WNOHANG)
            if not pid:
                break
            status = status >> 8
            self._log.info('[%s] worker %s ended with status: %s', os.getpid(), pid, status)
            worker = self._workers.pop(pid)
            os.close(worker['pipe'][0])
            os.close(worker['pipe'][1])
        self._spawn_workers()

    def _SIGHUP(self, from_pid):
        self._log.debug('[%s] SIGHUP from %d', os.getpid(), from_pid)
        if from_pid == os.getpid():
            self._respawn_workers()
        else:
            self._shutdown_worker(from_pid)

    def _SIGINT(self, from_pid):
        self._log.debug('[%s] SIGINT from %d', os.getpid(), from_pid)
        if from_pid == os.getpid():
            self._shutdown()
        else:
            self._shutdown_worker(from_pid)

    def _SIGQUIT(self, from_pid):
        self._log.debug('[%s] SIGQUIT from %d', os.getpid(), from_pid)
        if from_pid == os.getpid():
            self._shutdown()
        else:
            self._shutdown_worker(from_pid)

    def _SIGTERM(self, from_pid):
        self._log.debug('[%s] SIGTERM from %d', os.getpid(), from_pid)
        if from_pid == os.getpid():
            self._shutdown()
        else:
            self._shutdown_worker(from_pid)

    def _SIGUSR1(self, from_pid):
        self._log.debug('[%s] SIGUSR1 from %d', os.getpid(), from_pid)
        if from_pid == os.getpid():
            self._add_worker()

    def _SIGUSR2(self, from_pid):
        self._log.debug('[%s] SIGUSR2 from %d', os.getpid(), from_pid)
        if from_pid == os.getpid():
            self._remove_worker()

    def _SIGTTIN(self,from_pid):
        self._log.debug('[%s] SIGTTIN from %d', os.getpid(), from_pid)
        if from_pid == os.getpid():
            self._add_worker()
        
    def _SIGTTOU(self,from_pid):
        self._log.debug('[%s] SIGTTOU from %d', os.getpid(), from_pid)
        if from_pid == os.getpid():
            self._remove_worker()

def _resolve_worker(worker):
    if not isinstance(worker, basestring):
        return worker

    module_name, func_name = worker.split(':')
    module = __import__(module_name)
    for name in module_name.split('.')[1:]:
        module = getattr(module, name)
    return getattr(module, func_name)
