from glob import glob
import os

import numpy as np

datadir = os.path.join(os.path.abspath('..'), 'data')

fl = glob(os.path.join(datadir, '*.csv'))

for fname in fl:
    data = np.recfromcsv(fname)
    print data.
