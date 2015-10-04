from os import path
import os
from glob import glob

single = ['random', 'bass', 'guitar']
double = ['drums', 'voice']

def load_samples(mixer, origin='./assets/samples'):
    global single 
    global double
    origin = path.abspath(origin)
    singles = {}
    for s in single:
        singles[s] = []
        for f in glob(path.join(origin, s, '*.wav')):
            if path.isfile(f):
                print("Loading %s" % f)
                try:
                    singles[s].append(mixer.Sound(f))
                except:
                    print("File %f is not readable" % f)
    doubles = {}
    for s in double:
        doubles[s] = {}
        for c in glob(path.join(origin, s, '*')):
            if path.isdir(c):
                c = path.basename(c)
                doubles[s][c] = []
                for f in glob(path.join(origin, s, c, '*.wav')):
                    if path.isfile(f):
                        print("Loading %s" % f)
                        try:
                            doubles[s][c].append(mixer.Sound(f))
                        except:
                            print("File %f is not readable" % f)
    return {'single': singles, 'double': doubles}

