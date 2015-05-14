#!/opt/anaconda/bin/python
import os
import os.path
# from os import environ
env = os.environ
import sys
import shutil
from shutil import rmtree, copyfile
import tarfile
import re
import datetime as dt
import time
import numpy as np
from glob import glob

from osgeo import gdal, osr
from osgeo.gdalconst import *
# import data_handler as dh

gdal.UseExceptions()

# inputdir = './input'
# outputdir = './output'

mask_fname = 'maske_sval.tiff'

permadir = '/application/growingseason/permanent'
#permadir = './permanent'

if env['USER'] == 'mapred':
    import cioppy
    ciop = cioppy.Cioppy()
    def LOGINFO(x): ciop.log("INFO", "Cp/ECHO:" + x)
    LOGINFO(" Using Cioppy tools")
    copy = lambda pths, dst: ciop.copy(pths, dst, extract=False)
    getparam = ciop.getparam
    publish = ciop.publish
else:
    def LOGINFO(x): print("[INFO]ECHO:" + x)
    params = {
        'mode' : 'all',
        'startdate' : '2000-07-02',
        'enddate'   : '2525-08-05',
        'othreshold': 0.5,
        'ethreshold': 0.7
    }
    def getparam(x): return params[x]
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

def copy_and_unpack(url, dst):
    fname = os.path.basename(url)
    path = os.path.join(dst, fname)
    copy(url, dst)
    tf = tarfile.open(path, 'r')
    tile = tf.next().name       # Subdir is first in tarfile
    tf.extractall(path=dst)
    tf.close()
    os.unlink(path)
    return tile


def safe_getparam(x, default):
    try:
        rval = getparam(x)
    except:
        return default
    return rval

def mkdir_p(path):
    try:
        junk = os.listdir(path)
    except OSError:
        head, tail = os.path.split(path)
        mkdir_p(head)
        os.mkdir(path)

def cleandir(dir):
    for name in os.listdir(dir):
        pth = os.path.join(dir, name)
        try:
            shutil.rmtree(pth)
        except OSError:
            os.unlink(pth)

def encode(idays):
  odays = np.minimum(np.maximum(0, idays - 100), 199).astype(np.uint8)

  # Values 370 and above (mask values) map to [200, ...)
  ii = np.where(idays >= 370)
  odays[ii] = idays[ii] - 170

  return odays


def create_remapped_mask(src_fn, mask_fn, remap_mask_fn):

    copyfile(src_fn, remap_mask_fn)
    try:
        src_ds = gdal.Open(mask_fn, GA_ReadOnly)
    except RuntimeError:
        mask_fn = os.path.split(mask_fn)[-1]
        src_ds = gdal.Open(mask_fn, GA_ReadOnly)
    dst_ds = gdal.Open(remap_mask_fn, GA_Update)

    rmask = dst_ds.ReadAsArray()
    dst_ds.GetRasterBand(1).WriteArray(0*rmask + 370)   # Fill with water

    gdal.ReprojectImage(src_ds, dst_ds)
    dst_ds = None

def get_remapped_mask(src_fn, mask_fn, remap_mask_fn='GS_omask.tiff'):

    create_remapped_mask(src_fn, mask_fn, remap_mask_fn)

    ms = gdal.Open(remap_mask_fn)
    return ms


def average(datadir, outputdir, avg_fname, date_start, date_end):
    '''Prototype functionality for averaging in SenSyF S2 Service.

    datadir -- where input files are found
    outputdir -- where files are written
    avg_fname -- name of file (in permadir) where results (average) should be saved
    date_start -- 
    date_end -- date intervals to consider.  The day/month ranges are
         considered independently from the years, i.e.
         date_start = '2000-07-04'; date_end = '2010-08-03'
         will compute the average for the period July 4th to August 3rd 
         over all years from 2000 to 2010 (inclusive).'''

    dts = time.strptime(date_start, '%Y-%m-%d')
    dte = time.strptime(date_end, '%Y-%m-%d')
    ys, ye = dts.tm_year, dte.tm_year
    ms, me = dts.tm_mon,  dte.tm_mon
    ds, de = dts.tm_mday, dte.tm_mday

    pat = re.compile(r'^ndvi(\d+)_(\d+)')
    for filename in os.listdir(datadir):
        m = pat.search(filename)
        if m: break

    if not m: raise RuntimeError('No input files found')


    # Use input data source as template to remap mask
    m_ds = get_remapped_mask(os.path.join(datadir, filename),
                             os.path.join(permadir, mask_fname))
    mask = m_ds.ReadAsArray()
    
    ndat = np.zeros(mask.shape, dtype=np.int16)
    data = np.zeros(mask.shape, dtype=np.float64)

    for filename in os.listdir(datadir):
        m = pat.search(filename)
        if not m: continue
        ynum, dnum = map(int, m.groups())
        if ynum+2000 < ys or ynum+2000 > ye: continue
        date = dt.date(ynum+2000, 1, 1) + dt.timedelta(dnum-1)
        if date < dt.date(ynum+2000, ms, ds) or date > dt.date(ynum+2000, me, de): continue

        dds = gdal.Open(os.path.join(datadir, filename))
        ddd = dds.ReadAsArray()
        xy = np.where(ddd > 0)
        data[xy] += ddd[xy]
        ndat[xy] += 1
        LOGINFO("read file " + filename)

    avg = np.where(mask == 1, data/ndat, np.nan)

    # Create file with average
    ysize, xsize = avg.shape
    driver = gdal.GetDriverByName('GTiff')
    out = driver.Create(os.path.join(outputdir, avg_fname), xsize, ysize, 1, GDT_Float32)
    out.SetGeoTransform(dds.GetGeoTransform())
    out.SetProjection(dds.GetProjectionRef())
    out.GetRasterBand(1).WriteArray(avg.astype(np.float32))
    out = None                # Close and flush file
    return 0

def save_product(ds, outputdir, data, year, mask, fmt, prod_name, prod_description):
    ysize, xsize = data.shape

    driver = gdal.GetDriverByName(fmt)
    if fmt == 'GTiff': prod_name += '.tiff'
    elif fmt == 'ENVI': prod_name += '.dat'
    else: raise RuntimeError('Format ' + fmt + ' to be added')
    out = driver.Create(prod_name, xsize, ysize, 1, GDT_Byte)

    if mask is not None:
        data = np.where(mask == 1, data, mask)

    out.SetGeoTransform(ds.GetGeoTransform())
    out.SetProjection(ds.GetProjectionRef())
    # out.SetMetadataItem('band_names', prod_description)
    rb = out.GetRasterBand(1)
    rb.SetDescription(prod_description)
    rb.WriteArray(encode(data))
    out = None                  # Close and flush file

    # ff = file(prod_name + '.dat', 'w')
    # ff.write(data)
    # ff.close()
    # hdr['data type'] = 5      # double-float
    # hdr['interleave'] = 'bsq'
    # hdr['band names'] = ['Growth season onset']

    # dh.writeHdr(prod_name + '.hdr', hdr)
    LOGINFO("wrote " + prod_name)

def save_onset(ds, outputdir, onset, year, mask=None, fmt='GTiff'):
    GSO_name = os.path.join(outputdir, 'GS_onset_{0}'.format(2000+year))
    GSO_description = 'Growth season onset'
    save_product(ds, outputdir, onset, year, mask, fmt, GSO_name, GSO_description)

def save_peak(ds, outputdir, peak, year, mask=None, fmt='GTiff'):
    GSP_name = os.path.join(outputdir, 'GS_peak_{0}'.format(2000+year))
    GSP_description = 'Growth season peak'
    save_product(ds, outputdir, peak, year, mask, fmt, GSP_name, GSP_description)

def save_end(ds, outputdir, end, year, mask=None, fmt='GTiff'):
    GSE_name = os.path.join(outputdir, 'GS_end_{0}'.format(2000+year))
    GSE_description = 'Growth season end'
    save_product(ds, outputdir, end, year, mask, fmt, GSE_name, GSE_description)

def GS_avgpeak(avg_fname):

    gdal.UseExceptions()
    # avg_fname = 'peak_average.tiff'
    try:
      # hdr, avg = dh.read_envi(avg_fname)
      # junk = open(avg_fname, 'r')   # To provoke IOError
      ds = gdal.Open(avg_fname, GA_ReadOnly)
      avg = ds.ReadAsArray()
    except:
      return None, None

    return ds, avg

def above(datadir, outputdir, thr_scale, avg_fname):
    '''Prototype functionality for finding first day above a threshold in SenSyF S2 Service.

    datadir -- directory containing input files
    outputdir -- directory wherein to place the result files
    thr_scale -- the scaling of the average which constitutes the threshold
    avg_fname -- name of file (in permadir) where results (average) has been saved. '''

    pat = re.compile(r'ndvi(\d+)_(\d+).tiff')

    for filename in os.listdir(datadir):
        m = pat.search(filename)
        if m: break

    if not m: raise RuntimeError('No input files found')

    # Use input data source as template to remap mask
    mask_ds = get_remapped_mask(os.path.join(datadir, filename),
                                os.path.join(permadir, mask_fname))
    mask = mask_ds.ReadAsArray()
    proj = mask_ds.GetProjectionRef()
    tran = mask_ds.GetGeoTransform()

    # hdr, avg_peak = GS_avgpeak(datadir)
    ds, avg_peak = GS_avgpeak(os.path.join(outputdir, avg_fname))

    LOGINFO("Got avg_peak with shape {0} and dtype {1}".format(avg_peak.shape, avg_peak.dtype))
    thr = thr_scale * avg_peak

    if ds.GetGeoTransform() != tran \
       or avg_peak.shape != mask.shape:
            raise ValueError, "Bogus file: " + avg_fname

    files = sorted([ x for x in os.listdir(datadir) if pat.match(x) ])

    lastyear = -1
    onset = None
    oset = []
    for fn in files:
        try:
            year, dnum = map(int, pat.match(fn).groups())
        except:
            print "File {} not understood".format(fn)
            bah()
            continue

        if year != lastyear:
            if onset is not None:
                # save data
                save_onset(ds, outputdir, onset, lastyear, mask=mask)
                oset.append(onset)

            # onset = np.zeros(data.shape) + np.nan
            lastdata = None

        # Here, lastdata does not exist if this is first data set in the year
        lastyear = year

        # hdr, data = dh.read_envi(datadir + fn)
        ds = gdal.Open(os.path.join(datadir, fn), GA_ReadOnly)
        data = ds.ReadAsArray()
        # if ds.GetProjectionRef() != proj \
        if ds.GetGeoTransform() != tran \
           or data.shape != mask.shape:
                raise ValueError, "Bogus file: " + os.path.join(datadir, fn)
        # print "Read file " + fn
        if lastdata is None:
            # First dataset of year
            # onset[np.where(data > thr)] = dnum
            onset = np.where(mask == 1, np.nan, mask)
            onset = np.where(np.isnan(onset) & (data > thr), dnum, onset)
        else:
            xy = np.where((data > thr) & np.isnan(onset))
            if len(xy[0]) != 0:
                y0 = lastdata[xy]
                y1 = data[xy]
                dx = dnum - lastday
                onset[xy] = lastday + dx*((thr[xy]-y0)/(y1-y0))
        lastday = dnum
        lastdata = data

    # Done
    save_onset(ds, outputdir, onset, year, mask=mask)

    return 0

def peak(datadir, outputdir):
    '''Prototype functionality for finding day of highest value in SenSyF S2 Service.

    datadir -- directory containing input files
    outputdir -- directory wherein to place the result files.'''

    pat = re.compile(r'ndvi(\d+)_(\d+).tiff')

    for filename in os.listdir(datadir):
        m = pat.search(filename)
        if m: break

    if not m: raise RuntimeError('No input files found')

    # Use input data source as template to remap mask
    mask_ds = get_remapped_mask(os.path.join(datadir, filename),
                                os.path.join(permadir, mask_fname))
    mask = mask_ds.ReadAsArray()
    proj = mask_ds.GetProjectionRef()
    tran = mask_ds.GetGeoTransform()

    files = sorted([ x for x in os.listdir(datadir) if pat.match(x) ])

    lastyear = -1
    peak = None
    pk = []
    for fn in files:
        try:
            year, dnum = map(int, pat.match(fn).groups())
        except:
            print "File {} not understood".format(fn)
            bah()
            continue

        if year != lastyear:
            if peak is not None:
                # save data
                save_peak(ds, outputdir, peak, lastyear, mask=mask)
                pk.append(peak)

            # peak = np.zeros(data.shape) + np.nan
            peakdata = None

        # Here, lastdata does not exist if this is first data set in the year
        lastyear = year

        # hdr, data = dh.read_envi(datadir + fn)
        ds = gdal.Open(os.path.join(datadir, fn), GA_ReadOnly)
        data = ds.ReadAsArray()
        # if ds.GetProjectionRef() != proj \
        if ds.GetGeoTransform() != tran \
           or data.shape != mask.shape:
                raise ValueError, "Bogus file: peak_average.tiff"
        # print "Read file " + fn
        if peakdata is None:
            # First dataset of year
            peak = np.where(mask == 1, dnum, mask)
            peakdata = data
        else:
            xy = np.where((data > peakdata) & (mask == 1))
            if len(xy[0]) != 0:
                # TODO: fit a parabola
                peakdata[xy] = data[xy]
                peak[xy] = dnum
        # lastday = dnum
        # lastdata = data

    # Done
    save_peak(ds, outputdir, peak, year, mask=mask)

    return 0

def below(datadir, outputdir, thr_scale, date_start, date_end):
    '''Prototype functionality for finding first day below threshold
    (after peak) in SenSyF S2 Service.

    datadir -- directory containing input files
    outputdir -- directory wherein to place the result files
    thr_scale -- the scaling of the average which constitutes the threshold
    date_start -- 
    date_end -- date intervals to consider.  The day/month ranges are
         considered separately within each year, i.e.
         date_start = '2000-07-20'; date_end = '2010-08-05'
         will compute the threshold based on the average for the period July
         20th to August 5th in each year, for all years from 2000 to 2010
         (inclusive).'''

    dts = time.strptime(date_start, '%Y-%m-%d')
    dte = time.strptime(date_end, '%Y-%m-%d')
    ys, ye = dts.tm_year, dte.tm_year
    # ms, me = dts.tm_mon,  dte.tm_mon
    # ds, de = dts.tm_mday, dte.tm_mday
    dstart, dend = dts.tm_yday, dte.tm_yday

    pat = re.compile(r'^ndvi(\d+)_(\d+).tiff')
    for filename in os.listdir(datadir):
        m = pat.search(filename)
        if m: break

    if not m: raise RuntimeError('No input files found')

    # Use input data source as template to remap mask
    m_ds = get_remapped_mask(os.path.join(datadir, filename),
                             os.path.join(permadir, mask_fname))
    mask = m_ds.ReadAsArray()
    proj = m_ds.GetProjectionRef()
    tran = m_ds.GetGeoTransform()

    files = sorted([ x for x in os.listdir(datadir) if pat.match(x) ])

    lastyear = -1
    gs_end = None
    averaging = 1

    for fn in files:
        try:
            year, dnum = map(int, pat.match(fn).groups())
        except:
            print "File {} not understood".format(fn)
            bah()
            continue

        if year+2000 < ys or year+2000 > ye: continue

        if year != lastyear:
            if gs_end is not None:
                # Done
                save_end(ds, outputdir, gs_end, lastyear, mask=mask)
            peak_sum = 0 * mask
            nsets = 0
            gs_end = mask.copy()
            lastyear = year
            averaging = 1

        if dnum < dstart: continue

        ds = gdal.Open(os.path.join(datadir, fn), GA_ReadOnly)
        data = ds.ReadAsArray()

        if averaging:
            if dnum <= dend:
                peak_sum += data
                nsets += 1
                continue
            else:
                if nsets == 0: raise RuntimeError('No data in year')
                peak_average = np.where(peak_sum > 0, peak_sum / nsets, 0)
                gs_end[np.where(peak_average == 0)] = 390       # No data
                averaging = 0

        ii = np.where((gs_end == 1) & (data < thr_scale * peak_average))
        gs_end[ii] = dnum



    # Done
    save_end(ds, outputdir, gs_end, year, mask=mask)

    return 0


def usage(msg):
    print 'Usage: s2_processtile average datadir outputdir avg_fname [date_start [date_end]]'
    print 'Usage: s2_processtile above datadir outputdir thr avg_fname'
    print 'Usage: s2_processtile peak datadir outputdir'
    print 'Usage: s2_processtile below datadir outputdir thr [date_start [date_end]]'

    raise RuntimeError(msg)

def cluster_main():

    avg_fname = 'GS_avg.tiff'
    mode       = safe_getparam('mode', 'all')
    if mode != 'all': raise ValueError("Only mode 'all' implemented for now")

    o_startdate = safe_getparam('startdate-onset', '1900-07-04')
    o_enddate   = safe_getparam('enddate-onset',   '2500-08-03')
    e_startdate = safe_getparam('startdate-end',   '1925-07-20')
    e_enddate   = safe_getparam('enddate-end',     '2525-08-09')
    othreshold = float(safe_getparam('othreshold', 0.7))
    ethreshold = float(safe_getparam('ethreshold', 0.9))

    LOGINFO("Mode: " + mode)

    if 'TMPDIR' not in env: env['TMPDIR'] = '/var/tmp'
    srcdir = os.path.join(env['TMPDIR'], 'innpputs')
    dstdir = os.path.join(env['TMPDIR'], 'outputs')
    mkdir_p(srcdir)
    mkdir_p(dstdir)

    tiles = []
    for line in sys.stdin:
        cleandir(srcdir)
        tile = copy_and_unpack(line.rstrip(), srcdir)
        src_tiledir = os.path.join(srcdir, tile)
        dst_tiledir = os.path.join(dstdir, tile)
        mkdir_p(os.path.join(dst_tiledir))

        # Onset in two parts: compute average, then find when threshold is exceeded
        LOGINFO("Computing ONSET for tile " + tile)
        LOGINFO("Using dates from {0} to {1}".format(o_startdate, o_enddate))
        status = average(src_tiledir, dst_tiledir, avg_fname, o_startdate, o_enddate)
        status = above(src_tiledir, dst_tiledir, othreshold, avg_fname)

        # Peak
        LOGINFO("Computing PEAK for tile " + tile)
        status = peak(src_tiledir, dst_tiledir)

        # End
        LOGINFO("Computing END for tile " + tile)
        LOGINFO("Using dates from {0} to {1}".format(e_startdate, e_enddate))
        status = below(src_tiledir, dst_tiledir, ethreshold, e_startdate, e_enddate)

        # Rename results
        for name in os.listdir(dst_tiledir):
            if not re.match('GS_(onset|peak|end)_.*\.tiff', name): continue

            old = os.path.join(dst_tiledir, name)
            new = os.path.join(dstdir, os.path.splitext(name)[0] + '_' + tile + '.tiff')

            os.rename(old, new)
        rmtree(dst_tiledir)

	tiles.append(tile)
	LOGINFO("Completed results for tile " + tile)

    LOGINFO("Publishing results for tiles " + ", ".join(tiles))
    # publish(dstdir, recursive=True)
    publish(glob(dstdir + '/*.tiff'))

def cmdline_main(args):

    thr_scale = 0.7

    try:
        opcode = args.pop(0)
        datadir = args.pop(0)
	outputdir = args.pop(0)

        if opcode.lower() == 'average':
            date_start = '1900-07-04'   # default start Jul 4th, all years
            date_end = '2525-08-03'     # default end Aug 3rd, all years
            avg_fname = args.pop(0)
            if len(args): date_start = args.pop(0)
            if len(args): date_end = args.pop(0)
	    print opcode, datadir, outputdir, avg_fname, date_start, date_end
            return average(datadir, outputdir, avg_fname, date_start, date_end)
        elif opcode.lower() == 'above':
	    thr_scale = float(args.pop(0))
            avg_fname = args.pop(0)
	    print opcode, datadir, outputdir, thr_scale, avg_fname
            return above(datadir, outputdir, thr_scale, avg_fname)
        elif opcode.lower() == 'peak':
            return peak(datadir, outputdir)
        elif opcode.lower() == 'below':
	    thr_scale = float(args.pop(0))
            date_start = '1900-07-20'   # default start Jul 20th, all years
            date_end = '2525-08-09'     # default end Aug 5th, all years
            if len(args): date_start = args.pop(0)
            if len(args): date_end = args.pop(0)
            return below(datadir, outputdir, thr_scale, date_start, date_end)
        else:
            usage('Unknown command: ' + opcode)

    except IndexError:
        usage('Incorrect number of arguments')

if __name__ == '__main__':

    if env['USER'] != 'mapred':
        # Running from command-line
        cmdline_main(sys.argv[1:])

    else:
        # Running in cluster
        cluster_main()

    sys.exit(0)


