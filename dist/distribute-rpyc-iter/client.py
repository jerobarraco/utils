#!/usr/local/bin/python3
# coding: utf-8

__author__ = "Jeronimo Barraco-Marmol"
__copyright__ = "Copyright (C) 2021 Jeronimo Barraco-Marmol"
__license__ = "LGPL V3"
__version__ = "0.7"

import json
import os
import rpyc
import subprocess
import sys
import time
import traceback

WORK_PATH = "! YO put the path to this script here plz :) "
CONF = json.load(open(os.path.join(WORK_PATH, 'client.json'), 'r'))
WORKERS = CONF.get('workers', [])
# don't go lower than 1, otherwise with many max concurrent tasks in xcode you'll get 20 requests per second,
# will eat the bloat on the server
COOLDOWN = max(CONF.get('cooldown', 2), 2)
DEBUG = CONF.get('debug', False)
TIMEOUT = CONF.get('timeout', 0)
CONCONF = {
    "sync_request_timeout": None if TIMEOUT < 1 else TIMEOUT
}

curTime = 0
exitTries = 0
conns = {}

def cmdInList(arg, list):
    for cmd in list:
        if arg.endswith(cmd): return True
    return False

def shouldRunLocally(args):
    if not WORKERS: return True
    return cmdInList(args[0], CONF.get('runLocally', []))

def run(args, cwd=None):
    global exitTries, curTime

    use_shell = cmdInList(args[0], CONF.get('useShell', []))

    env = "" if not cmdInList(args[0], CONF.get('sendEnv', [])) else os.environ.copy()

    run_local = shouldRunLocally(args)
    if DEBUG:
        open(os.path.join(WORK_PATH, 'clog'), 'a').write(
            "command %s\ncwd %s\nenv %s\nlocal %s\n" % (args, env, cwd, run_local)
        )

    if run_local:
        args[0] = args[0] + '_'
        ret = subprocess.run(args, cwd=cwd, check=True, stderr=subprocess.STDOUT, stdout=subprocess.PIPE, env=env, shell=use_shell)
        print(ret.stdout)
        return ret.returncode

    conns = {}
    busy = True
    while busy:
        for w in WORKERS:
            retc = 0
            c = None
            try:
                c = conns.get(w, None)
                if not c:
                    host, port = w.rsplit(':', 1)
                    c = rpyc.connect(host, int(port), config=CONCONF)
                    conns[w] = c
            except Exception as e:
                if DEBUG: print(traceback.format_exc())
                continue  # try next worker

            if not c: continue

            # got a client, do stuff
            try:
                executed = c.root.tryRun(args, cwd, env, use_shell)
                if not executed: continue

                for line in iter(c.root.getLine, None):
                    #sys.stdout.write(line.decode('utf-8'))
                    sys.stdout.write(line)
                retc = c.root.getExitCode()
                if retc:
                    error = c.root.getError()
                    if error:
                        print(error)
                return retc
            except KeyboardInterrupt as e:
                rets = traceback.format_exc()
                if DEBUG: print(rets)
                exitTries += 1
                if exitTries > 5: raise e
            except rpyc.AsyncResultTimeout as e:
                rets = traceback.format_exc()
                if DEBUG: print(rets)
                raise e
            except EOFError as e:
                rets = traceback.format_exc()
                if DEBUG: print(rets)
                raise e
            except Exception as e:
                rets = traceback.format_exc()
                if DEBUG: print(rets)
                retc = 8
                continue # hotfix, why?, xcode keeps sending random interrupts. it will still timeout on too many retries
                # return retc

        time.sleep(COOLDOWN)
        if TIMEOUT > 0:
            curTime += 1
            if curTime >= TIMEOUT:
                print("CLIENT TIMEOUT!")
                return 9

if __name__ == "__main__":
    retc = run(sys.argv[:], os.getcwd())
    exit(retc)