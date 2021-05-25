#!/usr/bin/python3
# coding: utf-8

__author__ = "Jeronimo Barraco-Marmol"
__copyright__ = "Copyright (C) 2021 Jeronimo Barraco-Marmol"
__license__ = "GPL V3"
__version__ = "0.2"

import sys
import time
import os
import traceback
import xmlrpc.client
import json
import subprocess

WORKERS = 'Put the real path of this script here'
conf = json.load(open(os.path.join(WORKERS, 'client.json'), 'r'))
workers = conf.get('workers', [])
# don't go lower than 1, otherwise with many max concurrent tasks in xcode you'll get 20 requests per second,
# will eat the bloat on the server
cooldown = max(conf.get('cooldown', 1), 1)
DEBUG = conf.get('debug', False)
TIMEOUT = conf.get('timeout', 0)
curTime = 0
exitTries = 0

def cmdInList(arg, list):
    for cmd in list:
        if arg.endswith(cmd): return True
    return False

def shouldRunLocally(args):
    if not workers: return True
    return cmdInList(args[0], conf.get('runLocally', []))

def run(args, cwd=None, env={}):
    global exitTries, curTime

    use_shell = cmdInList(args[0], conf.get('useShell', []))
    # clear env if not needed
    if not cmdInList(args[0], conf.get('sendEnv', [])):
        env = {}

    if shouldRunLocally(args):
        args[0] = args[0] + '_'
        if DEBUG: print("running locally")
        ret = subprocess.run(args, cwd=cwd, check=True, stderr=subprocess.STDOUT, stdout=subprocess.PIPE, env=env, shell=use_shell)
        return ret.returncode, ret.stdout

    conns = {}
    busy = True
    while busy:
        for w in workers:
            rets = ''
            retc = 0
            try:
                c = conns.get(w, None)
                if c is None:
                    c = xmlrpc.client.ServerProxy(w)
                    conns[w] = c
            except Exception as e:
                if DEBUG: print(traceback.format_exc())
                continue # try next worker

            try:
                executed, retc, rets = c.tryRun(args, cwd, env, use_shell)
                if executed:
                    return retc, rets
            except KeyboardInterrupt as e:
                exitTries += 1
                if exitTries > 5:
                    print("too many errors")
                    raise e
            except Exception as e:
                rets = traceback.format_exc()
                retc = 8
                continue # hotfix, xcode seems to keep killing this. something wrong...  why?, doesnt matter, rpyc might fix this. it will still timeout on too many retries
                return retc, rets

        time.sleep(cooldown)
        if TIMEOUT > 0:
            curTime += 1
            if curTime >= TIMEOUT:
                return 9, "CLIENT TIMEOUT!"

if __name__ == "__main__":
    retc, rets = run(sys.argv, os.getcwd(), os.environ.copy())
    print(rets)
    exit(retc)