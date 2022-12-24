
from __future__ import print_function

import os
import sys
import glob
import logging
import subprocess

from builtins import str as text

from pyclibrary import CParser

__all__ = ['MID','CC','MSG']


class MessageIDDB(object):
    """Message ID Database"""
    def __init__(self):
        self._fw = {}
        self._inv = {}

    def add(self,name,mid):
        if name in self._fw:
            print('WARNING: {} already defined as {}'.format(name,
                self._fw[name]))
        self._fw[name] = mid
        self._inv[mid] = name
        setattr(self,name,mid)

    def inv(self,mid):
        return self._inv.get(mid,None)

class CommandCodeDB(object):
    """Command Code Database"""
    def __init__(self):
        self._fw = {}

    def add(self,name,cc):
        if name in self._fw:
            print('WARNING: {} already defined as {}'.format(name,
                self._fw[name]))
        self._fw[name] = cc
        setattr(self,name,cc)

    def inv(self,cc):
        return [(k,v) for k,v in self._fw.items() if v == cc]

class MessageStructDB(object):
    """Message Struct Database"""
    def __init__(self):
        self._fw = {}

    def add(self,name,spec):
        if name in self._fw:
            print('WARNING: {} already defined as {}'.format(name,
                self._fw[name]))
        self._fw[name] = spec
        setattr(self,name,spec)


def load_headers(headers, verbose=False, cache_file_path=None):
    """
    load data from a set of cFS message / id headers
    """
    print("Loading definitions from headers:")
    for header in headers:
        print(" - {}".format(header))

    logging.basicConfig()
    logging.getLogger('pyclibrary.c_parser').setLevel(logging.INFO)
    logging.getLogger('c_parser').setLevel(logging.INFO)

    if cache_file_path:
        parser = CParser(headers, process_all=False, cache=text(cache_file_path))
    else:
        parser = CParser(headers, process_all=False)

    parser.process_all(cache=text(cache_file_path),
            print_after_preprocess=False)

    mid = MessageIDDB()
    cc = CommandCodeDB()
    msg = MessageStructDB()

    for k,v in parser.defs['values'].items():
        if k.endswith('_MID'):
            mid.add(k,v)
        if k.endswith('_CC'):
            cc.add(k,v)

    for k,v in parser.defs['types'].items():

        struct_name = v.type_spec.split(' ')

        if len(struct_name) == 2:
            if struct_name[1] in parser.defs['structs']:
                struct_data = parser.defs['structs'][struct_name[1]]
                msg.add( k, struct_data)
        else:
            msg.add(k, v.type_spec)

    if verbose:
        print('Loaded MIDs:')
        for k in sorted(dir(mid)):
            if not k.startswith('_'):
                print(' - {}'.format(k))

        print('Loaded CCs:')
        for k in sorted(dir(cc)):
            if not k.startswith('_'):
                print(' - {}'.format(k))

        print('Loaded message structures:')
        for k in sorted(dir(msg)):
            if not k.startswith('_'):
                print(' - {}'.format(k))

    return (mid,cc,msg,parser)

def load_bundle(bundle_path, mission, target, apps, verbose=False, use_cache=False):
    # get the bundle
    if bundle_path is None:
        bundle_path = os.getcwd()

    # Stable order to avoid unnecessary reloading
    apps = sorted(apps)

    # get the mission
    if mission is None:

        mission_directories = sorted(
                glob.glob(os.path.join(bundle_path,'*_defs')))
        if len(mission_directories) > 0:
            mission = os.path.basename(
                    mission_directories[0]).replace('_defs','')

        mission = os.environ.get('MISSIONCONFIG',mission)

    if mission is None:
        print("Could not determine mission.")
        sys.exit(1)

    # Get mission headers
    mission_dir = os.path.join(bundle_path,mission+'_defs')
    mission_cfg = '{}_mission_cfg.h'.format(mission)

    headers = [
            os.path.join(mission_dir,mission_cfg),
            ]

    # Get target headers
    msgids_paths = []
    if target is not None:
        msgids_paths.append(os.path.join(mission_dir,'{}_msgids.h'.format(target)))
    msgids_paths.append(os.path.join(mission_dir,'cfe_msgids.h'.format(target)))

    for path in msgids_paths:
        if os.path.exists(path):
            headers.append(path)
            break

    headers.append(os.path.join(bundle_path,'cfe','modules','core_api','fsw','inc','cfe_es_extern_typedefs.h'))
    headers.append(os.path.join(bundle_path,'cfe','modules','core_api','fsw','inc','cfe_evs_extern_typedefs.h'))
    headers.append(os.path.join(bundle_path,'cfe','modules','core_api','fsw','inc','cfe_tbl_extern_typedefs.h'))
    headers.append(os.path.join(bundle_path,'cfe','modules','core_api','fsw','inc','cfe_sb_extern_typedefs.h'))
    headers.append(os.path.join(bundle_path,'cfe','modules','core_api','fsw','inc','cfe_sb.h'))

    # Get app headers
    search_paths = (
            [os.path.join(bundle_path,'apps',app,'fsw') for app in apps] +
            [os.path.join(bundle_path,'cfe','modules')])
    for path in search_paths:
        for root, dirs, files in os.walk(path):
            for filename in files:
                if filename.endswith('.h') and ('msg' in filename or 'perfids' in filename):
                    headers.append(os.path.join(root,filename))

    # Define cache directory
    cache_path = os.path.join(
            mission_dir,
            '{}-pycfs.cache'.format(target))
    print("Using cache path: {}".format(cache_path))
    try:
        os.makedirs(cache_path)
    except:
        pass

    if use_cache:
        cache_file_path = os.path.join(cache_path,'cache')
    else:
        cache_file_path = None

    include_paths = [['-I',os.path.dirname(h)] for h in headers]
    for root, dirs, files in os.walk(os.path.join(bundle_path,'build',mission)):
        for dirname in dirs:
            if dirname == 'inc':
                include_paths.append(['-I',os.path.join(root,dirname)])
    include_args = (
            [i for l in include_paths for i in l]
            +['-I',os.path.join(bundle_path,'psp','fsw','inc')]
            +['-I',os.path.join(bundle_path,'osal','src','os','inc')]
            +['-I',os.path.join(bundle_path,'osal','ut_assert','inc')]
            +['-I',os.path.join(bundle_path,'cfe','cmake','target','inc')]
            +['-I',os.path.join(bundle_path,'cfe','modules','core_api','fsw','inc')]
            +['-I',os.path.join(bundle_path,'cfe','modules','msg','fsw','inc')]
            +['-I',os.path.join(bundle_path,'build','inc')]
            +['-I',os.path.join(bundle_path,'build','native','default_cpu1','inc')]   # Hacky Fix. Pls change this line to be compatible across targets.
            +['-I',mission_dir])

    # For each header, run `gcc -E` to get preproc output (processing #include
    # directives etc)
    processed_headers = []
    for header in headers:
        processed_header = os.path.join(cache_path, header[1:])
        processed_header_defines = os.path.join(cache_path, header[1:]+'.def')
        processed_header_expanded = os.path.join(cache_path, header[1:]+'.exp')

        cache_exists = os.path.exists(cache_file_path)
        processed_header_exists = os.path.exists(processed_header)
        processed_header_out_of_date = (
                processed_header_exists
                and os.path.getmtime(processed_header) < os.path.getmtime(header))

        if not cache_exists or not processed_header_exists or processed_header_out_of_date:
            print('Preprocessing {}'.format(header))

            lines = []
            try:
                os.makedirs(os.path.dirname(processed_header))
            except:
                pass

            # Get #defines
            cmd = ([
                'gcc',
                '-fdirectives-only', # preserve #define directives
                '-E',header]
                +include_args
                +['-o',processed_header_defines
                ])
            subprocess.call(cmd)

            # remove included definitions from header preproc output
            # see: https://gcc.gnu.org/onlinedocs/cpp/Preprocessor-Output.html
            with open(processed_header_defines,'r') as proc_header_file_in:
                for i,line in enumerate(proc_header_file_in):
                    if (line.lower().startswith('#define')
                            and ' __' not in line
                            and 'ARGCHECK' not in line
                            and 'CFE_ES_DTEST' not in line
                            ):
                        lines.append(line)

            # Get expanded structs
            cmd = ([
                'gcc',
                '-E',header]
                +include_args
                +['-o',processed_header_expanded
                ])
            subprocess.call(cmd)

            # remove included definitions from header preproc output
            # see: https://gcc.gnu.org/onlinedocs/cpp/Preprocessor-Output.html
            with open(processed_header_expanded,'r') as proc_header_file_in:
                keep = True
                for i,line in enumerate(proc_header_file_in):
                    if line.strip().startswith('# '):
                        if line.strip().endswith('2'):
                            if header in line:
                                keep = True
                        elif line.strip().endswith('1'):
                            keep = False

                        # Drop the preproc linemarker
                        continue

                    if keep:
                        lines.append(line)

            print('Got {} lines for header {} / {}'.format(len(lines),header,processed_header))

            with open(processed_header,'w') as proc_header_file_out:
                for line in lines:
                    proc_header_file_out.write(line)

        processed_headers.append(processed_header)

    return load_headers(processed_headers, verbose=verbose, cache_file_path=cache_file_path)

