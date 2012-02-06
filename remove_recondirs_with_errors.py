from glob import glob
import os
from shutil import rmtree
import subprocess

fl = sorted(glob('/g2/users/satra/ADHD200/surfaces/*/scripts/recon-all.log'))
count = 0
for filename in fl:
    status = subprocess.check_output(['tail', '-n 5', filename])
    subject = filename.split('/')[-3]
    if 'with ERRORS' in status:
        rmtree(os.path.join('/g2/users/satra/ADHD200/surfaces', subject))
    elif 'finished without' in status:
        count += 1
    else:
        print "U: %s"%subject

print "%d subjects processed without error"%count
                                        
