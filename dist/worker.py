#!/usr/bin/python3 -u
# coding: utf-8
#!/usr/local/bin/python3

__author__ = "Jeronimo Barraco-Marmol"
__copyright__ = "Copyright (C) 2021 Jeronimo Barraco-Marmol"
__license__ = "LGPL V3"
__version__ = "1.01"

# built-in
import datetime
import sys
import json
import subprocess
import threading
import traceback
import collections

# 3rd party
import rpyc

# local
import utils

# Globals
CONF = {}
remapDirs = {}
remapCmds = {}
numTasks = 1
LOCK = None
DEBUG = True
USE_COLORS = False
TIMEOUT = 1
# time to wait for stdout on worker. a bit of an optimization, too low and can be slowed by network. too high and might wait for too long (in case there's coms)
TIMEOUT_READ = 1

COLORS_T = (
	utils.Colors.T_RED, utils.Colors.T_GREEN, utils.Colors.T_YELLOW, utils.Colors.T_BLUE, utils.Colors.T_PURPLE, utils.Colors.T_CYAN, utils.Colors.T_WHITE,
	utils.Colors.T_B_RED, utils.Colors.T_B_GREEN, utils.Colors.T_B_YELLOW, utils.Colors.T_B_BLUE, utils.Colors.T_B_PURPLE, utils.Colors.T_B_CYAN, utils.Colors.T_B_WHITE,
)
COLORS_B = (
	utils.Colors.B_RED, utils.Colors.B_GREEN, utils.Colors.B_YELLOW, utils.Colors.B_BLUE, utils.Colors.B_PURPLE, utils.Colors.B_CYAN, utils.Colors.B_WHITE,
	utils.Colors.B_B_RED, utils.Colors.B_B_GREEN, utils.Colors.B_B_YELLOW, utils.Colors.B_B_BLUE, utils.Colors.B_B_PURPLE, utils.Colors.B_B_CYAN, utils.Colors.B_B_WHITE,
)
COLORS = COLORS_T
COLOR_IDX = collections.deque((i for i in range(len(COLORS))))

# Code

class WorkerService(rpyc.Service):
	proc = None
	rc = 0
	stop_out = b''
	stop_err = b''
	# functions to read stds polling
	readStdOut = None
	readStdErr = None

	locked = False
	timer = None
	start_time = None
	stop_lock = None
	color_i = -1

	T_START = '>'
	T_STOP = '-'
	T_ERROR = 'X'
	T_TIME_OUT = '!'
	T_FORCE_STOP = '='

	def on_connect(self, conn):
		# code that runs when a connection is created
		# (to init the service, if needed)
		pass

	def on_disconnect(self, conn):
		# code that runs after the connection has already closed
		# (to finalize the service, if needed)
		self.stop(True) # make sure to stop the process, can happen on certain conditions

	def __init__(self):
		self.stop_lock = threading.Semaphore(1)
		self.resetReaders()

	def __emptyRead(self):
		# an empty read function to have set while the process is not running
		return b'' # if nothing avail return b'' or won't be able to concatenate

	def resetReaders(self):
		# ensure there are no problems
		self.readStdErr = self.__emptyRead
		self.readStdOut = self.__emptyRead

	def write(self, msg):
		global COLORS
		if self.color_i>-1:
			msg = COLORS[self.color_i] + msg + utils.Colors.RESET
		sys.stdout.write(msg)
		sys.stdout.flush()

	def stop(self, kill=True):
		global LOCK, COLOR_IDX
		# once stopped no need to stop again (hopefully), avoid problems when re-entering
		# this function can be called many times, even as a result of this functions
		if not self.stop_lock.acquire(False):
			return False # already stopping

		# first check for the timer. we are not really reentrant
		if self.timer:
			self.timer.cancel()
			self.timer = None

		# this func is called more than once sometimes, beware
		if self.proc:
			# these lines in this order are necessary according to docs
			if kill:
				# We need to avoid this when doing comms mode. since otherwise the process won't read the input and won't write the output.
				# dont: https://stackoverflow.com/a/21143100/260242 closing stdin will break communicate. which is actually really important to have here.
				# kill is optional to allow for ... killing commands
				self.proc.kill()
			# communicate will wait for the process to end (and closes stdin/out)
			# stderr pipes to stdout, also communicate sets the return code
			# very important to receive the rest of the out and err
			o, e = self.proc.communicate()
			self.stop_out += o
			self.stop_err += e

			self.rc = self.proc.returncode
			if DEBUG:
				delta = datetime.datetime.now() - self.start_time
				print('stop: %i > %s' % (self.rc, delta))
			else:
				self.write(WorkerService.T_STOP)

		self.proc = None
		self.resetReaders()
		# return the color
		if self.color_i >= 0:
			COLOR_IDX.append(self.color_i) # use appendleft if you want to reuse a color as soon as it finishes
			self.color_i = -1

		# this func is called more than once sometimes, beware
		if self.locked: # might be unnecessary since we have a thread lock, but better be safe for now
			self.locked = False
			LOCK.release()

		self.stop_lock.release() # in case someone will try to re-run on the same connection
		return True

	def onTimeout(self):
		if DEBUG:
			print("TIMEOUT!")
		else:
			self.write(WorkerService.T_TIME_OUT)
		self.stop(True)
		self.stop_err += b"\nOUTATIME!\n"

	def run(self, cmd, cwd=None, env=None, shell=False):
		global TIMEOUT, DEBUG, USE_COLORS
		if self.proc:
			if DEBUG:
				print('Trying to run a process when im already running!')
			else:
				self.write(WorkerService.T_FORCE_STOP)
			self.stop(True) #stopping just in case, old process might have been forsaken
			return False

		self.stop_out = b""
		self.stop_err = b""
		self.rc = 0
		self.proc = None

		if USE_COLORS:
			try:
				self.color_i = COLOR_IDX.popleft()
			except:
				pass

		# a bit deprecated, to be able to run things locally.
		for k, v in remapCmds.items():
			c = cmd[0]
			if c.endswith(k):
				cmd[0] = v.join(c.rsplit(k, 1)) # replace only last occurrence

		# a bit deprecated,
		for k, v in remapDirs.items():
			# also remap cwd
			if cwd.startswith(k):
				cwd = cwd.replace(k, v, 1)
			# remap dirs in command
			for i, c in enumerate(cmd):
				if c.startswith(k):
					c = c.replace(k, v, 1)
					cmd[i] = c

		# to avoid accidentally setting an empty environ
		if not env: env = None

		self.start_time = datetime.datetime.now()
		if DEBUG:
			print("")
			print('start', self.start_time)
			print("cmd", str(cmd))
			print("cwd", str(cwd))
			print('env', str(env))
			print('shell', str(shell))
		else:
			self.write(WorkerService.T_START)

		if TIMEOUT > 0:
			self.timer = threading.Timer(TIMEOUT, self.onTimeout)
			self.timer.start()

		self.rc = 0
		try:
			self.proc = subprocess.Popen(
				cmd, cwd=cwd, stderr=subprocess.PIPE, stdout=subprocess.PIPE, stdin=subprocess.PIPE, env=env, shell=shell,
				# encoding='utf-8', bufsize=1, universal_newlines=True #bufsize is only supported in text mode (encoding)
				#bufsize=1 forces line buffering. we don't want that
			)
			# create a reader
			self.readStdOut = utils.readPoll(self.proc.stdout, TIMEOUT_READ, b'')
			self.readStdErr = utils.readPoll(self.proc.stderr, 0.00001, b'') # no need to wait for this one as we wait for stdout
		except Exception as e:
			self.stop_err += traceback.format_exc().encode('utf-8')
			if DEBUG:
				print("\nWorker General Exception!\n")
				print(self.stop_err)
			else:
				self.write(WorkerService.T_ERROR)

			self.stop(True)
			# self.rc = 6 # stop will set rc, but we might want to make this explicit
		# still return True after this, so the client knows we tried to run (but failed)
		# otherwise it will try again
		return True

	def exposed_tryRun(self, cmd, cwd=None, env=None, shell=False):
		global LOCK
		if not LOCK.acquire(False):
			self.stop_err = b"\ni'm busy\n"
			return False

		self.locked = True
		self.run(cmd, cwd, env, shell)
		return True

	def exposed_comm(self, in_data=None):
		stdout = b''
		stderr = b''

		# handle finished process
		if not self.proc:
			# avoid loosing output
			stderr += self.stop_err
			stdout += self.stop_out
			self.stop_err = b''
			self.stop_out = b''
			if stderr or stdout:
				# if there was some output, we need to return that. and we should get a new call to comm.
				return stdout, stderr

			return None

		try:
			# communicate will wait for the process to end (in this case with a timeout)
			if self.proc.poll() is None: # Check if child process has terminated. Set and return returncode attribute. Otherwise, returns None.
				if in_data:
					self.proc.stdin.write(in_data)
			# stdout, stderr = self.proc.communicate(input=in_data, timeout=TIMEOUT_READ) # this guy does not return ANY data until the proc finishes >:(

			#stdout += utils.readIfAny(self.proc.stdout, TIMEOUT_READ, b'')
			stdout += self.readStdOut()
			#stderr += utils.readIfAny(self.proc.stderr, 0.00001, b'')
			stderr += self.readStdErr()
		except subprocess.TimeoutExpired:
			pass

		# removed, timer will kill the process already
		# handle dead process
		# check self.proc it might have been killed by the timer
		#if self.proc and (self.proc.returncode is not None): # notice this is NOT None
		#	self.stop() # will fill stop_* variables and do proper cleanup
			# to avoid loosing output, we continue as normal, and check stopped on next comm

		return stdout, stderr

	def isRunning(self):
		return self.proc and (self.proc.returncode is None)

	def exposed_stop(self, kill=True):
		return self.stop(kill)

	def exposed_getExitCode(self):
		return self.rc

	def exposed_ping(self):
		"""Test the connection"""
		return True

	def exposed_isRunning(self):
		return self.isRunning()

def loadConf(fname):
	global CONF, remapDirs, remapCmds, numTasks, LOCK, DEBUG, TIMEOUT, TIMEOUT_READ, USE_COLORS, COLORS, COLOR_IDX, COLORS_B

	CONF = json.load(open(fname, 'r'))
	remapDirs = CONF.get('remapDirs', {})
	remapCmds = CONF.get("remapCmds", {})
	numTasks = CONF.get("numTasks", 1)
	LOCK = threading.Semaphore(int(numTasks))
	DEBUG = CONF.get('debug', False)
	USE_COLORS = CONF.get('colors', False)
	TIMEOUT = CONF.get('timeout', 0)
	TIMEOUT_READ = CONF.get('timeoutRead', 1)

	icons = CONF.get('icons', ())
	if icons and len(icons)>4:
		WorkerService.T_START = icons[0]
		WorkerService.T_STOP = icons[1]
		WorkerService.T_ERROR = icons[2]
		WorkerService.T_TIME_OUT = icons[3]
		WorkerService.T_FORCE_STOP = icons[4]
	if CONF.get('colorsBg', False):
		COLORS = COLORS_B
		COLOR_IDX = collections.deque((i for i in range(len(COLORS))))

	return

def main():
	global TIMEOUT, numTasks, CONF, TIMEOUT_READ
	if len(sys.argv) < 2:
		print("Please pass the config file as argument.")
		exit(1)

	loadConf(sys.argv[1])

	port = CONF['port']
	host = CONF['host']
	print("Starting worker. Host=%s:%s Tasks=%s Timeout=%s TimeoutRead=%s\nRemapCmds=%s\nRemapDirs=%s"
		  % (host, port, numTasks, TIMEOUT, TIMEOUT_READ, repr(remapCmds), repr(remapDirs)))
	from rpyc.utils.server import ThreadedServer
	t = ThreadedServer(WorkerService, hostname=host, port=port, protocol_config={})
	t.start()

if __name__ == '__main__':
	main()
