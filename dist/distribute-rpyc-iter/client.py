#!/usr/local/bin/python3
# coding: utf-8

__author__ = "Jeronimo Barraco-Marmol"
__copyright__ = "Copyright (C) 2021 Jeronimo Barraco-Marmol"
__license__ = "LGPL V3"
__version__ = "0.9"

CONF = {
    "debug": True,
    "timeout": 300,
    "runLocally": [
        "clang++",
        "client.py",
        "emcc++"
    ],
    "workers": [
        "localhost:7700",
        "localhost:7701",
        "localhost:7702",
        "localhost:7703"
    ],
    "sendEnv": [],
    "useShell": []
}

# ------------------ Here be dragons
import json
import os
import rpyc
import subprocess
import sys
import time
import traceback

#WORK_PATH = "! YO put the path to this script here plz :) "
#CONF = json.load(open(os.path.join(WORK_PATH, 'client.json'), 'r'))
WORKERS = CONF.get('workers', [])
# don't go lower than 1, otherwise with many max concurrent tasks in xcode you'll get 20 requests per second,
# will eat the bloat on the server
COOLDOWN = max(CONF.get('cooldown', 2), 2)
DEBUG = CONF.get('debug', False)
TIMEOUT = int(CONF.get('timeout', 0))
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
    global CONF
    if not WORKERS: return True
    return cmdInList(args[0], CONF.get('runLocally', []))

def run(args, cwd=None):
    global exitTries, curTime, CONF

    use_shell = cmdInList(args[0], CONF.get('useShell', []))

    env = None if not cmdInList(args[0], CONF.get('sendEnv', [])) else os.environ.copy()

    run_local = shouldRunLocally(args)
    #if DEBUG:
    #    open(os.path.join(WORK_PATH, 'clog'), 'a').write(
    #        "command %s\ncwd %s\nenv %s\nlocal %s\n" % (args, env, cwd, run_local)
    #    )

    if run_local:
        args[0] = args[0] + '_'
        ret = subprocess.run(args, cwd=cwd, check=True, stderr=subprocess.STDOUT, stdout=subprocess.PIPE, env=env, shell=use_shell)
        print(ret.stdout)
        return ret.returncode

    conns = {}
    while True:
        for w in WORKERS:
            # TODO move this inner loop as function please
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
                    sys.stdout.write(line) #decode happens on worker

                retc = c.root.getExitCode()
                if retc:
                    error = c.root.getError()
                    if error:
                        print(error)
                return retc
            except KeyboardInterrupt as e:
                #Xcode loooves to send this :(
                rets = traceback.format_exc()
                if DEBUG: print(rets)
                exitTries += 1
                if exitTries > 5: raise e
            except rpyc.AsyncResultTimeout as e:
                rets = traceback.format_exc()
                if DEBUG: print(rets)
                raise e
            except EOFError as e: # TODO verify this is ok with XCode
                rets = traceback.format_exc()
                if DEBUG: print(rets)
                raise e
            except Exception as e:
                rets = traceback.format_exc()
                if DEBUG: print(rets)
                retc = 8
                continue # hotfix, why?, xcode keeps sending random interrupts. it will still timeout on too many retries anyway
                # return retc
        #ForEnd
        time.sleep(COOLDOWN)
        if TIMEOUT > 0:
            curTime += 1
            if curTime >= TIMEOUT:
                print("CLIENT TIMEOUT!")
                return 9

if __name__ == "__main__":
    retc = run(sys.argv[:], os.getcwd())
    exit(retc)