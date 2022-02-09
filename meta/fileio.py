import os
import sys
import h5py
import argparse
import datetime

import pandas as pd
# import dxchange.reader as dxreader
from collections import OrderedDict, deque

from pathlib import Path

from meta import log
from meta import utils

PIPE = "│"
ELBOW = "└──"
TEE = "├──"
PIPE_PREFIX = "│   "
SPACE_PREFIX = "    "

def read_dx_meta(fname, output=None, add_shape=True):
    """
    Get the tree view of a hdf/nxs file.

    Parameters
    ----------
    file_path : str
        Path to the file.
    output : str or None
        Path to the output file in a text-format file (.txt, .md,...).
    add_shape : bool
        Including the shape of a dataset to the tree if True.

    Returns
    -------
    list of string
    """

    file_path = fname
    hdf_object = h5py.File(file_path, 'r')
    tree = deque()
    meta = {}
    _make_tree_body(tree, meta, hdf_object, add_shape=add_shape)
    # for entry in tree:
    #     print(entry)
    return tree, meta

def _get_subgroups(hdf_object, key=None):
    """
    Supplementary method for building the tree view of a hdf5 file.
    Return the name of subgroups.
    """
    list_group = []
    if key is None:
        for group in hdf_object.keys():
            list_group.append(group)
        if len(list_group) == 1:
            key = list_group[0]
        else:
            key = ""
    else:
        if key in hdf_object:
            try:
                obj = hdf_object[key]
                if isinstance(obj, h5py.Group):
                    for group in hdf_object[key].keys():
                        list_group.append(group)
            except KeyError:
                pass
    if len(list_group) > 0:
        list_group = sorted(list_group)
    return list_group, key

def _add_branches(tree, meta, hdf_object, key, key1, index, last_index, prefix,
                  connector, level, add_shape):
    """
    Supplementary method for building the tree view of a hdf5 file.
    Add branches to the tree.
    """
    shape = None
    key_comb = key + "/" + key1
    if add_shape is True:
        if key_comb in hdf_object:
            try:
                obj = hdf_object[key_comb]
                if isinstance(obj, h5py.Dataset):
                    shape = str(obj.shape)
                    if obj.shape[0]==1:
                        s = obj.name.split('/')
                        name = "_".join(s)[1:]
                        # print(s)
                        # print(name)
                        value = obj[()][0]
                        attr = obj.attrs.get('units')
                        if attr != None:
                            attr = attr.decode('UTF-8')
                            # log.info(">>>>>> %s: %s %s" % (obj.name, value, attr))
                        if  (value.dtype.kind == 'S'):
                            value = value.decode(encoding="utf-8")
                            # log.info(">>>>>> %s: %s" % (obj.name, value))
                        meta.update( {name : [value, attr] } )
            except KeyError:
                shape = str("-> ???External-link???")
    if shape is not None:
        tree.append(f"{prefix}{connector} {key1} {shape}")
    else:
        tree.append(f"{prefix}{connector} {key1}")
    if index != last_index:
        prefix += PIPE_PREFIX
    else:
        prefix += SPACE_PREFIX
    _make_tree_body(tree, meta, hdf_object, prefix=prefix, key=key_comb,
                    level=level, add_shape=add_shape)

def _make_tree_body(tree, meta, hdf_object, prefix="", key=None, level=0,
                    add_shape=True):
    """
    Supplementary method for building the tree view of a hdf5 file.
    Create the tree body.
    """
    entries, key = _get_subgroups(hdf_object, key)
    num_ent = len(entries)
    last_index = num_ent - 1
    level = level + 1
    if num_ent > 0:
        if last_index == 0:
            key = "" if level == 1 else key
            if num_ent > 1:
                connector = PIPE
            else:
                connector = ELBOW if level > 1 else ""
            _add_branches(tree, meta, hdf_object, key, entries[0], 0, 0, prefix,
                          connector, level, add_shape)
        else:
            for index, key1 in enumerate(entries):
                connector = ELBOW if index == last_index else TEE
                if index == 0:
                    tree.append(prefix + PIPE)
                _add_branches(tree, meta, hdf_object, key, key1, index, last_index,
                              prefix, connector, level, add_shape)

# #####################################################################################
def create_rst_file(args):
    
    meta, year_month, pi_name = extract_meta(args)

    decorator = '='
    if os.path.isdir(args.doc_dir):
        log_fname = os.path.join(args.doc_dir, 'log_' + year_month + '.rst')

    with open(log_fname, 'a') as f:
        if f.tell() == 0:
            # a new file or the file was empty
            f.write(utils.add_header(year_month))
            f.write(utils.add_title(pi_name))
        else:
            #  file existed, appending
            f.write(utils.add_title(pi_name))
        f.write('\n')        
        f.write(meta)        
        f.write('\n\n')        
    log.warning('Please copy/paste the content of %s in your rst docs file' % (log_fname))

def extract_meta(args):

    list_to_extract = ('measurement_instrument_monochromator_energy', 
                    'measurement_sample_experimenter_email',
                    'measurement_instrument_sample_motor_stack_setup_sample_x', 
                    'measurement_instrument_sample_motor_stack_setup_sample_y'
                    )

    # set pandas display
    pd.options.display.max_rows = 999
    year_month = 'unknown'
    pi_name    = 'unknown'
    fname      = args.h5_name

    if os.path.isfile(fname): 
        meta_dict, year_month, pi_name = extract_dict(fname, list_to_extract)
        # print (meta_dict, year_month, pi_name)
    elif os.path.isdir(fname):
        # Add a trailing slash if missing
        top = os.path.join(fname, '')
        # Set the file name that will store the rotation axis positions.
        h5_file_list = list(filter(lambda x: x.endswith(('.h5', '.hdf')), os.listdir(top)))
        h5_file_list.sort()
        meta_dict = {}
        file_counter=0
        for fname in h5_file_list:
            h5fname = top + fname
            sub_dict, year_month, pi_name = extract_dict(h5fname, list_to_extract, index=file_counter)
            meta_dict.update(sub_dict)
            file_counter+=1
        if year_month == 'unknown':
            log.error('No valid HDF5 file(s) fund in the directory %s' % top)
            log.warning('Make sure to use the --h5-name H5_NAME  option to select  the hdf5 file or directory containing multiple hdf5 files')
            return None
           
    else:
        log.error('No valid HDF5 file(s) fund')
        return None

    df = pd.DataFrame.from_dict(meta_dict, orient='index', columns=('value', 'unit'))
    return df.to_markdown(tablefmt='grid'), year_month, pi_name

def extract_dict(fname, list_to_extract, index=0):

    tree, meta = read_dx_meta(fname)

    start_date     = 'process_acquisition_start_date'
    experimenter   = 'measurement_sample_experimenter_name'
    full_file_name = 'measurement_sample_full_file_name'

    try: 
        dt = datetime.datetime.strptime(meta[start_date][0], "%Y-%m-%dT%H:%M:%S%z")
        year_month = str(dt.year) + '-' + '{:02d}'.format(dt.month)
    except ValueError:
        log.error("The start date information is missing from the hdf file %s. Error (2020-01)." % fname)
        year_month = '2020-01'
    except TypeError:
        log.error("The start date information is missing from the hdf file %s. Error (2020-02)." % fname)
        year_month = '2020-02'
    try:
        pi_name = meta[experimenter][0]
    except KeyError:
        log.error("The experimenter name is missing from the hdf file %s." % fname)
        pi_name = 'Unknownxx'
    try:    
        # compact full_file_name to file name only as original data collection directory may have changed
        meta[full_file_name][0] = os.path.basename(meta[full_file_name][0])
    except KeyError:
        log.error("The full file name is missing from the hdf file %s." % fname)

    sub_dict = {(('%3.3d' % index) +'_' + k):v for k, v in meta.items() if k in list_to_extract}

    return sub_dict, year_month, pi_name