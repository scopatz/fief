"""Creates a Windows installer for fief.  This requires that NSIS and Python 
already be installed on the system and a fairly solid internet connection.
"""

import os
import sys
cwd = os.getcwd()
if cwd not in sys.path:
    sys.path.insert(0, cwd)

import urllib
import subprocess
from zipfile import ZipFile

from fief.fetch import retrieve_http

BUILD = os.path.abspath('build')
DOWNLOADS = os.path.join(BUILD, 'downloads')
FIEF = os.path.join(BUILD, 'fief')

MINGW_GET_URL = 'http://sourceforge.net/projects/mingw/files/Installer/mingw-get/mingw-get-0.5-beta-20120426-1/mingw-get-0.5-mingw32-beta-20120426-1-bin.zip/download'
PYTHON_URL = 'http://www.python.org/ftp/python/2.7.3/python-2.7.3.msi'

def ensure_dir(d):
    if not os.path.exists(d):
        os.mkdir(d)

def ensure_url(url, fname):
    fpath = os.path.join(DOWNLOADS, fname)
    if os.path.exists(fpath):
        return fpath
    retriever = retrieve_http(url, fpath, tag=fname)
    got = retriever()
    if not got:
        raise RuntimeError('{0} failed to download'.format(fname))
    return fpath


def setup():
    dirs = (BUILD, DOWNLOADS, FIEF)
    for d in dirs:
        ensure_dir(d)

def mingw_install():
    zippath = ensure_url(MINGW_GET_URL, 'mingw-get.zip')
    with ZipFile(zippath) as zf:
        zf.extractall(FIEF)
    exe = os.path.join(FIEF, 'bin', 'mingw-get.exe')
    rtn = subprocess.check_call([exe, 'update'])
    rtn = subprocess.check_call([exe, 'install', 'gcc', 'g++', 'fortran', 'gdb', 
                                 'mingw32-make', 'msys-base'])
								 
def python_install():
    msipath = ensure_url(PYTHON_URL, 'python-2.7.3.msi')
    # may need to be '"{0}"'.format(msipath) and 
    # 'TARGETDIR="{0}"'.format(FIEF) on some systems
    rtn = subprocess.check_call(['msiexec.exe', '/qn', 
                                 '/i', '{0}'.format(msipath),   
                                 'TARGETDIR={0}'.format(FIEF), 'ADDLOCAL=ALL'])

def fief_install():
    pypath = os.path.join(FIEF, 'python.exe')
    rtn = subprocess.call([pypath, 'setup.py', 'install', 
                           '--install-scripts={0}'.format(os.path.join(FIEF, 'bin'))])

def main():
    setup()
    mingw_install()
    python_install()
    fief_install()

if __name__ == '__main__':
    main()
