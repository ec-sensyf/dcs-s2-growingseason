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
else:
    def LOGINFO(x): print("[INFO]ECHO:" + x)

def colorize(fname, vrtname):
    LOGINFO("Colorizing " + fname + " using " + vrtname)

    os.rename(fname, 'tmp.tiff')

    src_ds = gdal.Open('tmp.tiff')
    vrt = gdal.Open(vrtname)
    # vrt = gdal.Open(permadir + 'test_nocolor.vrt')
    driver = gdal.GetDriverByName('GTiff')

    dst_ds = driver.CreateCopy(fname, vrt, 0)

    for tag, val in src_ds.GetMetadata().iteritems():
        dst_ds.SetMetadataItem(tag, val)

    dst_rb = dst_ds.GetRasterBand(1)
    src_rb = src_ds.GetRasterBand(1)
    dst_rb.WriteArray(src_rb.ReadAsArray())
    
    dst_ds = None
    src_ds = None
    os.unlink('tmp.tiff')
    # os.rename(fname, os.path.join(dstdir, fname))


if __name__ == '__main__':
    junk = sys.argv.pop(0)
    vrtname = sys.argv.pop(0)

    for name in sys.argv:
        colorize(name, vrtname)

