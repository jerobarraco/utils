#!/usr/local/bin/python3
# coding: utf-8

__author__ = "Jeronimo Barraco-Marmol"
__copyright__ = "Copyright (C) 2021 Jeronimo Barraco-Marmol"
__license__ = "LGPL V3"
__version__ = "0.12"

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
TIMEOUT = CONF.get('timeout', None)
if TIMEOUT is not None and TIMEOUT < 1: TIMEOUT = None

class WorkerService(rpyc.Service):
    proc = None
    rc = 0
    error = ""
    locked = False

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

        # this func is called more than once sometimes, beware
        if self.proc:
            try:
                self.error = self.proc.communicate(timeout=0.5)[0]
            except subprocess.TimeoutExpired:
                # this try, and these lines in this order are necessary according to docs
                self.proc.kill()
                self.error += self.proc.communicate()[0] # stderr pipes to stdout, also communicate sets the returncode
            self.rc = self.proc.returncode
            if DEBUG:
                print('retcode ' + str(self.rc))
                print('stop', datetime.datetime.now())

        self.proc = None

        # this func is called more than once sometimes, beware
        if self.locked:
            self.locked = False
            LOCK.release()

    def run(self, cmd, cwd=None, env=None, shell=False):
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

        print("")
        print('start', datetime.datetime.now())
        print("cmd", str(cmd))
        print("cwd", str(cwd))
        print('env', str(env))
        print('shell', str(shell))

        self.rc = 0
        try:
            self.proc = subprocess.Popen(
                cmd, cwd=cwd, stderr=subprocess.STDOUT, stdout=subprocess.PIPE, env=env, shell=shell,
                # bufsize=1, encoding='utf-8'
                bufsize=1, universal_newlines=True, encoding='utf-8'
            )
        except Exception as e:
            print("Worker General Exception!")
            self.error = traceback.format_exc()
            self.stop()
            self.rc = 6 # stop will set rc, but we might want to make this explicit

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
