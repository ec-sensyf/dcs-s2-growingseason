#!/opt/anaconda/bin/python

import sys
import os
import re
from glob import glob
from osgeo import gdal, osr
from osgeo.gdalconst import *


env = os.environ

if env['USER'] == 'mapred':
    import cioppy
    ciop = cioppy.Cioppy()
    def LOGINFO(x): ciop.log("INFO", "Cp/ECHO:" + x)
    LOGINFO(" Using Cioppy tools")
    copy = lambda pths, dst: ciop.copy(pths, dst, extract=False)
    # getparam = ciop.getparam
    def publish(pths):
        if isinstance(pths, basestring):
            pths = [pths]
        for pth in pths:
            LOGINFO("Publishing path " + pth)
            ciop.publish(pth, metalink=True)
    permadir = '/application/growingseason/permanent/'
else:
    def LOGINFO(x): print("[INFO]ECHO:" + x)
    params = {
        'mode' : 'all',
        'startdate' : '2000-07-02',
        'enddate'   : '2525-08-05',
        'othreshold': 0.5,
        'ethreshold': 0.7
    }
    # def getparam(x): return params[x]
    def copy(pths, dst): 
        if isinstance(pths, basestring):
            pths = [pths]
        for pth in pths:
            shutil.copy(pth, dst)
    def publish(pths, **kwargs):
        if 'recursive' in kwargs:
            pths = [os.path.join(pths, x) for x in os.listdir(pths)]
        if isinstance(pths, basestring):
            pths = [pths]
        for pth in pths:
            LOGINFO("Publishing path " + pth)
    permadir = env['HOME'] + '/src/SenSyF/s2/growingseason/permanent/'

def mkdir_p(path):
    try:
        junk = os.listdir(path)
    except OSError:
        head, tail = os.path.split(path)
        mkdir_p(head)
        os.mkdir(path)

def colorize(fname, dstdir):
    LOGINFO("Colorizing " + fname)
    try:
        product_type = re.match(r'GS_(\w+)_(\d{4})\.tiff', fname).groups()[0]
    except AttributeError:
        raise ValueError("Unexpected name of product file")

    if product_type not in ['onset', 'peak', 'end']:
        raise ValueError("Unexpected type of product file")

    os.rename(fname, 'tmp.tiff')

    src_ds = gdal.Open('tmp.tiff')
    vrt = gdal.Open(permadir + product_type + '.vrt')
    driver = gdal.GetDriverByName('GTiff')

    dst_ds = driver.CreateCopy(fname, vrt, 0)

    dst_rb = dst_ds.GetRasterBand(1)
    src_rb = src_ds.GetRasterBand(1)
    dst_rb.WriteArray(src_rb.ReadAsArray())
    
    dst_ds = None
    src_ds = None
    os.unlink('tmp.tiff')
    os.rename(fname, os.path.join(dstdir, fname))

def cluster_main():
    srcdir = os.path.join(env['TMPDIR'], 'inputs')
    dstdir = os.path.join(env['TMPDIR'], 'outputs')
    mkdir_p(srcdir)
    mkdir_p(dstdir)

    os.chdir(srcdir)

    for line in sys.stdin:
        url = line.rstrip()
        fname = os.path.basename(url)

        copy(url, srcdir)
        colorize(fname, dstdir)
    publish(glob(dstdir + '/*.tiff'))

def cmdline_main(args):
    for fname in args:
        colorize(fname, '.')


if __name__ == '__main__':

    if env['USER'] != 'mapred':
        # Running from command-line
        cmdline_main(sys.argv[1:])

    else:
        # Running in cluster
        cluster_main()

    sys.exit(0)



