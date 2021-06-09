#!/usr/local/bin/python3
# coding: utf-8

__author__ = "Jeronimo Barraco-Marmol"
__copyright__ = "Copyright (C) 2021 Jeronimo Barraco-Marmol"
__license__ = "LGPL V3"
__version__ = "0.14"

import datetime
import sys
import json
import subprocess
import threading
import traceback
import rpyc

if len(sys.argv) < 2:
    print("please pass the config file as argument.")
    exit(1)

CONF = json.load(open(sys.argv[1], 'r'))
remapDirs = CONF.get('remapDirs', {})
remapFiles = CONF.get("remapFiles", {})
numTasks = CONF.get("numTasks", 1)
LOCK = threading.Semaphore(int(numTasks))
DEBUG = CONF.get('debug', False)
TIMEOUT = CONF.get('timeout', 0)

class WorkerService(rpyc.Service):
    proc = None
    rc = 0
    error = ""
    locked = False
    timer = None
    stopping = False
    start_time = None
    def on_connect(self, conn):
        # code that runs when a connection is created
        # (to init the service, if needed)
        pass

    def on_disconnect(self, conn):
        # code that runs after the connection has already closed
        # (to finalize the service, if needed)
        self.stop() # make sure to stop the process, can happen on certain conditions

    def stop(self):
        global LOCK
        if self.stopping: return
        self.stopping = True # once stopped no need to stop again (hopefully)

        # first check for the timer. we are not really reentrant
        if self.timer:
            self.timer.cancel()
            self.timer = None

        # this func is called more than once sometimes, beware
        if self.proc:
            try:
                self.error = self.proc.communicate(timeout=0.5)[0]
            except subprocess.TimeoutExpired:
                # this try, and these lines in this order are necessary according to docs
                self.proc.kill()
                self.error += self.proc.communicate()[0] # stderr pipes to stdout, also communicate sets the returncode

        if self.proc:# self.proc might have been killed by timeout
            self.rc = self.proc.returncode
            if DEBUG:
                delta = datetime.datetime.now() - self.start_time
                print('stop [%i] @ %s' % (self.rc, delta))
            else:
                sys.stdout.write(".")
                sys.stdout.flush()

        self.proc = None

        # this func is called more than once sometimes, beware
        if self.locked:
            self.locked = False
            LOCK.release()

    def timeout(self):
        if DEBUG:
            print("TIMEOUT!")
        else:
            sys.stdout.write('|')
            sys.stdout.flush()

        self.stop()
        # stop will try to set these
        self.rc = max(self.rc, 13)
        self.error += "OUTATIME!"

    def run(self, cmd, cwd=None, env=None, shell=False):
        global TIMEOUT, DEBUG
        self.error = ""
        self.rc = 0
        self.proc = None
        # a bit deprecated, to be able to run things locally.
        for k, v in remapFiles.items():
            c = cmd[0]
            if c.endswith(k):
                cmd[0] = v.join(c.rsplit(k, 1)) # replace only last occurrence

        # a bit deprecated,
        for k, v in remapDirs.items():
            # also remap cwd
            if cwd.startswith(k):
                cwd = cwd.replace(k, v, 1)
            # remap dirs in command
            for i, c in enumerate(cmd):
                if c.startswith(k):
                    c = c.replace(k, v, 1)
                    cmd[i] = c

        # to avoid accidentally setting an empty environ
        if not env: env = None

        self.start_time = datetime.datetime.now()
        if DEBUG:
            print("")
            print('start', self.start_time)
            print("cmd", str(cmd))
            print("cwd", str(cwd))
            print('env', str(env))
            print('shell', str(shell))
        else:
            sys.stdout.write("-")
            sys.stdout.flush()

        if TIMEOUT > 0 :
            self.timer = threading.Timer(TIMEOUT, self.timeout)
            self.timer.start()

        self.rc = 0
        try:
            self.proc = subprocess.Popen(
                cmd, cwd=cwd, stderr=subprocess.STDOUT, stdout=subprocess.PIPE, env=env, shell=shell,
                # bufsize=1, encoding='utf-8'
                bufsize=1, universal_newlines=True, encoding='utf-8'
            )
        except Exception as e:
            if DEBUG:
                print("Worker General Exception!")
            else:
                sys.stdout.write('X')
                sys.stdout.flush()

            self.error = traceback.format_exc()
            self.stop()
            self.rc = 6 # stop will set rc, but we might want to make this explicit
            # still return True after this, so the client knows we tried to run (but failed)

        return True

    def exposed_tryRun(self, cmd, cwd=None, env=None, shell=False):
        global LOCK
        if not LOCK.acquire(False):
            self.error = "im busy"
            return False

        self.locked = True
        self.run(cmd, cwd, env, shell)
        return True

    def exposed_getLine(self):
        line = None
        if self.proc:
            try:
                line = self.proc.stdout.readline()
            except Exception as e:
                line = " ERROR WHILE TRYING TO READ THE OUTPUT\n"
                line += traceback.format_exc()
                print(line)

            self.rc = self.proc.poll()

            # force it to be None, as iter in client checks for None
            if not line:
                line = None
                self.stop()

        return line

    def exposed_getExitCode(self):
        return self.rc

    def exposed_getError(self):
        return self.error

    def exposed_ping(self):
        """Test the connection"""
        return True

def main():
    port = CONF['port']
    host = CONF['host']
    print("Starting worker. Host=%s:%s Tasks=%s Timeout=%s" % (host, port, numTasks, TIMEOUT))
    from rpyc.utils.server import ThreadedServer
    t = ThreadedServer(WorkerService, hostname=host, port=port, protocol_config={})
    t.start()

if __name__ == '__main__':
    main()
