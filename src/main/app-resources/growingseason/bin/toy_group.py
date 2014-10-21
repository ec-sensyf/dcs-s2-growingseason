#!/usr/bin/python

import sys
import os
import re
from collections import defaultdict

def main(fd, dstdir):

    groups = defaultdict(list)

    try: os.mkdir(dstdir)
    except OSError: pass


    for line in fd:
        dname, fname = os.path.split(line)
        if fname[:4] != 'ndvi': continue
        parts = re.split(r'\D+', line)
        key = parts[-5], parts[-4]
        groups[key].append(line)

    for k in groups.iterkeys():
        fname = 'tile_' + ('_'.join(k)) + '.urls'
        fd = open(os.path.join(dstdir, fname), 'w')
        fd.writelines(groups[k])
        fd.close()
        print fname

    # return grups



if __name__ == '__main__':
    junk = sys.argv.pop(0)
    dstdir = './outputs'
    fd = sys.stdin

    if len(sys.argv):
        dstdir = sys.argv.pop(0)
    if len(sys.argv):
        fd = open(sys.argv.pop(0))

    main(fd, dstdir)
