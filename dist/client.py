#!/usr/bin/python3 -u
# coding: utf-8
# can use this one if you installed with brew on mac, also change the other .py files
#!/usr/local/bin/python3

__author__ = "Jeronimo Barraco-Marmol"
__copyright__ = "Copyright (C) 2021 Jeronimo Barraco-Marmol"
__license__ = "LGPL V3"
__version__ = "1.01"

# ------------------ Here be dragons (that means don't touch, unless you're contributing the changes that is)
import os
import rpyc
import subprocess
import sys
import time
import traceback

# locals
import utils
import config

REAL_PATH = os.path.realpath(__file__)
FNAME = os.path.basename(REAL_PATH)
WORK_PATH = os.path.dirname(REAL_PATH)
# don't go lower than 2, otherwise with many max concurrent tasks in xcode you'll get 20 requests per second,
# will bloat on the server
config.COOLDOWN = max(config.COOLDOWN, 2)
# has this format because this is for rpyc
CON_CONF = {
	"sync_request_timeout": None if config.TIMEOUT < 1 else config.TIMEOUT
}

def cmdInList(arg, cmd_list):
	if not cmd_list: return False
	for cmd in cmd_list:
		if not cmd: continue #important to not count '' as '*' as endswith will return True
		if cmd == '*': return True
		if arg.endswith(cmd): return True
	return False

def shouldRunDirectly(args):
	if not config.WORKERS: return True
	if cmdInList(args[0], config.RUN_DIRECTLY): return True

	# run local files directly (mac)
	for a in args[1:]:
		if a.startswith('@/private') or a.startswith('/private'): return True

	return False

def shouldUseShell(args):
	for a in args[1:]:
		if a in ('&&', ';', '||'): return True
	return cmdInList(args[0], config.USE_SHELL)

def shouldUseEnv(args):
	return cmdInList(args[0], config.USE_ENV)

def shouldUseComm(args):
	return cmdInList(args[0], config.USE_COMM)

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
	global conns, CON_CONF
	c = None
	try:
		c = conns.get(address, None)
		if not c: # create a new connection if it doesn't exist
			host, port = address.rsplit(':', 1)
			c = rpyc.connect(host, int(port), config=CON_CONF)
			conns[address] = c
		# Test the connection AND the worker. rpyc raises an exception when trying to execute, not when connecting (at least sometimes).
		# Note it does this everytime. Just because it was working before doesn't means it still does.
		if not c.root.ping(): return None
	except ConnectionRefusedError as e:
		return None  # try next worker
	except Exception as e:
		if config.DEBUG:
			print("Connection to worker failed:")
			print(traceback.format_exc())
		return None  # try next worker
	return c

def write(out=b'', err=b''):
	if not sys.stdout.closed and out:
		sys.stdout.buffer.write(out)
		sys.stdout.flush()# testing
	if not sys.stderr.closed and err:
		sys.stderr.buffer.write(err)
		sys.stderr.flush()# testing
	#if out: sys.stdout.write(out.decode('utf-8'))
	#if err: sys.stderr.write(err.decode('utf-8'))

def doCommWork(c):
	"""Does the work using the passed worker, and tries to pass the stdin into it"""

	read = utils.readPoll(sys.stdin, 0.001, None) # not waiting since the worker will... probably
	while True:
		#in_data = utils.readIfAny(sys.stdin, 0.001, None)
		in_data = read()
		if in_data is not None:
			if not in_data: # stdin will return b'' on EOF.
				#	in_data = b'\x1A\r\n' # try sending ctrl z # not working atm https://bytes.com/topic/python/answers/696448-how-write-ctrl-z-serial-port
				c.root.stop(False) # stop but don't kill. (will wait for the subprocess to stop)

		res = c.root.comm(in_data=in_data)
		if res is None: break

		write(*res)
		#out, err = res
		# if out: sys.stdout.write(out.decode('utf-8'))
		# if err: sys.stderr.write(err.decode('utf-8'))

def doWork(c):
	"""Does the work using the passed worker, without passing stdin"""
	while True: # less fancy than iter, probably more fasterest
		res = c.root.comm()
		if res is None: break

		write(*res)
		#out, err = res
		#if out: sys.stdout.write(out.decode('utf-8'))
		#if err: sys.stderr.write(err.decode('utf-8'))

def tryRunInAWorker(c, args, cwd=None, env=None, shell=False, comm=False):
	global exitTries
	wretc = -1
	try:
		executed = c.root.tryRun(args, cwd, env, shell)
		if not executed: return False, -1

		if comm: doCommWork(c)
		else: doWork(c)

		wretc = c.root.getExitCode()
		return True, wretc
	except KeyboardInterrupt as e:
		# Xcode loooves to send this :(
		rets = traceback.format_exc()
		if config.DEBUG: print(rets)

		exitTries += 1
		if exitTries > 5:
			raise e
	except rpyc.AsyncResultTimeout as e:
		rets = traceback.format_exc()
		if config.DEBUG: print(rets)
		raise e
	except EOFError as e:
		rets = traceback.format_exc()
		if config.DEBUG: print(rets)
		raise e
	except Exception as e:
		rets = traceback.format_exc()
		if config.DEBUG: print(rets)
		# hotfix, why?, xcode keeps sending random interrupts. it will still timeout on too many retries anyway (should this be a raise)
		# return FAILURE
		wretc = 8
	return False, wretc

def runInWorkers(args, cwd=None, env=None, shell=False, comm=False):
	"""runs a command on the best worker possible."""
	# select the workers to use based on the config
	cur_workers = config.WORKERS
	worker_is = config.clientsToUse(args)
	if worker_is:
		cur_workers = [config.WORKERS[i] for i in worker_is]

	# iterate the workers. and try to get 1 to run the command
	for w in cur_workers:
		c = getConnection(w)
		if not c: continue

		# got a client, do stuff
		executed, wretc = tryRunInAWorker(c, args, cwd, env, shell, comm)
		if executed:
			return True, wretc

	return False, -1 # could not execute

def runDirect(args, cwd=None, env=None, shell=False):
	"""runs a command directly as subprocess bypassing the workers"""
	# run direct inherits the stdin. so that it works a bit better in those scenarios.
	# "if the default settings of None, no redirection will occur; the child’s file handles will be inherited from the parent. "
	# https://docs.python.org/3/library/subprocess.html  # subprocess.Popen
	# https://stackoverflow.com/a/53292311/260242
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
	global exitTries, curTime

	fixSelf(args)
	config.doFixes(args)

	run_direct = shouldRunDirectly(args) or config.shouldRunDirect(args)
	use_shell = shouldUseShell(args) or config.shouldUseShell(args)
	use_comm = shouldUseComm(args) or config.shouldUseComm(args)
	use_env = shouldUseEnv(args) or config.shouldUseEnv(args)
	env = None if not use_env else os.environ.copy()
	#if DEBUG:
	#    open(os.path.join(WORK_PATH, 'clog'), 'a').write(
	#        "fname%s\ncommand %s\ncwd %s\nenv %s\nlocal %s\nshell %s\n" % (FNAME, args, cwd, env, run_direct, use_shell)
	#    )

	if run_direct:
		return runDirect(args, cwd, env, use_shell)

	while True:
		executed, retc = runInWorkers(args, cwd, env, use_shell, use_comm)
		if executed:
			if config.SLEEP: time.sleep(config.SLEEP)
			return retc

		time.sleep(config.COOLDOWN)
		if config.TIMEOUT > 0:
			curTime += config.COOLDOWN
			if curTime >= config.TIMEOUT:
				print("CLIENT TIMEOUT!")
				return 9


if __name__ == "__main__":
	conns = {}
	curTime = 0
	exitTries = 0

	retc = run(sys.argv[:], os.getcwd())
	exit(retc)
