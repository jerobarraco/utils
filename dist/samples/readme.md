# Config

## config.py (client.py)
the config is embedded. this is a feature. the description is in the comments.

## worker.js (worker.py)
the config is in worker.js you need one per each worker. i can't put comments on js. so here is the explanation:

"host": "localhost" or "x.x.x.x" (ip).
	recommended to use localhost. The ip or device to listen for connections for.
"port": "####"
	the port to use for listening connection. 
	port and host must match on config.py

"numTasks": 4
	maximum number of tasks allowed in the current worker.

"timeout": 360
	timeout in seconds for the process to run. when reached. the process WILL get killed. if it's less-than-or 0 then no timeout is set.

"timeoutRead": 1
	timeout used for read. this timeout won't kill the process. this is how much the worker will wait for output of the command. 
	when this time is reached communication is returned to the client. and further read is attempted later.
	a big value means less network communication, hence faster times.
	but increases time before receiving data from the client, and maybe latency.
	it's similar to buffering on output.
	when using with pipes (coms) it will delay the execution. but a small time means more overhead on network.

"debug": true,
	true or false. will print debug information

"colors": true,
	true or false. will use colors

"colorsBg": false,
	true or false. will use colors for the background.

"icons": ["▶", "✓", "✘", "!", "="],
	icons to use. (hint you could use emojis sometimes, but might look aweful.) icons are in this order:
	* start
	* finished
	* finished with error
	* timeout
	* stopped (killed)

"remapCmds": {},
	deprecated
	remap only the command. it only remaps the ending part. and last ocurrence. won´t remap a folder
	e.g. {"/clang", "/clang_"} (will call to clang_ whenever you try and call clang)

"remapDirs": {}
	remapDirs: deprecated
	remap the current working directory (and maybe parameters!). it only remaps the starting part. so to change something in the middle. youd need to specify the whole path until there.
	e.g. {"/home/peter/", "/home/worker/"} (peter is the address on the client, worker the one in the worker)
