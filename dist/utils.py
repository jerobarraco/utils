#!/usr/bin/python3
# coding: utf-8
#!/usr/local/bin/python3

__author__ = "Jeronimo Barraco-Marmol"
__copyright__ = "Copyright (C) 2021 Jeronimo Barraco-Marmol"
__license__ = "LGPL V3"
__version__ = "1.00"

import select
import os

#inspired by https://stackoverflow.com/a/51604225/260242
def readLen(p):
	# works on mac, might work on linux, probably doesnt on windows, but you shouldn't be using it anyway
	# if windows: return 1 #would be 'ok'
	size = os.fstat(p.fileno()).st_size
	return size

def readIfAny(p, timeout=1, default=None):
	if select.select([p], [], [], timeout)[0]:
		size = readLen(p)
		if size:
			return p.read(size)
	return default

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
