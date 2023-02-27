#!/usr/bin/python3 -u
# coding: utf-8
#!/usr/local/bin/python3

__author__ = "Jeronimo Barraco-Marmol"
__copyright__ = "Copyright (C) 2021 Jeronimo Barraco-Marmol"
__license__ = "LGPL V3"
__version__ = "1.00"

import select
import os
import threading
import queue

# https://stackoverflow.com/a/58071295/260242
import platform
PLATFORM =  platform.system().lower()
IS_LINUX =  PLATFORM == "linux"
IS_WINDOWS = PLATFORM == "windows"
IS_MAC = PLATFORM == "darwin"

def readLen(p):
	# doesn't really work on linux, use readPoll.
	#inspired by https://stackoverflow.com/a/51604225/260242
	# works on mac, probably doesn't on windows, but you shouldn't be using it anyway
	# if windows: return 1 #would be 'ok'
	if IS_MAC: return os.fstat(p.fileno()).st_size
	#if IS_WINDOWS || IS_LINUX: return 1
	return 1 # "she'll be right" (this might lock if there's nothing to read :( )

def readIfAny(p, timeout=1, default=None):
	# doesn't really work on linux, use readPoll for that
	# left here in case mac breaks. at which point it would be better to have one function that uses the correct method depending on the platform
	if select.select([p], [], [], timeout)[0]:
		size = readLen(p)
		if size:
			return p.read(size)
	return default

# https://stackoverflow.com/a/10759061/260242
# timeout in seconds
def readPoll(p, timeout=1, default=None):
	poller = select.poll()
	poller.register(p, select.POLLIN)
	# read bytes and not strs
	dev = getattr(p, "buffer", p) # conveniently stdin.buffer and stdin and stdout has a read function
	timeout_ms = timeout *1000

	def read(size=None): # i don't like to do this. but i just did.
		ret = poller.poll(timeout_ms)
		if not ret: return default
		if ret[0][1] in (select.POLLERR, select.POLLHUP) :
			return default # left here for debug
		if ret[0][1] == select.POLLIN:
			return dev.read(size)

		return default

	return read

class ReadThread(threading.Thread):
	buff = None
	def __init__(self, q, dev):
		super().__init__()
		self.q = q
		self.dev = dev
		self.read = readPoll(dev, 1, None)# notice none as default. and 1 as timeout.
		self.stopRequest = threading.Event()
		self.atEof = False

	def run(self):
		if self.stopRequest.is_set():
			print("Tried to re-run a reader thread. that won't work")
			return

		while not self.stopRequest.is_set():
			r = self.read(1) # read 1 byte. readPoll will wait at most 1 sec. otherwise we're likely to have a deadlock
			if r == b'':
				self.atEof = True # don´t reset it

			something = r is not None
			if not self.atEof and something:
				self.q.put(r, True, None) # if full block

	def join (self, timeout=None):
		self.stopRequest.set()
		super().join(timeout)
		self.__clean__()

	def __clean__(self):
		del self.q
		del self.dev
		del self.read

class Reader:
	def __init__(self, dev, size = 1024):
		self.queue = queue.Queue(size) # deques with maxlength will DISCARD elements https://docs.python.org/3/library/collections.html#collections.deque
		self.thread = ReadThread(self.queue, dev)
		self.thread.start()
		pass

	def read(self):
		out = b''
		while True:
			try:
				out += self.queue.get(False) # don´t block
			except queue.Empty:
				break
		return out

	def isEof(self):
		return self.thread.atEof

	def stop(self):
		self.thread.join(3)

# https://en.wikipedia.org/wiki/ANSI_escape_code#Fe_Escape_sequences https://stackoverflow.com/a/37340245/260242
class Colors:
	RESET = '\033[m'

	T_BLACK = '\033[30m'
	T_RED = '\033[31m'
	T_GREEN = '\033[32m'
	T_YELLOW = '\033[33m'
	T_BLUE = '\033[34m'
	T_PURPLE = '\033[35m'
	T_CYAN = '\033[36m'
	T_WHITE = '\033[37m'

	T_B_BLACK = '\033[90m'
	T_B_RED = '\033[91m'
	T_B_GREEN = '\033[92m'
	T_B_YELLOW = '\033[93m'
	T_B_BLUE = '\033[94m'
	T_B_PURPLE = '\033[95m'
	T_B_CYAN = '\033[96m'
	T_B_WHITE = '\033[97m'

	B_BLACK = '\033[40m'
	B_RED = '\033[41m'
	B_GREEN = '\033[42m'
	B_YELLOW = '\033[43m'
	B_BLUE = '\033[44m'
	B_PURPLE = '\033[45m'
	B_CYAN = '\033[46m'
	B_WHITE = '\033[47m'

	B_B_BLACK = '\033[100m'
	B_B_RED = '\033[101m'
	B_B_GREEN = '\033[102m'
	B_B_YELLOW = '\033[103m'
	B_B_BLUE = '\033[104m'
	B_B_PURPLE = '\033[105m'
	B_B_CYAN = '\033[106m'
	B_B_WHITE = '\033[107m'

	E_NONE = '\033[0m'
	E_BOLD = '\033[1m'
	E_UNDERLINE = '\033[2m'
	E_NEG1 = '\033[3m'
	E_NEG2 = '\033[4m'

	# 'REVERSE' and similar modes need be reset explicitly
	REVERSE = "\033[;7m"
	BOLD = "\033[;1m"
