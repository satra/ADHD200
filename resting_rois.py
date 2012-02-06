import os
from glob import glob

import numpy as np

import nipype.pipeline.engine as pe
import nipype.interfaces.freesurfer as fs
import nipype.interfaces.io as nio
import nipype.interfaces.utility as niu
from nipype.workflows.freesurfer.utils import create_get_stats_flow


basedir = '/g2/users/satra/ADHD200'
datadir = os.path.join(basedir, 'preproc')
surfacedir = os.path.join(basedir, 'surfaces')

subjects = []
for fname in sorted(glob(os.path.join(datadir, '*'))):
    if not os.path.islink(fname):
        subject_id = fname.split('/')[-1]
        subjects.append(subject_id)

roiproc = pe.Workflow(name='adhd200rois')

inputnode = pe.Node(niu.IdentityInterface(fields=['subject_id']),
                    name='inputspec')
inputnode.iterables = ('subject_id', subjects)

datasource = pe.Node(nio.DataGrabber(infields=['subject_id'],
                                     outfields=['filtered_func',
                                                'mean_image']),
                     name='datasource')
datasource.inputs.base_directory = datadir
datasource.inputs.template = '%s/*%s.nii.gz'
datasource.inputs.template_args = dict(filtered_func=[['subject_id', 'filtered']],
                                       mean_image=[['subject_id', 'mean']])

roiproc.connect(inputnode, 'subject_id', datasource, 'subject_id')

fssource = pe.Node(nio.FreeSurferSource(),
                   name = 'fssource')
fssource.inputs.subjects_dir = surfacedir

register = pe.Node(fs.BBRegister(init='fsl', contrast_type='t2'),
                      name='register')
register.inputs.subjects_dir = surfacedir

voltransform = pe.Node(fs.ApplyVolTransform(inverse=True, interp='nearest'),
                          name='transform')
voltransform.inputs.subjects_dir = surfacedir

def choose_aseg(aparc_files):
    for fname in aparc_files:
        if 'aparc+aseg' in fname:
            return fname
    raise ValueError('No aparc+aseg file found')

"""
Connect the nodes
"""

roiproc.connect([
        (inputnode, fssource, [('subject_id','subject_id')]),
        (inputnode, register, [('subject_id', 'subject_id')]),
        (datasource, register, [('mean_image', 'source_file')]),
        (datasource, voltransform, [('mean_image', 'source_file')]),
        (register, voltransform, [('out_reg_file','reg_file')]),
        (fssource, voltransform, [(('aparc_aseg', choose_aseg),'target_file')])
        ])


statsflow = create_get_stats_flow()

roiproc.connect(voltransform, 'transformed_file', statsflow, 'inputspec.label_file')
roiproc.connect(datasource, 'filtered_func', statsflow, 'inputspec.source_file')

statsflow.inputs.segstats.avgwf_txt_file = True

def strip_ids(subject_id, summary_file, roi_file):
    import numpy as np
    import os
    roi_idx = np.genfromtxt(summary_file[0])[:,1].astype(int)
    roi_vals = np.genfromtxt(roi_file[0])
    rois2skip = [0, 2, 4, 5, 7, 14, 15, 24, 30, 31, 41, 43, 44, 46,
                 62, 63, 77, 80, 85, 1000, 2000]
    ids2remove = []
    for roi in rois2skip:
        idx, = np.nonzero(roi_idx==roi)
        ids2remove.extend(idx)
    ids2keep = np.setdiff1d(range(roi_idx.shape[0]), ids2remove)
    filename = os.path.join(os.getcwd(), subject_id+'.csv')
    newvals = np.vstack((roi_idx[ids2keep], roi_vals[:, np.array(ids2keep)])).T
    np.savetxt(filename, newvals, '%.4f', delimiter=',')
    return filename

roistripper = pe.Node(niu.Function(input_names=['subject_id', 'summary_file', 'roi_file'],
                                   output_names=['roi_file'],
                                   function=strip_ids),
                      name='roistripper')
roiproc.connect(inputnode, 'subject_id', roistripper, 'subject_id')
roiproc.connect(statsflow, 'segstats.avgwf_txt_file', roistripper, 'roi_file')
roiproc.connect(statsflow, 'segstats.summary_file', roistripper, 'summary_file')

datasink = pe.Node(nio.DataSink(parameterization=False), name='sinker')

datasink.inputs.base_directory = os.path.join(basedir, 'rois')
roiproc.connect(inputnode, 'subject_id', datasink, 'container')
roiproc.connect(register, 'out_reg_file', datasink, '@reg_file')
roiproc.connect(register, 'min_cost_file', datasink, '@cost_file')
roiproc.connect(statsflow, 'segstats.avgwf_txt_file', datasink, '@avgwftxt')
roiproc.connect(statsflow, 'segstats.summary_file', datasink, '@summarytxt')
roiproc.connect(roistripper, 'roi_file', datasink, '@strippedroi')
roiproc.connect(voltransform, 'transformed_file', datasink, '@transform')

datasink2 = pe.Node(nio.DataSink(parameterization=False), name='sinker2')
datasink2.inputs.base_directory = os.path.join(basedir, 'homology_workdir', 'input')
roiproc.connect(roistripper, 'roi_file', datasink2, '@strippedroi')

def get_substitutions(subject_id):
    subs = [('_%s.dat'%subject_id, '.dat'),
        ('aparc+aseg_warped_avgwf','%s_roi'%subject_id),
        ('aparc+aseg_warped','%s_labels'%subject_id)
        ]
    return subs
roiproc.connect(inputnode, ('subject_id', get_substitutions), datasink, 'substitutions')

roiproc.base_dir = os.path.join(basedir, 'working')
#roiproc.config = {'execution': {'stop_on_first_crash' : True}}
#roiproc.run('MultiProc', plugin_args={'n_procs' : 4})
roiproc.run('PBS', plugin_args={'qsub_args' : '-o /dev/null -e /dev/null'})
