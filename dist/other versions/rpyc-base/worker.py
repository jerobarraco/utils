#!/usr/local/bin/python3
# coding: utf-8

__author__ = "Jeronimo Barraco-Marmol"
__copyright__ = "Copyright (C) 2021 Jeronimo Barraco-Marmol"
__license__ = "GPL V3"
__version__ = "0.4"

import sys
import json
import subprocess
import threading
import traceback
import rpyc

if len(sys.argv) < 2 :
    print("please pass the config file as argument.")
    exit(1)

CONF = json.load(open(sys.argv[1], 'r'))
remapDirs = CONF.get('remapDirs', {})
remapFiles = CONF.get("remapFiles", {})
numTasks = CONF.get("numTasks", 1)
LOCK = threading.Semaphore(numTasks)
DEBUG = CONF.get('debug', False)
TIMEOUT = CONF.get('timeout', None)
if TIMEOUT is not None and TIMEOUT < 1: TIMEOUT = None

class WorkerService(rpyc.Service):
    def on_connect(self, conn):
        # code that runs when a connection is created
        # (to init the service, if needed)
        pass

    def on_disconnect(self, conn):
        # code that runs after the connection has already closed
        # (to finalize the service, if needed)
        pass

    def run(self, cmd, cwd=None, env=None, shell=False):
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

        # xmlrpc cant marshal none, so use this, to avoid accidentally setting an empty environ
        if not env: env = None

        print("cmd", str(cmd))
        print("cwd", str(cwd))
        print('env', str(env))
        print('shell', str(shell))

        retc = 0
        rets = ''
        try:
            ret = subprocess.run(
                cmd, cwd=cwd, check=True, timeout=TIMEOUT, stderr=subprocess.STDOUT, stdout=subprocess.PIPE, env=env, shell=shell
            )
            retc = ret.returncode
            rets = ret.stdout
        except subprocess.TimeoutExpired as e:
            print("Worker TIMEOUT!")
            retc = e.returncode
            rets = e.stdout
        except subprocess.CalledProcessError as e:
            print("Worker Process error!")
            retc = e.returncode
            rets = e.stdout
        except Exception as e:
            print("Worker General Exception!")
            retc = 6
            rets = traceback.format_exc()
        return retc, rets

    def exposed_tryRun(self, cmd, cwd=None, env=None, shell=False):
        global LOCK
        if not LOCK.acquire(False):
            #if DEBUG: print("im busy")
            return (False, 0, "")

        ret = self.run(cmd, cwd, env, shell)
        LOCK.release()
        return (True, ret[0], ret[1])
        # TODO yield

def main():
    port = CONF['port']
    host = CONF['host']
    print("Starting worker. Host=%s:%s Tasks=%s Timeout=%s" % (host, port, numTasks, TIMEOUT))
    from rpyc.utils.server import ThreadedServer
    t = ThreadedServer(WorkerService, hostname=host, port=port, protocol_config={})
    t.start()

if __name__ == '__main__':
    main()
