#!/usr/local/bin/python3
# coding: utf-8

__author__ = "Jeronimo Barraco-Marmol"
__copyright__ = "Copyright (C) 2021 Jeronimo Barraco-Marmol"
__license__ = "LGPL V3"
__version__ = "0.21"

import datetime
import sys
import json
import subprocess
import threading
import traceback
import rpyc

if len(sys.argv) < 2:
	print("please pass the config file as argument.")
	exit(1)

CONF = json.load(open(sys.argv[1], 'r'))
remapDirs = CONF.get('remapDirs', {})
remapFiles = CONF.get("remapFiles", {})
numTasks = CONF.get("numTasks", 1)
LOCK = threading.Semaphore(int(numTasks))
DEBUG = CONF.get('debug', False)
TIMEOUT = CONF.get('timeout', 0)
BUFF_SECS = CONF.get('buff_secs', 0.5)

class WorkerService(rpyc.Service):
	proc = None
	rc = 0
	stop_out = b''
	stop_err = b''
	locked = False
	timer = None
	timeout = False
	stopping = False
	start_time = None
	def on_connect(self, conn):
		# code that runs when a connection is created
		# (to init the service, if needed)
		pass

	def on_disconnect(self, conn):
		# code that runs after the connection has already closed
		# (to finalize the service, if needed)
		self.stop() # make sure to stop the process, can happen on certain conditions

	def stop(self):
		global LOCK
		# once stopped no need to stop again (hopefully), avoid problems when re-entering
		# this function can be called many times, even as a result of this functions
		if self.stopping: return
		self.stopping = True

		# first check for the timer. we are not really reentrant
		if self.timer:
			self.timer.cancel()
			self.timer = None

		# this func is called more than once sometimes, beware
		if self.proc:
			try:
				# communicate will wait for the process to end (in this case with a timeout)
				o, e = self.proc.communicate(timeout=0.5)
				self.stop_out += o
				self.stop_err += e
			except subprocess.TimeoutExpired:
				# this try, and these lines in this order are necessary according to docs
				self.proc.kill()
				# communicate will wait for the process to end
				# stderr pipes to stdout, also communicate sets the return code
				o, e = self.proc.communicate()
				self.stop_out += o
				self.stop_err += e

			self.rc = self.proc.returncode
			if DEBUG:
				delta = datetime.datetime.now() - self.start_time
				print('stop: %i > %s' % (self.rc, delta))
			else:
				sys.stdout.write(".")
				sys.stdout.flush()

		self.proc = None

		# this func is called more than once sometimes, beware
		if self.locked:
			self.locked = False
			LOCK.release()

		return

	def onTimeout(self):
		if DEBUG:
			print("TIMEOUT!")
		else:
			sys.stdout.write('|')
			sys.stdout.flush()
		# avoid thread weirdness, loosing output, and let the process finish if it happens to finish by next read
		# comm will check and kill
		self.timeout = True

	def run(self, cmd, cwd=None, env=None, shell=False):
		global TIMEOUT, DEBUG
		self.stop_out = b""
		self.stop_err = b""
		self.rc = 0
		self.proc = None
		self.stopping = False
		# a bit deprecated, to be able to run things locally.
		for k, v in remapFiles.items():
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
			sys.stdout.write("-")
			sys.stdout.flush()

		if TIMEOUT > 0:
			self.timer = threading.Timer(TIMEOUT, self.onTimeout)
			self.timer.start()

		self.rc = 0
		try:
			self.proc = subprocess.Popen(
				cmd, cwd=cwd, stderr=subprocess.PIPE, stdout=subprocess.PIPE, stdin=subprocess.PIPE, env=env, shell=shell,
				#cmd, cwd=cwd, stderr=subprocess.STDOUT, stdout=subprocess.PIPE, env=env, shell=shell,
				# encoding='utf-8', bufsize=1,universal_newlines=True #bufsize is only supported in text mode (encoding)
			)
		except Exception as e:
			self.stop_err += traceback.format_exc().encode('utf-8')
			if DEBUG:
				print("\nWorker General Exception!\n")
				print(self.stop_err)
			else:
				sys.stdout.write('X')
				sys.stdout.flush()

			self.stop()
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
			return None

		try:
			# communicate will wait for the process to end (in this case with a timeout)
			stdout, stderr = self.proc.communicate(input=in_data, timeout=BUFF_SECS)
		except subprocess.TimeoutExpired:
			pass

		# handle timeout and dead process
		if self.timeout or (not self.proc) or (self.proc.returncode is not None):
			self.stop() # will fill stop_*
			stderr += self.stop_err
			stdout += self.stop_out
			self.stop_err = b''
			self.stop_out = b''
			if self.timeout:
				stderr += b"\nOUTATIME!\n"

		return stdout, stderr

	def exposed_getExitCode(self):
		return self.rc

	def exposed_ping(self):
		"""Test the connection"""
		return True


def main():
	global TIMEOUT, numTasks
	port = CONF['port']
	host = CONF['host']
	print("Starting worker. Host=%s:%s Tasks=%s Timeout=%s" % (host, port, numTasks, TIMEOUT))
	from rpyc.utils.server import ThreadedServer
	t = ThreadedServer(WorkerService, hostname=host, port=port, protocol_config={})
	t.start()

if __name__ == '__main__':
	main()
