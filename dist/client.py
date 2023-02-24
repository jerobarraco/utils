#!/usr/bin/python3
# coding: utf-8
# can use this one if you installed with brew on mac, also change the other .py files
#!/usr/local/bin/python3

__author__ = "Jeronimo Barraco-Marmol"
__copyright__ = "Copyright (C) 2021 Jeronimo Barraco-Marmol"
__license__ = "LGPL V3"
__version__ = "1.0"

# Yeah the config is embedded. i don´t want to have to parse an extra file everytime this client is run. after all it's meant
# to run stuff that are already too heavy for one machine.
# if you need different config copy the client+custom+utils+worker files elsewhere. it's very small.
CONF = {
	"debug": True,
	"timeout": 180,
	"cooldown": 2,
	"sleep": 0,
	"workers": [
		# you can use an ip or "localhost" this is intentional. but "localhost" is preferred, since that will force you to set up ssh tunneling
		# which has security implications
		"localhost:7711",
		"localhost:7722",
	],"dontUse":[ # this is just here just to quickly disable or enable workers by moving this line up&down
		"localhost:7715",
		"localhost:7717",
		"localhost:7722",
		"localhost:7711",
		"localhost:7712",
		"localhost:7718",
		"localhost:7703",
		"localhost:7705",
	],"dontUse":[ # this is just here just to quickly disable or enable workers by moving this line up&down
		"localhost:7723",
	],
	# List of commands to run locally, * means all
	"runLocally": [
	],
	# " List of commands to run using the current environment, * means all"
	"useEnv": [
	],
	# List of commands to run using shell, * means all. shell might create side effects. and a slight security issue if ran outside ssh
	"useShell": [
	],
	# List of commands to pipe stdin to, * means all. TODO fix not being able to handle "eof" client might never finish.
	"useComm": [
		# for example 'grep' (which doesnt work atm)
	]
}

# ------------------ Here be dragons (that means don't touch, unless you're contributing the changes that is)
import os
import rpyc
import subprocess
import sys
import time
import traceback

# locals
import utils
import custom

REAL_PATH = os.path.realpath(__file__)
FNAME = os.path.basename(REAL_PATH)
WORK_PATH = os.path.dirname(REAL_PATH)
WORKERS = CONF.get('workers', [])
# don't go lower than 2, otherwise with many max concurrent tasks in xcode you'll get 20 requests per second,
# will bloat on the server
COOLDOWN = max(CONF.get('cooldown', 2), 2)
DEBUG = CONF.get('debug', False)
TIMEOUT = int(CONF.get('timeout', 0))
CONCONF = {
	"sync_request_timeout": None if TIMEOUT < 1 else TIMEOUT
}
SLEEP = CONF.get('sleep', 0)

def cmdInList(arg, cmd_list):
	if not cmd_list: return False
	for cmd in cmd_list:
		if not cmd: continue #important to not count '' as '*' as endswith will return True
		if cmd == '*': return True
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

def shouldUseComm(args):
	global CONF
	return cmdInList(args[0], CONF.get('useComm', []))

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

def doCommWork(c):
	"""Does the work using the passed worker, and tries to pass the stdin into it"""
	while True:
		in_data = utils.readIfAny(sys.stdin, 0.001, None)
		if in_data is not None:
			in_data = in_data.encode('utf-8')
			# TODO fix: stdin will return '' on EOF, doushio (how to tell the worker)????
			# 	is there something to fix? do i really _need_ to terminate it? isnt eof on stdin a valid run condition? can stdin have something later?
			#if not in_data:
			#	in_data = b'\x1A\r\n' # try sending ctrl z # not working atm https://bytes.com/topic/python/answers/696448-how-write-ctrl-z-serial-port
			#	c.root.stop()

		res = c.root.comm(in_data=in_data)  # no need to wait, client waits
		if res is None: break
		out, err = res
		if out: sys.stdout.write(out.decode('utf-8'))
		if err: sys.stderr.write(err.decode('utf-8'))

def doWork(c):
	"""Does the work using the passed worker, without passing stdin"""
	while True: # less fancy than iter, probably more fasterest
		res = c.root.comm()
		if res is None: break
		out, err = res
		if out: sys.stdout.write(out.decode('utf-8'))
		if err: sys.stderr.write(err.decode('utf-8'))

def tryRunInAWorker(c, args, cwd=None, env=None, shell=False, comm=False):
	global exitTries
	retc = -1
	try:
		executed = c.root.tryRun(args, cwd, env, shell)
		if not executed: return False, -1

		if comm: doCommWork(c)
		else: doWork(c)

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
		# hotfix, why?, xcode keeps sending random interrupts. it will still timeout on too many retries anyway (should this be a raise)
		# return FAILURE
		retc = 8
	return False, retc

def runInWorkers(args, cwd=None, env=None, shell=False, comm=False):
	global WORKERS
	for w in WORKERS:
		c = getConnection(w)
		if not c: continue

		# got a client, do stuff
		executed, retc = tryRunInAWorker(c, args, cwd, env, shell, comm)
		if executed:
			return True, retc

	return False, -1 # could not execute

def runLocal(args, cwd=None, env=None, shell=False):
	try:
		ret = subprocess.run(
			args, cwd=cwd, check=True, env=env, shell=shell
		)
		return ret.returncode
	except subprocess.CalledProcessError as e:
		return e.returncode
	except Exception as e:
		print(traceback.format_exc())
		return -10

def run(args, cwd=None):
	global exitTries, curTime, CONF, SLEEP

	fixSelf(args)
	for fix in custom.FIXES:
		fix(args, CONF)

	run_local = shouldRunLocally(args) or (custom.RUN_LOCAL and custom.RUN_LOCAL(args))
	use_shell = shouldUseShell(args) or (custom.USE_SHELL and custom.USE_SHELL(args))
	use_comm = shouldUseComm(args) or (custom.USE_COMM and custom.USE_COMM(args))
	use_env = shouldUseEnv(args) or (custom.USE_ENV and custom.USE_ENV(args))
	env = None if not use_env else os.environ.copy()
	#if DEBUG:
	#    open(os.path.join(WORK_PATH, 'clog'), 'a').write(
	#        "fname%s\ncommand %s\ncwd %s\nenv %s\nlocal %s\nshell %s\n" % (FNAME, args, cwd, env, run_local, use_shell)
	#    )

	if run_local:
		return runLocal(args, cwd, env, use_shell)

	while True:
		executed, retc = runInWorkers(args, cwd, env, use_shell, use_comm)
		if executed:
			if SLEEP: time.sleep(SLEEP)
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
