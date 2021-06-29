#!/usr/bin/python3
# coding: utf-8

__author__ = "Jeronimo Barraco-Marmol"
__copyright__ = "Copyright (C) 2021 Jeronimo Barraco-Marmol"
__license__ = "GPL V3"
__version__ = "0.3"

import sys
import json
import subprocess
import threading
import socketserver
import traceback
from xmlrpc.server import SimpleXMLRPCServer
from xmlrpc.server import SimpleXMLRPCRequestHandler

if len(sys.argv) < 2 :
    print("please pass the config file as argument.")
    exit(1)

conf = json.load(open(sys.argv[1], 'r'))
remapDirs = conf.get('remapDirs', {})
remapFiles = conf.get("remapFiles", {})
numTasks = conf.get("numTasks", 1)
lock = threading.Semaphore(numTasks)
DEBUG = conf.get('debug', False)
TIMEOUT = conf.get('timeout', None)
if TIMEOUT is not None and TIMEOUT < 1: TIMEOUT = None

def run(cmd, cwd=None, env=None, shell=False):
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

def tryRun(cmd, cwd=None, env=None, shell=False):
    if not lock.acquire(False):
        #if DEBUG: print("im busy")
        return (False, 0, "")

    ret = run(cmd, cwd, env, shell)
    lock.release()
    return (True, ret[0], ret[1])

# Restrict to a particular path.
class RequestHandler(SimpleXMLRPCRequestHandler):
    rpc_paths = ('/RPC2',)

class RPCThreading(socketserver.ThreadingMixIn, SimpleXMLRPCServer):
    pass

print("Starting worker. Host=%s:%s Tasks=%s Timeout=%s" % (conf['host'], conf['port'], numTasks, TIMEOUT) )
# Create server
with RPCThreading((conf['host'], int(conf['port'])), requestHandler=RequestHandler, logRequests=DEBUG) as server:
    server.register_introspection_functions()

    #server.register_function(run)
    server.register_function(tryRun)

    # Run the server's main loop
    server.serve_forever()