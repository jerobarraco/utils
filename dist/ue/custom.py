#!/usr/bin/python3
# coding: utf-8
#!/usr/local/bin/python3

__author__ = "Jeronimo Barraco-Marmol"
__copyright__ = "Copyright (C) 2021 Jeronimo Barraco-Marmol"
__license__ = "LGPL V3"
__version__ = "1.00"

def fixAndroidLink(args, CONF={}):
	"""This is just to try to fix linking (on android)
	if the executable is clang, adds ++ and removes _
	This depends on you using (forcing) 'clang' as the compiler (and not clang++)
	Will mutate args"""

	# only check on clang not clang++ (important because we need to remove _)
	# this means, you should avoid to shadow/override clang++
	is_clang = args[0].endswith('/clang') or args[0].endswith('/clang_')
	if not is_clang: return False

	has_out = False
	is_link = False
	#verify the out is an so
	for a in args:
		if a == '-o':
			has_out = True
			continue
		if not has_out: continue
		if a.endswith('.so'):
			is_link = True
			break
		has_out = False

	if is_link:
		if args[0][-1] == '_':
			args[0]=args[0][:-1] #remove the _ , linker needs to not have it (really)

		if not args[0].endswith('++'): # force to use ++
			args[0] += '++'
	return is_link

def fixUE(args):
	pass

def shouldRunLocal(args):
	# fix for unreal asking clang for some stuff in private
	# todo move to samples and leave this without one
	last = args[-1]

	# - is required (since reading/writing to stdin is hard)
	# --version is nice for speed
	# -lgcc is when it does linking. this is a nice to have also, just because linking reads a lot of disk and is relatively fast on local
	if last in ("-", "--version", "-lgcc"): return True
	if "PCH." in last: return True #notice sintax here means something different
	return False

#Exports
RUN_LOCAL = shouldRunLocal # None
#functions that tell if need to use env
USE_ENV = None
# functions that tell if need to use shell
USE_SHELL = None
# functions that tell if need to use comm pipes
USE_COMM = None
# functions that applies fixes
FIXES = () #(fixAndroidLink,)