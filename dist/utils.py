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

if IS_WINDOWS:
	# used for the windows poll
	import win32event, win32file, pywintypes

def readLen(p):
	# returns the len to read on a device
	# doesn't really work (on linux). left for testing.
	#inspired by https://stackoverflow.com/a/51604225/260242
	# works on mac, probably doesn't on windows, but you shouldn't be using it anyway
	# if windows: return 1 #would be 'ok'
	if IS_MAC: return os.fstat(p.fileno()).st_size
	#if IS_WINDOWS || IS_LINUX: return 1
	return 1 # "she'll be right" (this might lock if there's nothing to read :( )

def _stdCanReadWindows(p, timeout=1):
	# https://stackoverflow.com/a/71860247/260242
	handle = pywintypes.HANDLE(p.fileno())
	try:
		# without this the wait might return despite there not being any input
		win32file.FlushFileBuffers(handle)
	except pywintypes.error:
		# this sometimes fails, but we don't mind
		pass
	ret = win32event.WaitForSingleObject(handle, int(timeout * 1000))
	hasRead = ret == win32event.WAIT_OBJECT_0
	return hasRead

def _stdCanReadPosix(p, timeout=1):
	# https://stackoverflow.com/a/71860247/260242
	# note this is not very trustworthy
	rlist = select.select([p], [], [], timeout)[0]
	return bool(rlist)

stdCanRead = _stdCanReadWindows if IS_WINDOWS else _stdCanReadPosix

def readIfAny(p, timeout=1, default=None):
	# doesn't really work on linux.
	# left here in case mac breaks. at which point it would be better to have one function that uses the correct method depending on the platform
	if stdCanRead(p, timeout):
		size = readLen(p)
		if size:
			return p.read(size)
	return default

if IS_WINDOWS:
	# stub WindowsPoll class to cover that on windows there is no one
	class _WindowsPoll: # fake it till you make it (TM)
		def poll(self, timeout):
			if stdCanRead(self.p, timeout):
				return [self.p, select.POLLIN]
			if self.p.closed:
				return [self.p, select.POLLHUP]
			return []

		def register(self, p, unused):
			self.p = p

	select.poll = _WindowsPoll
	select.POLLIN = 1
	select.POLLPRI = 2
	select.POLLERR = 8
	select.POLLHUP = 16
	select.POLLNVAL = 32
	select.POLLRDHUP = 8192

def readPoll(p, timeout=1, default=None):
	"""read a device by polling it. works ok on linux and has a stub for windows, probably works on mac.
	 used by Reader class. you can use with Reader or directly (discouraged)."""
	# https://stackoverflow.com/a/10759061/260242
	# timeout in seconds

	poller = select.poll()
	poller.register(p, select.POLLIN)
	# read bytes and not strs. actually explicit is better than implicit
	# dev = getattr(p, "buffer", p) # conveniently stdin.buffer and stdin and stdout has a read function
	timeout_ms = timeout *1000

	def isFlag(v, f):
		return (v & f) == f

	_eof = b''
	def read(size=1): # i don't like to do this. but i just did.
		ret = poller.poll(timeout_ms)
		if not ret:
			return default

		val = ret[0][1]
		if isFlag(val, select.POLLIN) or isFlag(val, select.POLLPRI):
			try:
				return p.read(size)
			except Exception:
				return _eof # let it burn x3 (better/easier than checking if closed at the start. since poller will do it and sometimes in between those 2 calls it gets closed :( )

		# notice the if above. there is nothing to read as long as there's no "in"
		# 	- well actually this is a lie. when ffmpeg closes due to an existing file,
		#	- it's so quick that we can't read the content before pollhup and it poller REMOVES the pollin even though there's still data. WTF?!
		# 	- https://pymotw.com/3/select/index.html all this socket stuff, i don't like.
		# 	- i rather have ffmpeg breaking than having my software locking up. i need to test it more.
		if isFlag(val, select.POLLHUP) or isFlag(val, select.POLLRDHUP) or isFlag(val, select.POLLERR) or isFlag(val, select.POLLNVAL):
			return _eof # tell them is eof

		return default

	return read

class _ReadThread(threading.Thread):
	"""class for handling the threaded read by polling
	None means no data, b'' means eof. the opposite of what i would do. but that's how the system works."""
	buff = None
	def __init__(self, q, dev):
		super().__init__()
		self.q = q
		self.dev = dev
		self.read = readPoll(dev, 1, None) # notice none as default. and 1 as timeout.
		self.stopRequest = threading.Event()
		self.atEof = False

	def run(self):
		# don't call this directly unless you want problems. call "start"
		if self.stopRequest.is_set():
			print("Tried to re-run a reader thread. that won't work")
			return

		while not self.stopRequest.is_set():
			r = self.read(1) # read 1 byte. readPoll will wait at most 1 sec. otherwise we're likely to have a deadlock
			if r == b'':
				self.atEof = True # don´t reset it
				break # optimization (after eof nothing can be read right?)

			something = r is not None
			if not self.atEof and something:
				self.q.put(r, True, None) # if full block

	def join(self, timeout=None):
		self.stopRequest.set()
		super().join(timeout)
		self.__clean__()

	def __clean__(self):
		del self.q
		del self.dev
		del self.read

class Reader:
	"""Reads from a device in the background. with a buffer. and has a sane interface that wont except all the time or cause crashes.
	Can only be used once. Once this has been stopped. you need a new instance.
	Please call with a device of bytes, not str (e.g. stdin.buffer stdout.buffer)."""
	def __init__(self, dev, size = 1024):
		self.queue = queue.Queue(size) # deques with maxlength will DISCARD elements https://docs.python.org/3/library/collections.html#collections.deque
		self.thread = _ReadThread(self.queue, dev)
		self.thread.start()

	def read(self):
		"""reads whatever is available at that moment and returns it and forgets it. returns b'' when empty. check isEof to know if it has finished."""
		out = b''
		while True:
			try:
				out += self.queue.get(False) # don't block we will read as much as we can but no more. will except on empty.
			except queue.Empty:
				break
		return out

	def hasData(self):
		return self.queue.not_empty

	def isEof(self):
		return self.thread.atEof

	def stop(self, timeout=1):
		self.thread.join(timeout)
		return self.read() # empty buffers or the thread might be stuck trying to write

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
