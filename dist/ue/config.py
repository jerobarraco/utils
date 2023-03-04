#!/usr/bin/python3
# coding: utf-8
#!/usr/local/bin/python3

__author__ = "Jeronimo Barraco-Marmol"
__copyright__ = "Copyright (C) 2021 Jeronimo Barraco-Marmol"
__license__ = "LGPL V3"
__version__ = "1.01"


# this config file is a copy of the base one, tweaked for unreal on linux

# ------- General config

# Yeah the config is embedded. i don´t want to have to parse an extra file everytime this client is run.
# also json has to be parsed from string, from python, while a .py not only gets precompiled, but also parsed by python itself.
# after all it's meant to run stuff that are already too heavy for one machine.
# if you need different config copy the client+config+utils+worker files elsewhere. it's very small.

# times are in seconds
DEBUG = True
TIMEOUT = 180
COOLDOWN = 2
SLEEP = 0
WORKERS = (
	# you can use an ip or "localhost" this is intentional. but "localhost" is preferred, since that will force you to set up ssh tunneling
	# which has security implications
	# the order defines the priority. workers are always tested in order. (that's absolutely intentional).
	"localhost:7722",
	"localhost:7711",
	"localhost:7744"
)

_OTHERS = (# this is just here just to quickly disable or enable workers by moving this line up&down
	"localhost:7715",
	"localhost:7717",
	"localhost:7712",
	"localhost:7718",
	"localhost:7703",
	"localhost:7705",
	"localhost:7723",
)

# List of commands to run directly, * means all.
# This skips workers, and as such, load balancing. careful.. eg 'ld'
# but also uses the client.py stdin/out/err
# (fun fact, mc works)
RUN_DIRECTLY = (
)

# List of commands to run using the current environment, * means all
USE_ENV = ()

# List of commands to run using a shell, * means all. shell might create side effects. and a slight security issue if ran outside ssh.
# there were some reasons why you would like to run in a shell. one of them is expansion of commands. the rest i forgot. has some implications with stdin/out/err maybe.
USE_SHELL = (
)

# List of commands to pipe stdin to, * means all.
# for example 'grep', or "sort"
USE_COMM = (
)


# ----- Functions

# --- these are used in this file only
def fixAndroidLink(args):

	"""This is just to try to fix linking (on android)
	if the executable is clang, adds ++ and removes _
	This depends on you using (forcing) 'clang' as the compiler (and not clang++)
	Will mutate args"""
	# TODO this was code used for another toolchain (not ue) but i leave it here in case someone (or me) gets around to fix it.
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


# to be used by client
def doFixes(args):
	return False
	# ignored
	#for fix in [fixUE, fixAndroidLink]:
	#	fix(args, CONF)

def clientsToUse(args):
	# run pchs only on local instance, but through the worker, hence using load balancing
	# the local worker is index 0
	last = args[-1]
	# local worker is in position 1, this is not ideal. it should be 0, but since im testing this i put it in 1.
	local_w = (1, )

	# force these to use local worker.
	# -lgcc (link) is a speed-ups (since it uses lots of disk and memory but not much cpu) (still goes through the worker, so there's load balancing)
	# PCH is a fix (not always happens) notice the difference in syntax
	if (last in ("-lgcc", "-")) or ("PCH." in last):
		return local_w
	return None

def shouldRunDirect(args):
	last = args[-1]

	# "-" is needed, fix for unreal asking clang for some stuff in private (using stdin)
	#    actually now this also works when putting it into useComm but this way might be more bulletproof.
	# "--version" is nice for speed
	if last in ("-", "--version"): return True
	return False

def shouldUseShell(args):
	for a in args[1:]:
		if a in ('&&', ';', '||', '|', '>', '<'): return True
	return False

def shouldUseComm(args):
	return False

def shouldUseEnv(args):
	return False
