
# set up
on system preferences, under sharing
*enable file sharing,
*click "options" then select your user (important)

on $HOME/.ssh/config add the line
Compression yes

*enable remote login
*click + and add you and any one that will use the pc as worker.
* do the same on any worker machine

on all machines:
install python3 (3.8.9) (with brew probably)
sudo pip3 install rpyc

brew install tmux
on client machine, edit dxon, then run
on worker machines run dxenable (unless theyre also clients)

for each worker machine (including local machine) 
* put all this files together. maybe in the same folder as the client and worker script (this folder)
* create a worker conf file (worker-xx.json) and edit (see samples)
* create a connect script and edit (see samples) (except local machine)

# tweak smb for fastness
defaults write com.apple.desktopservices DSDontWriteNetworkStores -bool TRUE

# To run
on each worker machine (including yours)
* connect via ssh: ssh -L 7XXX:localhost:7XXX cf-mac-XXX  (except on local machine) (or use the connect script)
* connect to tmux: tmux attach (or tmux if no session started)
* run worker: ./worker (edit first)

activate script (dxon)


# TODO
improve the doc

note: linker will not link if exectuable is appended with _
worker is returning exitcode None for certain commands (linker) 

fix ios 
    mv

fix android

    FIXED
    mv clang clang_
    ln -s client.py ./clang
    # make sure clang++ is ok
    rm clang++
    cp ./clang_ ./clang++
    remove remaps on clang++ in workers

    (did i changed the compiler somewhere to be clang?)



fix em
    
    see $HOME/.emscripten

# Unsupported
Pipes not supported (stdin stdout). will hang the command.
environ purposely not forwarded (by default). 
shell purposely not activated (by default)
interactive shell not supported (input password, enter yes, etc)
