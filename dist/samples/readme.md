# Config

## client.py
the config is embedded. this is a feature. the description is in the comments.

## worker.js (worker.py)
the config is in worker.js you need one per each worker. i can't put comments on js. so here is the exlanation:

    TODO


# Worker config
remapCmds: deprecated
remap only the command. it only remaps the ending part. and last ocurrence. won´t remap a folder

remapDirs: deprecated
remap the current working directory. it only remaps the starting part. so to change something in the middle. youd need to specify the whole path until there.
