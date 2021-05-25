#!/usr/local/bin/python3
# coding: utf-8

__author__ = "Jeronimo Barraco-Marmol"
__copyright__ = "Copyright (C) 2021 Jeronimo Barraco-Marmol"
__license__ = "LGPL V3"
__version__ = "0.8"

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
        pass
        self.stop()

    def stop(self):
        global LOCK
        if self.proc:
            self.rc = self.proc.wait(0.5)
            self.proc.kill()

        self.proc = None

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
            for i, c in enumerate(cmd):
                if c.startswith(k):
                    c = c.replace(k, v, 1)
                    cmd[i] = c

        # to avoid accidentally setting an empty environ
        if not env: env = None

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
            """
        except subprocess.TimeoutExpired as e:
            print("Worker TIMEOUT!")
            self.rc = e.returncode
            self.error = e.stdout
            self.proc = None
        except subprocess.CalledProcessError as e:
            print("Worker Process error!")
            self.rc = e.returncode
            self.error = e.stdout
            self.proc = None"""
        except Exception as e:
            print("Worker General Exception!")
            self.rc = 6
            self.error = traceback.format_exc()
            self.stop()

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
            self.rc = self.proc.poll()
            try:
                line = self.proc.stdout.readline()
            except Exception as e:
                line = " ERROR WHILE TRYING TO READ THE OUTPUT\n"
                line += traceback.format_exc()
                print(line)
            # force it to be None,
            if not line:
                line = None
                self.stop()

        return line

    def exposed_getExitCode(self):
        return self.rc

    def exposed_getError(self):
        return self.error

def main():
    port = CONF['port']
    host = CONF['host']
    print("Starting worker. Host=%s:%s Tasks=%s Timeout=%s" % (host, port, numTasks, TIMEOUT))
    from rpyc.utils.server import ThreadedServer
    t = ThreadedServer(WorkerService, hostname=host, port=port, protocol_config={})
    t.start()

if __name__ == '__main__':
    main()
