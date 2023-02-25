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

def shouldRunDirect(args):
	# fix for unreal asking clang for some stuff in private
	if args[-1] == "-": return True
	return False

def clientsToUse(args):
	# run pchs only on local instance, but through the worker, hence using load balancing
	# the local worker is index 0
	if "PCH." in args[-1]: return (0, )
	return None

#Exports
# all these are functions that receive args as params, and must return true/false. (except run_client)
# function that tell if it needs to run directly, and locally. skipping the use of workers.
# only use if the command fails when using a worker. it will skip load balancing. Use CLIENTS otherwise to filter allowed clients.
RUN_DIRECT = None # shouldRunDirect
#function that return a list of possible clients to run on, a list of INDEXES. or emtpy for all. eg (1,). receives args
CLIENTS = None
#function that tell if need to use env
USE_ENV = None
# function that tell if need to use shell
USE_SHELL = None
# function that tell if need to use comm pipes
USE_COMM = None
# functions that applies fixes
FIXES = () #(fixAndroidLink,)
