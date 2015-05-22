#!/opt/anaconda/bin/python

import sys
import os
import re
from collections import defaultdict

env = os.environ

if env['USER'] == 'mapred':
    import cioppy
    ciop = cioppy.Cioppy()
    def LOGINFO(x): ciop.log("INFO", "CP:" + x)
    def LOGERROR(x): ciop.log("ERROR", "CP:" + x)
    LOGINFO(" Using Cioppy tools")
    def copy(url, dst):
        LOGINFO("Copying <{0}> to <{1}>".format(url, dst))
        ciop.copy(pths, dst, extract=False)
    getparam = ciop.getparam
    def publish(pths):
        if isinstance(pths, basestring):
            pths = [pths]
        for pth in pths:
            LOGINFO("Publishing path " + pth)
            ciop.publish(pth, metalink=False)
else:
    def LOGINFO(x): print("[INFO]ECHO:" + x)
    def LOGERROR(x): print("[ERROR]ECHO:" + x)
    def copy(pths, dst): 
        if isinstance(pths, basestring):
            pths = [pths]
        for pth in pths:
            LOGINFO("Copying <{0}> to <{1}>".format(pth, dst))
            shutil.copy(pth, dst)
    def publish(pths, **kwargs):
        if 'recursive' in kwargs:
            pths = [os.path.join(pths, x) for x in os.listdir(pths)]
        if isinstance(pths, basestring):
            pths = [pths]
        for pth in pths:
            LOGINFO("Publishing path " + pth)



def main(fd, dstdir):

    groups = defaultdict(list)

    try: os.mkdir(dstdir)
    except OSError: pass


    for line in fd:
        dname, fname = os.path.split(line.rstrip())
        parts = fname.split('.', 1)
        if parts[1] != 'tar.gz' or not re.match(r'\d+_\d+', parts[0]):
            logerror("Unexpected input url: <{0}>".format(line.rstrip()))
            continue
        # if fname[:4] != 'ndvi': continue
        # parts = re.split(r'\D+', line)
        # key = parts[-5], parts[-4]
        groups[parts[0]].append(line)

    for k in groups.iterkeys():
        # fname = 'tile_' + ('_'.join(k)) + '.urls'
        fname = os.path.join(dstdir, 'tile_' + k + '.urls')
        fd = open(fname, 'w')
        fd.writelines(groups[k])
        fd.close()
        publish(fname)

    # return grups



if __name__ == '__main__':
    junk = sys.argv.pop(0)
    dstdir = env['TMPDIR']
    fd = sys.stdin

    if len(sys.argv):
        dstdir = sys.argv.pop(0)
    if len(sys.argv):
        fd = open(sys.argv.pop(0))

    main(fd, dstdir)
