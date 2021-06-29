#!/usr/local/bin/python3
# coding: utf-8

__author__ = "Jeronimo Barraco-Marmol"
__copyright__ = "Copyright (C) 2021 Jeronimo Barraco-Marmol"
__license__ = "LGPL V3"
__version__ = "0.19"

CONF = {
    "debug": True,
    "timeout": 180,
    "cooldown": 2,
    "workers": [
        "localhost:7715",
        "localhost:7717",
        "localhost:7722",
        "localhost:7703",
        "localhost:7711",
        "localhost:7712",
        "localhost:7718",
    ],"dontUse":[ # this is just here just to quickly disable or enable workers by moving this line up&down

    ],
    # List of commands to run locally, * means all
    "runLocally": [
        "/clang++", # for android linking
        "/client.py",
    ],
    # " List of commands to run using the current environment, * means all"
    "useEnv": [
    ],
    # " List of commands to run using shell, * means all. shell might create side effects. and a slight security issue if ran outside ssh
    "useShell": [
    ]
}

# ------------------ Here be dragons
import os
import rpyc
import subprocess
import sys
import time
import traceback

REAL_PATH = os.path.realpath(__file__)
FNAME = os.path.basename(REAL_PATH)
WORK_PATH = os.path.dirname(REAL_PATH)
WORKERS = CONF.get('workers', [])
# don't go lower than 2, otherwise with many max concurrent tasks in xcode you'll get 20 requests per second,
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
def getConnection(address):
    global conns, CONCONF
    c = None
    try:
        c = conns.get(address, None)
        if not c: # create a new connection if it doesn't exists
            host, port = address.rsplit(':', 1)
            c = rpyc.connect(host, int(port), config=CONCONF)
            conns[address] = c
        # Test the connection AND the worker. rpyc raises an exception when trying to execute, not when connecting (at least sometimes).
        # Note it does this everytime. Just because it was working before doesn't means it still does.
        if not c.root.ping(): return None
    except ConnectionRefusedError as e:
        return None  # try next worker
    except Exception as e:
        if DEBUG:
            print("Connection to worker failed:")
            print(traceback.format_exc())
        return None  # try next worker
    return c

def tryRunInAWorker(c, args, cwd=None, env=None, shell=False):
    global exitTries
    retc = -1
    try:
        executed = c.root.tryRun(args, cwd, env, shell)
        if not executed: return False, -1

        for out, err in iter(c.root.comm, None):
            if out: sys.stdout.write(out.decode('utf-8'))
            if err: sys.stderr.write(err.decode('utf-8'))
            # sys.stdout.write(line)# decode happens on worker (maybe if encoded decode?)

        retc = c.root.getExitCode()
        return True, retc
    except KeyboardInterrupt as e:
        # Xcode loooves to send this :(
        rets = traceback.format_exc()
        if DEBUG: print(rets)

        exitTries += 1
        if exitTries > 5:
            raise e
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
        return False, -1  # hotfix, why?, xcode keeps sending random interrupts. it will still timeout on too many retries anyway
        # retc = 8
        # return False, retc

def runInWorkers(args, cwd=None, env=None, shell=False):
    global exitTries, conns, curTime
    for w in WORKERS:
        c = getConnection(w)
        if not c: continue

        # got a client, do stuff
        executed, retc = tryRunInAWorker(c, args, cwd, env, shell)
        if executed:
            return True, retc

    return False, -1 # could not execute

def fixLink(args):
    """This is just to try to fix linking (on android)
    if the executable is clang, adds ++ and removes _
    This depends on you using clang as the compiler (and not clang++)
    Will mutate args"""

    # only check on clang not clang++ (important because we need to remove _)
    # this means, you should avoid to shadow/override clang++
    is_clang = args[0].endswith('/clang') or args[0].endswith('/clang_')
    if not is_clang: return False

    has_out = False
    is_link = False
    #verify the out is an so
    for a in args:
        if a == '-o':
            has_out = True
            continue
        if not has_out: continue
        if a.endswith('.so'):
            is_link = True
            break
        has_out = False

    if is_link:
        if args[0][-1] == '_':
            args[0]=args[0][:-1] #remove the _ , linker needs to not have it (really)

        if not args[0].endswith('++'): # force to use ++
            args[0] += '++'
    return is_link

def fixSelf(args):
    """
    Allows to run a different commands directly from client.
    if the script is the 1st param, it will remove it.
    if the 1st param is the same file as the script (using a link) it adds a _
    This will mutate args
    """

    # notice no os.realpath on args[0]. this is intentional,
    # and also allows linking to client (shadowing) (the official way to use this script)
    # #goes first as it can clash with the one below
    #if args[0] == REAL_PATH:
    # this one is safer, means that if its called by something with the same file name (client.py), regardless of the folder.
    # you can rename your client.py otherwise
    if os.path.basename(args[0]) == FNAME:
        args.pop(0)
    else: # this is safer, specially in windows, where we might want to use pyinstaller to shadow an exe
        # this is the usual usage, avoid looping on itself.
        args[0] = args[0] + '_'

def runLocal(args, cwd=None, env=None, shell=False):
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

    fixSelf(args)
    is_link = fixLink(args)
    run_local = is_link or shouldRunLocally(args)
    use_shell = shouldUseShell(args)
    env = None if not shouldUseEnv(args) else os.environ.copy()
    #if DEBUG:
    #    open(os.path.join(WORK_PATH, 'clog'), 'a').write(
    #        "fname%s\ncommand %s\ncwd %s\nenv %s\nlocal %s\nshell %s\n" % (FNAME, args, cwd, env, run_local, use_shell)
    #    )

    if run_local:
       return runLocal(args, cwd, env, use_shell)

    while True:
        executed, retc = runInWorkers(args, cwd, env, use_shell)
        if executed:
            return retc

        time.sleep(COOLDOWN)
        if TIMEOUT > 0:
            curTime += COOLDOWN
            if curTime >= TIMEOUT:
                print("CLIENT TIMEOUT!")
                return 9

if __name__ == "__main__":
    conns = {}
    curTime = 0
    exitTries = 0

    retc = run(sys.argv[:], os.getcwd())
    exit(retc)
