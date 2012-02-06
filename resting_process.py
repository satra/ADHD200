import os
from glob import glob
import sys

#sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

import numpy as np

#from nipype.utils.config import config
#config.enable_debug_mode()

import nipype.pipeline.engine as pe
import nipype.interfaces.fsl as fsl
import nipype.interfaces.io as nio
import nipype.interfaces.utility as niu
from nipype.workflows.fsl import create_resting_preproc


basedir = '/g2/users/satra/ADHD200'
subject_type = 'train'
datadir = os.path.join(basedir, '%sdata'%subject_type)

data = np.recfromcsv(os.path.join(basedir, 'scripts',
                                  'adhd-200_scanner_parameters.csv'),
                     skip_header=1)
site_map = dict(zip(data.site_id, zip(data.f_tr_ms/1000.,
                                data.slice_acquisition_order_phase_encoding_direction)))

subject_map = dict(np.recfromcsv(os.path.join(basedir, 'scripts',
                                             'adhd_subjects_%s.csv'%subject_type),
                                usecols=[0,1]))
print subject_map

subjects = []
for fname in sorted(glob(os.path.join(basedir, 'surfaces', '*'))):
    if not os.path.islink(fname):
        subject_id = fname.split('/')[-1]
        if int(subject_id) in subject_map and \
            os.path.exists(os.path.join(datadir, '%s_rest_1.nii.gz'%subject_id)):
            subjects.append(subject_id)

#subjects = ['9956994']
#print subjects

def get_sequence_info(subject_id, filename, subject_map, site_map):
    """Get sequence related info
    """
    from nibabel import load
    import numpy as np
    import os
    site_id = subject_map[int(subject_id)]
    TR = site_map[site_id][0]
    img = load(filename)
    _,_,nslices,_ = img.get_shape()
    if site_map[site_id][1].startswith('seq'):
        order = range(nslices)
    else:
        """Siemens scanners, you _can_ always know the slice order by looking
        at the protocol under "Slice _Series_Order": ascending (1,2,3,...,Nz-1,
        Nz), descending (Nz,Nz-1,...,3,2,1) or interleaved (1,3,5,...,Nz, 2, 4
        ..., Nz-1 for odd number of slices, or 2,4,6,...,Nz, 1,3,5,...,Nz-1 for
        even number of slices). The indices refer to the slice number in the
        file: so the first slice in the file is what we are calling "1", the
        second is called "2", etc."
        """
        order = np.concatenate((np.arange((nslices+1)%2, nslices, 2)+1,
                                np.arange(nslices%2, nslices, 2)+1)).tolist()
    order_file = os.path.abspath('custom_file_%s.txt'%subject_id)
    np.savetxt(order_file, order, '%d')
    return TR, order_file

preproc = pe.Workflow(name='adhd200rest')

inputnode = pe.Node(niu.IdentityInterface(fields=['subject_id']),
                    name='inputspec')
inputnode.iterables = ('subject_id', subjects)

datasource = pe.Node(nio.DataGrabber(infields=['subject_id'],
                                     outfields=['funcfile']),
                     name='datasource')
datasource.inputs.base_directory = datadir
datasource.inputs.template = '%s_rest_1.nii.gz'

getinfo = pe.Node(niu.Function(input_names=['subject_id', 'filename',
                                            'subject_map','site_map'],
                               output_names=['TR', 'slice_order'],
                               function=get_sequence_info),
                  name='getinfo')
getinfo.inputs.subject_map = subject_map
getinfo.inputs.site_map = site_map


preproc.connect(inputnode, 'subject_id', datasource, 'subject_id')
preproc.connect(inputnode, 'subject_id', getinfo, 'subject_id')

restflow = create_resting_preproc()
restflow.inputs.inputspec.num_noise_components = 6

def get_sigma(TR):
    return 10./(2*TR), .1/(2*TR)

sigma_node = pe.Node(niu.Function(input_names=['TR'],
                                  output_names=['low_sigma', 'high_sigma'],
                                  function=get_sigma),
                     name='getsigma')

preproc.connect(datasource, 'funcfile', getinfo, 'filename')
preproc.connect(datasource, 'funcfile', restflow, 'inputspec.func')
preproc.connect(getinfo, 'TR', sigma_node, 'TR')
preproc.connect(sigma_node, 'low_sigma', restflow, 'inputspec.lowpass_sigma')
preproc.connect(sigma_node, 'high_sigma', restflow, 'inputspec.highpass_sigma')
preproc.connect(getinfo, 'TR', restflow, 'slicetimer.time_repetition')
preproc.connect(getinfo, 'slice_order', restflow, 'slicetimer.custom_order')

get_mean = pe.Node(fsl.MeanImage(dimension='T'), name='get_mean')
preproc.connect(restflow, 'realign.outputspec.realigned_file', get_mean, 'in_file')

datasink = pe.Node(nio.DataSink(parameterization=False), name='sinker')

datasink.inputs.base_directory = os.path.join(basedir, 'preproc')
preproc.connect(inputnode, 'subject_id', datasink, 'container')
preproc.connect(get_mean, 'out_file', datasink, '@mean_image')
preproc.connect(restflow, 'outputspec.filtered_file', datasink, '@filtered')
preproc.connect(restflow, 'outputspec.noise_mask_file', datasink, '@noise')

def get_substitutions(subject_id):
    subs = [('vol0000_warp_merged_detrended_regfilt_filt', '%s_filtered'%subject_id),
        ('vol0000_warp_merged_tsnr_stddev_thresh','%s_noise_mask'%subject_id),
        ('vol0000_warp_merged_mean','%s_mean'%subject_id)
        ]
    return subs
preproc.connect(inputnode, ('subject_id', get_substitutions), datasink, 'substitutions')

preproc.base_dir = os.path.join(basedir, 'working')
#preproc.config = {'execution': {'stop_on_first_crash' : True}}
preproc.run('MultiProc', plugin_args={'n_procs' : 4})

