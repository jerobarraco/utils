# installation

* install python3
* install rpyc
* copy this package to a workspace that can be shared
    
eg:
    
    pip3 install --user rpyc 

# Basic howto

## run programs in a worker

run the worker with its config. (see samples/worker.js for a sample on how to config a worker)

    dist> ./worker.py workerX.js

now you can run any command in that worker by running the client

    dist> ./client.py echo 1

Note:
  You can run them directly, or explicitly with python.
  But make sure they are executable and that the shebang is set correctly (mac might like something different).

## Shadow a program (turn a program to be distributed, invoked by workers)

move your program to have an extra "_"

    move 'clang' to 'clang_'

The client program will add a _ when it needs to call the original software.
The workers will also call the command with a _ after it.

Now make a link to client.py in the place of the program

    ln -s ../../dist/client.py clang

Note: The extra "_" only applies when "shadowing" a real program. Like when doing a symlink like above.
Not when you call it in its normal form (like `python client.py program_to_run args`)
This is intentional, since we want to avoid calling the client in a cycle.

You can look at `samples/dxon` for an example.
`dxon` and `dxoff` are sample scripts used to activate and deactivate the distributed compilation
I encourage you to set up yours.

## Run multiple workers remotely 

* have multiple computers
* install the same environment in all (unless is something you can share over a mounted drive)
  * install python3 and rpyc
* optional but highly recommended:
  * set up an ssh server on each worker machine so that you can control them remotely
* set up a shared drive server on the client machine (master)
  * (eg sshfs works well on linux and mac, samba works well on mac and linux and windows. 
    could be nfs too, works well in linux, but permissions and encryption seems to be more complicated. might have issues with permissions)
  * if not using sshfs, export the samba mount (see notes on sample/worker)
  * Depending on the software you try to use it with you might need to share more than 1 folder.
    * This also depends on how that toolchain is installed and what other libraries/resources it uses.
    * Otherwise, you can put all into one workspace (like unrealEngine for linux)
    * E.g. for XCode you might need to share a few folders. and for AppCode (intelliJ) itself you need another one. 
* mount the workspace where you will execute commands to/from on each worker computer
  * eg if you are going to modify files in /home/user/workspace share and mount it in each worker computer,
    under the same route. see `samples/worker`
  * you can also have binaries in that folder as long as executing programs from a mounted drive won't bring problems.
    * e.g. UnrealEngine5's toolchain can be just shared over the drive and ´it just works´(TM)
* copy this package (dist folder) or better yet. have this package available in the workspace.
* set up one worker##.js per machine with the corresponding port and config (and ip). 
* optional but recommended: set up a startup worker script (you will probably need it)
  * see samples/worker for an example (notice i just run that one directly on each worker machine)
  * you will need a different one for each worker, since you need a different config file per worker

* from the client machine
    * optional: forward the worker port through ssh
      * see `samples/connect-w1`. 
      * You'd need one of this script per worker, since each has it's own port number and ip/machine name.
      * notice the port changes. since they are all forwarded to localhost. the client only connects to `localhost`.

* run each worker _on each remote machine_ 
  * connect through ssh (recommended, also recommended to use tmux).
  * or run directly on the machines if you have access to the hardware (not recommended)

And you're ready to run commands through client.py. either shadowing or directly.

Note:
you can modify config.py and the worker##.js, to use IPs (not only "localhost"), and you can open the ports on the worker's machine.
but then all your communication will go in plain and anyone can connect to the worker :] you might not want to do that.
the worker has no concept of user or authentication, encryption, or security, that's a design feature that took me several years to learn, so it won't change.
If you need any security use ssh . < that is a period.
Ssh port forward and connecting to "localhost" and opening ports on "localhost" helps to isolate them.
by forwarding the connection through ssh you ensure the communication is encrypted and authenticated.
By having each worker and client connect to their respective "localhost" you avoid having the port exposed on the network.
"localhost" is not the same as 0.0.0.0 (at least on mac and linux).
listening on localhost will not make it available by ip, that is, the network interface.


# Setting up your "toolchain" for distributed/turbo computing

See: `samples/dxon` `samples/dxoff` `ue/duon` ue `duoff`
If the program you're shadowing is part of another tool/program/framework.
You might need to ensure any limit is raised, since you will have now more virtual resources than local ones.
This heavily depends on which software you are using. I provide some examples in `samples/` and `ue/`
For example, in xcode you will need to raise the process limit.
On unreal engine you need to force it to raise the process limit, as well as lower the memory requirement.

It's recommended to set up a script to enable/disable this. Since you might want to try to do specific tasks locally, and having raised limits could choke your pc.
If you are overriding several things, i would recommend a script for each one. For example: one for desktop compilation, one for android.


# Idea: Sharing workers among clients from different computers/users

benefit: one worker will keep its load optimized so you can safely exhaust the worker pc resources.
it's possible.
but beware of paths collisions between clients from different users.
specially around system-wide apps (specially on windows which is very multi-user unfriendly).

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
there's a config in config.py to selectively enable it (useComm).
interactive software like grep, sort, from stdin won't know when to quit.
if you need to pipe stdin configure it to run directly (config.py::RUN_DIRECTLY)
