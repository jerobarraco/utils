#!/usr/bin/env python
#coding:utf-8
"""
	Documentation
		Some extra utils for os. Defines PLAT, P_LIN, P_MAC, P_WIN and open_file
"""

__version__ = "0.1a"

__author__ = "Jeronimo Barraco Marmol"

import sys, os, subprocess

# get Platform
P_LIN = 0
P_MAC = 1
P_WIN = 2
PLAT = P_LIN
if sys.platform == "win32":
	PLAT = P_WIN
else:
	PLAT = P_MAC if sys.platform == "darwin" else P_LIN



def open_file(filename):
	"""Tells the OS to open a file (shows explorer or opens the browser)"""
	if PLAT == P_WIN:
		os.startfile(filename)
	else:
		opener = "open" if PLAT == P_MAC else "xdg-open"
		subprocess.call([opener, filename])