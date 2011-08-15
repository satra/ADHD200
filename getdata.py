import os
import shutil
import tarfile
import urllib

import numpy as np

sources = np.genfromtxt('alldata.urls',dtype=object).tolist()

adhddir = os.path.abspath('..')
datadir = os.path.join(adhddir, 'data')
traindatadir = os.path.join(adhddir, 'traindata')
testdatadir = os.path.join(adhddir, 'testdata')

for source in sources:
    filename = source.split('/')[-1]
    output = os.path.join(datadir, filename)
    if not os.path.exists(output):
        print "Retrieving %s"%source
        urllib.URLopener().retrieve(source, output)

for source in sources:
    if 'tar.gz' in source and 'Combined_T' not in source:
        filename = source.split('/')[-1]
        location = os.path.join(datadir, filename)
        try:
            tar = tarfile.open(location, mode='r')
        except Exception, e:
            print "Error", location, e
            continue
        for name in tar.getnames():
            if 'gz' in name:
                src, id = name.split('/')[0:2]
                scantype = name.split('/')[-2]
                outfile = '_'.join((id, '%s.nii.gz'%scantype))
                if 'TestRelease' in source:
                    outfile = os.path.join(testdatadir, outfile)
                else:
                    outfile = os.path.join(traindatadir, outfile)
                if not os.path.exists(outfile):
                    print id, name, outfile
                    print "Extracting..."
                    tar.extract(name, '/tmp')
                    shutil.move(os.path.join('/tmp', name),
                                outfile)

