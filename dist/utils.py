#!/usr/local/bin/python3
# coding: utf-8

__author__ = "Jeronimo Barraco-Marmol"
__copyright__ = "Copyright (C) 2021 Jeronimo Barraco-Marmol"
__license__ = "LGPL V3"
__version__ = "0.23"

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
