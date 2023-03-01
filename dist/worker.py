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
import time
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
# global locks to limit the number of tasks.
LOCK = None
DEBUG = True
USE_COLORS = False
TIMEOUT = 1
# time to wait for stdout on worker. a bit of an optimization, too low and can slow the network. too high and might wait for too long (in case there's coms)
TIMEOUT_READ = 1
READ_SIZE = 1024
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
	#readStdOut = None
	#readStdErr = None
	# std readers
	std_out_r = None
	std_err_r = None

	# whether we are locked running (e.g. can't start a new process). this is safe to read. don't write it.
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

	#def __emptyRead(self):
	#	# an empty read function to have set while the process is not running
	#	return b'' # if nothing avail return b'' or won't be able to concatenate

	def resetReaders(self):
		# ensure there are no problems
		#self.readStdErr = self.__emptyRead
		#self.readStdOut = self.__emptyRead
		self.std_out_r = self.std_err_r = None

	def write(self, msg):
		global COLORS
		if self.color_i>-1:
			msg = COLORS[self.color_i] + msg + utils.Colors.RESET
		sys.stdout.write(msg)
		sys.stdout.flush()

	def unlock(self):
		# this func is called more than once sometimes, beware
		if self.locked: # might be unnecessary since we have a thread lock, but better be safe for now
			self.locked = False
			self.stop_lock.release()  # in case someone will try to re-run on the same connection
			LOCK.release()
			return True
		return False

	def stop(self, kill=True):
		global LOCK, COLOR_IDX

		if not self.locked:
			return False # if we're not locked running. nothing to stop. avoid acquiring the stop_lock and not releasing it. (this tends to happen when the client spams stop)
		# once stopped no need to stop again (hopefully), avoid problems when re-entering
		# this function can be called many times, even as a result of this function
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

			# ensure we don't cause issues with communicate
			self.std_out_r.stop(1)
			self.std_err_r.stop(1)
			# read the remaining buffer
			self.stop_out += self.std_out_r.read()
			self.stop_err += self.std_err_r.read()
			# communicate will wait for the process to end (and closes stdin/out)
			# stderr pipes to stdout, also communicate sets the return code
			# very important to receive the rest of the out and err
			o, e = self.proc.communicate()
			# do after communicate. but add before that.
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

		return True

	def onTimeout(self):
		if DEBUG:
			print("TIMEOUT!")
		else:
			self.write(WorkerService.T_TIME_OUT)
		self.stop(True)
		self.stop_err += b"\nOUTATIME!\n"

	def run(self, cmd, cwd=None, env=None, shell=False):
		global TIMEOUT, DEBUG, USE_COLORS, READ_SIZE

		if self.locked:
			if DEBUG:
				print('Trying to run a process when im already running! Can\'t do')
			else:
				self.write(WorkerService.T_FORCE_STOP)
			# self.stop(True) #stopping just in case, old process might have been forsaken
			# not stopping. we can't continue. (actually i might need to think about this)
			return False
		self.locked = True # this might be a problem if we call this twice from different threads on the same instance. "Should not happen"(TM) "She'll be right"

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
			# create readers
			self.std_out_r = utils.Reader(self.proc.stdout, READ_SIZE)
			self.std_err_r = utils.Reader(self.proc.stderr, READ_SIZE)
			# create a reader
			#self.readStdOut = utils.readPoll(self.proc.stdout, TIMEOUT_READ, b'')
			# no need to wait for this one as we wait for stdout
			#self.readStdErr = utils.readPoll(self.proc.stderr, 0.00001, b'')
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

	def isRunning(self):
		return self.locked and self.proc and (self.proc.returncode is None)

	def exposed_tryRun(self, cmd, cwd=None, env=None, shell=False):
		global LOCK
		if not LOCK.acquire(False):
			self.stop_err = b"\nworker is full...\n"
			return False

		return self.run(cmd, cwd, env, shell)

	def exposed_comm(self, in_data=None):
		stdout = b''
		stderr = b''

		# handle finished processes (important since it might have finished by itself)
		if not self.proc:
			# avoid loosing output. we need to do it in this order. since when terminating we call stop
			stderr += self.stop_err
			stdout += self.stop_out
			self.stop_err = b''
			self.stop_out = b''
			if stderr or stdout:
				# if there was some output, we need to return that. and we should get a new call to comm.
				return stdout, stderr
			else:
				self.unlock() # only now fully unlock. since we truly finished.
				# tell the client the process has finished. (important)
				return None

		ret = self.proc.poll() # check if dead

		# dead. handle properly. stop this charade. actually we will wait for a call to comms later (the one that returns none above)
		if ret is not None:
			# stop() will fill stop_* variables and do proper cleanup. it doesn't matter if we kill it. set to false to test. since it should be already dead.
			self.stop(False) # test if false breaks anything. or true does?
			stdout += self.stop_out # this actually speed things up (avoids one extra call to coms)
			stderr += self.stop_err
			self.stop_err = b''
			self.stop_out = b''
			# to avoid loosing output, we continue as normal, and check again on next comm
			return stderr, stdout

		# send data if possible
		if in_data and not self.proc.stdin.closed:
			try:
				self.proc.stdin.write(in_data)
			except BrokenPipeError:
				pass # sucky i know. happens rarely on useComs when the subprocess is too fast. the rest of the code will handle this properly. leaving this as this to allow for debugging if needed.

		#try:
			# communicate will wait for the process to end (in this case with a timeout)
			# NO. BAD. DON'T USE. EVER. stdout, stderr = self.proc.communicate(input=in_data, timeout=TIMEOUT_READ) # this guy does not return ANY data until the proc finishes >:(
		#except subprocess.TimeoutExpired:
			#pass

		if not (self.std_out_r.hasData() or self.std_err_r.hasData()):
			# only wait if we haven't read anything. manually wait since threaded polling does not wait. also wait *before* reading to ensure buffer is as full as possible
			time.sleep(TIMEOUT_READ) # a bit inefficient since we will wait the whole timeout but...

		stdout += self.std_out_r.read()
		#if not self.proc.stdout.closed:
			#stdout += utils.readIfAny(self.proc.stdout, TIMEOUT_READ, b'')
			#stdout += self.readStdOut(1)
		stderr += self.std_err_r.read()
		#if not self.proc.stderr.closed:
			#stderr += utils.readIfAny(self.proc.stderr, 0.00001, b'')
			#stderr += self.readStdErr(1)# size is important, or it might hang on some situations (ffmpeg)

		return stdout, stderr

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
	global CONF, remapDirs, remapCmds, numTasks, LOCK, DEBUG, TIMEOUT, TIMEOUT_READ, USE_COLORS, COLORS, COLOR_IDX, COLORS_B, READ_SIZE

	CONF = json.load(open(fname, 'r'))
	remapDirs = CONF.get('remapDirs', {})
	remapCmds = CONF.get("remapCmds", {})
	numTasks = CONF.get("numTasks", 1)
	LOCK = threading.Semaphore(int(numTasks))
	DEBUG = CONF.get('debug', False)
	USE_COLORS = CONF.get('colors', False)
	TIMEOUT = CONF.get('timeout', 0)
	TIMEOUT_READ = CONF.get('timeoutRead', 1)
	READ_SIZE = CONF.get('readSize', READ_SIZE)

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
	global TIMEOUT, numTasks, CONF, TIMEOUT_READ, READ_SIZE
	if len(sys.argv) < 2:
		print("Please pass the config file as argument.")
		exit(1)

	loadConf(sys.argv[1])

	port = CONF['port']
	host = CONF['host']
	print("Starting worker. Host=%s:%s Tasks=%s Timeout=%s TimeoutRead=%s ReadSize=%s \nRemapCmds=%s\nRemapDirs=%s"
		  % (host, port, numTasks, TIMEOUT, TIMEOUT_READ, READ_SIZE, repr(remapCmds), repr(remapDirs)))
	from rpyc.utils.server import ThreadedServer
	t = ThreadedServer(WorkerService, hostname=host, port=port, protocol_config={})
	t.start()

if __name__ == '__main__':
	main()
