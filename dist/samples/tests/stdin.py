#!/bin/python -u
import sys
for line in iter(sys.stdin.readline, ''):
	print(sys.stdin.read())

print ("done")

# cat "/mnt/extra/@home/nande/work/repos/breakout/assets/audio/music/DEMO.ogg" | ./client.py ffmpeg -f ogg -i pipe:  encoded.mp3
# cat readme.md | ./client.py grep --color=auto "#"
# cat "/mnt/extra/@home/nande/work/repos/breakout/assets/audio/music/DEMO.ogg" | ./client.py ffmpeg -f ogg -i pipe:  encoded.mp3
