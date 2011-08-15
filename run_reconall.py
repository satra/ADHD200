from glob import glob
import os

import numpy as np

fl = glob('/g2/users/satra/ADHD200/testdata/*anat*.gz')

sids = [f.split('_')[0].split('/')[-1] for f in fl]

if np.prod(np.unique(sids).shape) != len(sids):
    raise Exception('Mismatch between files and subjects')

existing_sids = [path.split('/')[-1] for path in glob('/g2/users/satra/ADHD200/surfaces/*')]

newsubjects = []
newfiles = []

for idx, s in enumerate(sids):
    if s in existing_sids:
        continue
    newsubjects.append(s)
    newfiles.append(fl[idx])

#newfiles = newfiles[:5]
#newsubjects = newsubjects[:5]

print len(newfiles)
if newfiles:
    """
    os.system('/software/common/bin/recon-all-pbs -q gablab -m satrajit.ghosh@gmail.com -a "-l nodes=mh18+mh19+mh20+mh21" -s %s -f %s' % \
                  (' '.join(newsubjects), ' '.join(newfiles)))
    """
    os.system('/software/common/bin/recon-all-pbs -q gablab -m satrajit.ghosh@gmail.com -s %s -f %s' % \
                  (' '.join(newsubjects), ' '.join(newfiles)))

