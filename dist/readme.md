# installation

* install python 3
* install rpyc
    
eg:
    
    pip3 install --user rpyc 

# Basic howto

# run programs in a worker

now run the worker with its config. (see samples/worker.js for a sample on how to config a worker)

    dist> worker.py workerX.js

now you can run any command in that worker by running the client

    dist> client.py echo 1

# to turn a program into using a worker

move your program to have an extra "_"

    move 'clang' to 'clang_'

now make a link to client.py in the place of clang

    ln -s ../../dist/client.py clang


# how to run multiple workers remotely 

* have multiple computers
* install the same environment in all (unless is something you can share over a mounted drive)
  * install python and rpyc
* copy this package (dist folder)
* set up one worker.js per machine with the corresponding ip
* optional but highly recommended:
  * set up an ssh server on each worker machine
* set up a shared drive server on the client machine (master) (eg samba works well on mac and linux and windows. could be nfs too but might bring issues with permissions)
* optional but recommended: set up a startup worker script (you will probably need it)
  * see samples/worker for an example (notice i just run that one directly on each worker machine)

* from the client machine
    * optional: forward the worker port through ssh
      * see samples/connect-w1. You'd need one of this script per worker (since each has it's own port number)
      * notice the port changes. since they are all forwarded to localhost. the client only connects to localhost.
* export the samba mount
* run each worker _on each remote machine_ 
  * connect through ssh (recommended, also recommended to use tmux). or run directly on the machines if you have access to the hardware (not recommended)

* note that you can modify client.py to use remote ips. and you can open the ports on the worker's machine.
but then all your communication will go in plain :] you won't want to do that.
the worker has no concept of user or authentication, that's a design feature that took me several years to learn, so it wont change.
if you need any security use ssh . < that is a period.
