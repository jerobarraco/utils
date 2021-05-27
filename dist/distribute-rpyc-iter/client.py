#!/usr/local/bin/python3
# coding: utf-8

__author__ = "Jeronimo Barraco-Marmol"
__copyright__ = "Copyright (C) 2021 Jeronimo Barraco-Marmol"
__license__ = "LGPL V3"
__version__ = "0.10"

CONF = {
    "debug": True,
    "timeout": 300,
    "cooldown": 2,
    "workers": [
        "localhost:7700",
        "localhost:7701",
        "localhost:7702",
        "localhost:7703"
    ],
    "runLocally": [
        "/clang++",
        "/client.py",
        "/emcc++",
        " List of commands to run locally, * means all"
    ],
    "useEnv": [
        '-*',
        '/clang++',
        " List of commands to run using the current environment, * means all"
    ],
    "useShell": [
        "-*",
        " List of commands to run using shell, * means all"
    ]
}

# ------------------ Here be dragons
import json
import os
import rpyc
import subprocess
import sys
import time
import traceback

WORK_PATH = os.path.realpath(os.path.dirname(__file__))
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

def cmdInList(arg, cmd_list):
    if '*' in cmd_list: return True
    for cmd in cmd_list:
        if arg.endswith(cmd): return True
    return False

def shouldRunLocally(args):
    global CONF, WORKERS
    if not WORKERS: return True
    if cmdInList(args[0], CONF.get('runLocally', [])): return True

    # run local files locally
    for a in args:
        if a.startswith('@/private') or a.startswith('/private'): return True

    return False

def shouldUseShell(args):
    global CONF
    for a in args:
        if a in ('&&', ';', '||'): return True
    return cmdInList(args[0], CONF.get('useShell', []))

def shouldUseEnv(args):
    global CONF
    return cmdInList(args[0], CONF.get('useEnv', []))

conns = {}
curTime = 0
exitTries = 0
def runInWorkers(args, cwd=None, env=None, shell=False):
    global exitTries, conns, curTime
    for w in WORKERS:
        # TODO ? move this inner loop as function please ?
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
            executed = c.root.tryRun(args, cwd, env, shell)
            if not executed: continue

            for line in iter(c.root.getLine, None):
                # sys.stdout.write(line.decode('utf-8'))
                sys.stdout.write(line)  # decode happens on worker

            retc = c.root.getExitCode()
            if retc:
                error = c.root.getError()
                if error:
                    print(error)
            return True, retc
        except KeyboardInterrupt as e:
            # Xcode loooves to send this :(
            rets = traceback.format_exc()
            if DEBUG: print(rets)
            exitTries += 1
            if exitTries > 5: raise e
        except rpyc.AsyncResultTimeout as e:
            rets = traceback.format_exc()
            if DEBUG: print(rets)
            raise e
        except EOFError as e:  # TODO verify this is ok with XCode
            rets = traceback.format_exc()
            if DEBUG: print(rets)
            raise e
        except Exception as e:
            rets = traceback.format_exc()
            if DEBUG: print(rets)
            retc = 8
            continue  # hotfix, why?, xcode keeps sending random interrupts. it will still timeout on too many retries anyway
            # return retc

    return False, 0

def fixLink(args):
    """This is just a test to try to fix linking.
    Will mutate args"""
    is_clang = args[0].endswith('/clang') or args[0].endswith('/clang_')
    if not is_clang: return
    has_out = False
    for a in args:
        if a == '-o':
            has_out = True
            continue
        if not has_out: continue
        if a.endswith('.so'):
            args[0] = '/clang++'.join(args[0].rsplit('/clang', 1))
        return

def runLocal(args, cwd=None, env=None, shell=False):
    ret = None
    args[0] = args[0] + '_'
    try:
        ret = subprocess.run(
            args, cwd=cwd, check=True, stderr=subprocess.STDOUT, stdout=subprocess.PIPE, env=env, shell=shell, encoding='utf-8'
        )
        print(ret.stdout)
        return ret.returncode
    except subprocess.CalledProcessError as e:
        print(e.output)
        print(traceback.format_exc())
        return -10
    except Exception as e:
        print(traceback.format_exc())
        return -10

def run(args, cwd=None):
    global exitTries, curTime, CONF

    fixLink(args)
    use_shell = shouldUseShell(args)
    run_local = shouldRunLocally(args)
    env = None if not shouldUseEnv(args) else os.environ.copy()
    #if DEBUG:
    #    open(os.path.join(os.path.realpath(os.path.???(__file__)), 'clog'), 'a').write(
    #        "command %s\ncwd %s\nenv %s\nlocal %s\n" % (args, env, cwd, run_local)
    #    )

    if run_local:
       return runLocal(args, cwd, env, use_shell)

    while True:
        executed, retc = runInWorkers(args, cwd, env, use_shell)
        if executed:
            return retc

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
