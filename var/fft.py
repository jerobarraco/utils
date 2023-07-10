#!/usr/bin/env python -u
"""
coded by : Jeronimo Barraco-Marmol
run as
    parec --channels=1 --latency-msec=20 --rate=22000 | python -u fft.py [10000 [256]]
"""
import struct, sys
import numpy as np

BARS = " ▁▂▃▄▅▆▇"#█"
BARSF1 =  " ▁▂▃▄▅▆▇█"
BARSF =  " ▏▎▍▌▋▊▉█" #░▒▓
MAX_B = len(BARS)-1
MAX_BF = len(BARSF)-1

# this is the same as MAX_S so use only one

cls = lambda: print("\033c\033[3J", end='')

def Bar(v):
    cv = min(1.0, max(0.0, v))
    return BARS[int(cv * MAX_B)]

def SBar(vals):
    return "".join(map(Bar, vals))

def BarF(v):
    cv = min(1.0, max(0.0, v))
    return BARSF[int(cv * MAX_BF)]

def BarFU(v):
    """unsafe, but optimized version, v MUST be between 0 and 1"""
    return BARSF[int(v * MAX_BF)]

def SBarF(vals):
    return "".join(map(BarF, vals))

HAMM = np.zeros(1)
def getFFT(data):
    global HAMM
    """Given some data and rate, returns FFTfreq and FFT (half)."""
    # taken from stackoverflow somewhere, the only one that worked
    # avg = np.average(data)
    #data = data - avg# zero center # not necessary
    data = data*HAMM

    fft = np.fft.rfft(data)
    fft = np.abs(fft)
    fft = fft[:int(len(fft) / 2)] # halve
    # fft = 10 * numpy.log10(fft)
    #freq = np.fft.fftfreq(len(fft), 1.0 / rate)
    #return freq[:int(len(freq) / 2)], fft[:int(len(fft) / 2)]
    #return freq[:int(len(freq) / 2)], fft
    return fft

VALS_MAX = 40000.0
VALS_W = 256
VALS = [0]*VALS_W
LINES_N = 20
LINES = [""]*LINES_N
RATE = 200
BS = 2
W = 50

VALS_DMAX = VALS_MAX
VALS_DDECAY = 50.0
def DynNorm(v):
    global VALS_DMAX
    VALS_DMAX = np.max([VALS_DMAX-VALS_DDECAY, np.average(v), 1.0])# i is the min, otherwise is a divide by 0
    #print (VALS_DMAX)
    return v/VALS_DMAX

def main():
    global VALS, HAMM
    HAMM = np.hamming(VALS_W)
    while True:
        # get the needed buffer in one call
        c = sys.stdin.buffer.read(BS*VALS_W)
        # convert to unsigned short low end
        VALS = list([
            struct.unpack("<h", c[i*BS:((i+1)*BS)])[0] for i in range(VALS_W)
        ])
        f = getFFT(VALS)
        afft = f/VALS_MAX
        #afft = DynNorm(f)
        afft = np.clip(afft, 0.0, 1.0) # clip for BafFU
        for c in map(BarFU, afft):
            sys.stdout.buffer.write(c.encode("utf-8"))
        sys.stdout.write('\n')
        sys.stdout.buffer.flush()

if __name__ == "__main__":
    if len(sys.argv)>1:
        VALS_MAX = float(sys.argv[1])

    if len(sys.argv)>2:
        VALS_W = int(sys.argv[2])
        VALS = [0]*VALS_W
    exit(main())
