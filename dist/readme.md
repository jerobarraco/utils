# installation

* install python3
* install rpyc
    
eg:
    
    pip3 install --user rpyc 

# Basic howto

## run programs in a worker

now run the worker with its config. (see samples/worker.js for a sample on how to config a worker)

    dist> ./worker.py workerX.js

now you can run any command in that worker by running the client

    dist> ./client.py echo 1

(Note you can run them directly (but make sure they are executable), or explicitly with python)

## Shadow a program (turn a program to be invoked by workers)

move your program to have an extra "_"

    move 'clang' to 'clang_'


this client program will add a _ when it needs to call the original software.
The workers will also call the command with a _ after it.

now make a link to client.py in the place of clang

    ln -s ../../dist/client.py clang

Note: The extra "_" only applies when "shadowing" a real program. Like when doing a symlink like above.
Not when you call it in its normal form (like `python client.py program_to_run args`)

## Run multiple workers remotely 

* have multiple computers
* install the same environment in all (unless is something you can share over a mounted drive)
  * install python3 and rpyc
* optional but highly recommended:
  * set up an ssh server on each worker machine so that you can control remotely
* set up a shared drive server on the client machine (master)
  * (eg sshfs works well on linux and mac, samba works well on mac and linux and windows. could be nfs too but might bring issues with permissions)
  * if not using sshfs, export the samba mount (see notes on sample/worker)
* mount the workspace where you will execute commands to/from on each worker computer
  * eg if you are going to modify files in /home/user/workspace share and mount that in each worker computer under the same route
  * (see samples/worker)
  * you can also have binaries in that folder (e.g. the unreal toolchain) as long as executing programs from a mounted drive won't bring problems.
* copy this package (dist folder) or better yet. have this package available in the folder you will mount later.
* set up one worker.js per machine with the corresponding ip
* optional but recommended: set up a startup worker script (you will probably need it)
  * see samples/worker for an example (notice i just run that one directly on each worker machine)

* from the client machine
    * optional: forward the worker port through ssh
      * see samples/connect-w1. You'd need one of this script per worker (since each has it's own port number)
      * notice the port changes. since they are all forwarded to localhost. the client only connects to localhost.
* run each worker _on each remote machine_ 
  * connect through ssh (recommended, also recommended to use tmux).
  * or run directly on the machines if you have access to the hardware (not recommended)

* note that you can modify client.py to use remote IPs (not only "localhost").
and you can open the ports on the worker's machine.
but then all your communication will go in plain :] you won't want to do that.
the worker has no concept of user or authentication, that's a design feature that took me several years to learn, so it wont change.
if you need any security use ssh . < that is a period. (ssh port forward and connecting to "localhost" and opening ports on "localhost" helps to isolate them)

# Sharing workers among clients from different computers/users

benefit: one worker will keep its load optimized so you can safely exhaust the worker pc resources.
it's possible.
but beware of paths collisions between clients from different users.
specially around system wide apps (specially on windows which is very multi-user unfriendly).

you can use multiple mounts on the worker, mounted with different credentials. 
( e.g.
/home/me/work mounted using "me" user
and /home/peter/work using "peter" user)

the worker will read+write and the mounted filesystem "should" map the correct user. (this is in theory and depends on how you've configured it)
but potentially leaves an open door for user "me" to read/write to /home/peter as peter.
also someone has to mount those things, so potentially either all users should be able to log into the worker machine,
or someone at the working machine should be able to mount the users (i.e. have their credentials).
you would probably want a middle solution (like users able to remotely mount their workspaces)
restarting the worker is uncomfortable as well, but as long as you don't need to change it's configuration, you don't to.

# Supported platforms
Linux, Mac, windows partially

## Windows
Shadowing a command is tricky and i haven´t done it properly yet, but might be doable.
I don't use windows, so feel free to donate to me to do this.
You would need to use something like pyinstaller or cxfreeze (haven't tried it). 
The issue with pyinstaller was that it exatracts the program each time you run it. (you could change it but i haven't tinkered with it yet.)

Running commands remotely is fine by using 
    
    python3 client.py command arg1 arg2 arg3



# Limitations

piping doesn't work perfectly all the times.
there's a config in client.py to selectively enable it (useComm).
interactive software like grep from stdin won't know when to quit.
other software can be piped normally
