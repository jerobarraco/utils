
# set up
on system preferences, under sharing
* enable file sharing,
* click "options" then select your user (important)

*on $HOME/.ssh/config add the line

    Compression yes

* enable remote login
* * click + and add you and *anyone* that will use the pc as worker.
* do the same on any worker machine

on all machines:
install python3 (3.8.9) (with brew probably)
sudo pip3 install rpyc

brew install tmux (optional)

on client machine, edit dxon, then run
on worker machines run dxenable (unless they're also clients)
    if you dont want/cant to do this modification, you can specify in the worker config to remap 
    "/clang_": "/clang"
    but you need to MAKE SURE you wont shadow clang (in that machine), or youll get in a loop

for each worker machine (including local machine) 
* put all this files together. maybe in the same folder as the client and worker script (this folder)
* create a worker conf file (worker-xx.json) and edit (see samples)
* create a connect script and edit (see samples) (except local machine)

# tweak smb for fastness (optional not much difference)
defaults write com.apple.desktopservices DSDontWriteNetworkStores -bool TRUE
sudo sysctl debug.lowpri_throttle_enabled=0 # maybe put in the config file
https://www.tecklyfe.com/speed-up-time-machine-backups/

# To run
on each worker machine (including yours)
* connect via ssh: ssh -L 7XXX:localhost:7XXX cf-mac-XXX  (except on local machine) (or use the connect script)
* connect to tmux: tmux attach (or tmux if no session started)
* run worker: ./worker (edit first)

activate script (dxon)


# TODO
improve the doc

note: linker will not link if exectuable is appended with _ (breaks android)
worker is returning exitcode None for certain commands (linker) 

fix ios 
    mv fails on resource busy (smb problem)

fix android

    FIXED
    mv clang clang_
    ln -s client.py ./clang
    # make sure clang++ is ok
    rm clang++
    cp ./clang_ ./clang++
    remove remaps on clang++ in workers

    modify client.py
    set config flag
        fixAndroid : true

    modify gradle.properties
        org.gradle.workers.max=48
        org.gradle.parallel=true

    change the compiler on 
        (somewhere)/CMakeFiles/3.10.2/CMakeCXXCompiler.cmake
            set(CMAKE_CXX_COMPILER "/usr/local/share/android-sdk/ndk-bundle/toolchains/llvm/prebuilt/darwin-x86_64/bin/clang")

   



fix em
    
    see $HOME/.emscripten

# Unsupported
Pipes not supported (stdin stdout). will hang the command (probably). (unless is a complex expression ran in a shell)
environ purposely not forwarded (by default, can be configured). 
shell purposely not activated (by default, can be configured)
interactive shell not supported (input password, enter yes, etc)
