"""Creates a Windows installer for fief.  This requires that NSIS and Python 
already be installed on the system and a fairly solid internet connection.
"""
import os
import sys
import shutil
import urllib
cwd = os.getcwd()
if cwd not in sys.path:
    sys.path.insert(0, cwd)

import urllib
import subprocess
from zipfile import ZipFile

BOOTSTRAP = os.path.split(__file__)[0]
BUILD = os.path.abspath('build')
DOWNLOADS = os.path.join(BUILD, 'downloads')
FIEF = os.path.join(BUILD, 'fief')

MINGW_GET_URL = 'http://sourceforge.net/projects/mingw/files/Installer/mingw-get/mingw-get-0.5-beta-20120426-1/mingw-get-0.5-mingw32-beta-20120426-1-bin.zip/download'
PYTHON_URL = 'http://www.python.org/ftp/python/2.7.3/python-2.7.3.msi'

MAKENSIS = os.path.join('C:\\', 'Program Files', 'NSIS', 'makensis.exe')

def retrieve_http(url, filename, tag=None):
    def hook(nblks, bytes_per_blk, fsize):
        r = min(max(3, int(fsize/1048576)), 1000) 
        totblks = 1 + fsize / bytes_per_blk
        if not (0 == nblks%(totblks/r) or totblks == nblks):
            return 
        msg = '[GET' + ('] ' if tag is None else ': {0}] '.format(tag))
        if nblks == 0:
            msg += 'downloading {0} -> {1}\n'.format(url, filename)
        else:
            msg += '{0:.1%} completed\n'.format(nblks / float(totblks))
        sys.stderr.write(msg)
    
    def retriever():
        try:
            dname = os.path.split(filename)[0]
            if not os.path.exists(dname):
                os.makedirs(dname)
            fname, hdrs = urllib.urlretrieve(url, filename, hook)
            got = True
        except urllib.ContentTooShortError:
            got = False
        return got

    return retriever

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

def dirsize(d):
    """Recussively computes the size in bytes of a directory."""
    size = 0
    for (path, dirs, files) in os.walk(d):
        for f in files:
            filename = os.path.join(path, f)
            size += os.path.getsize(filename)
    return size

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
    rtn = subprocess.call(['msiexec.exe', '/qn', '/x', msipath,])
    rtn = subprocess.check_call(['msiexec.exe', '/qn', 
                                 '/i', msipath,   
                                 'TARGETDIR={0}'.format(FIEF), 'ADDLOCAL=ALL'])
    # patch up python to use mingw by default
    dudir = os.path.join(FIEF, 'lib', 'distutils')
    with open(os.path.join(dudir, 'distutils.cfg'), 'w') as f:
        f.write('[build]\ncompiler=mingw32\n')
    with open(os.path.join(dudir, 'cygwinccompiler.py'), 'r') as f:
        ccc = f.read()
    ccc = ccc.replace(' -mno-cygwin', '')
    with open(os.path.join(dudir, 'cygwinccompiler.py'), 'w') as f:
        f.write(ccc)

def fief_install():
    pypath = os.path.join(FIEF, 'python.exe')
    rtn = subprocess.call([pypath, 'setup.py', 'install', 
                           '--install-scripts={0}'.format(os.path.join(FIEF, 'bin'))])

FIEF_NSI_TEMPLATE = """# This creates an installer for the fief environment.
# This is based off of the example found at http://nsis.sourceforge.net/A_simple_installer_with_start_menu_shortcut_and_uninstaller

!include EnvVarUpdate.nsh
 
!define APPNAME "fief"
!define COMPANYNAME "John Bachan, Anthony Scopatz"
!define DESCRIPTION "the user-developer package manager"

# These three must be integers
!define VERSIONMAJOR {version_major}
!define VERSIONMINOR {version_minor}
!define VERSIONBUILD {version_micro}

# These will be displayed by the "Click here for support information" link in "Add/Remove Programs"
# It is possible to use "mailto:" links in here to open the email client
!define HELPURL "https://github.com/scopatz/fief" # "Support Information" link
!define UPDATEURL "https://github.com/scopatz/fief" # "Product Updates" link
!define ABOUTURL "https://github.com/scopatz/fief" # "Publisher" link

# This is the size (in kB) of all the files copied into "Program Files"
!define INSTALLSIZE {installsize}
  
InstallDir "C:\\${{APPNAME}}"
 
# rtf or txt file - remember if it is txt, it must be in the DOS text format (\\r\\n)
LicenseData "license.rtf"
LicenseBkColor /windows
# This will be in the installer/uninstaller's title bar
Name "${{COMPANYNAME}} - ${{APPNAME}}"
#Icon "logo.ico"
outFile "${{APPNAME}}-install.exe"
# Set zip info
SetCompressor /FINAL lzma
XPStyle on
AutoCloseWindow true
BrandingText "by John Bachan and Anthony Scopatz"
 
!include LogicLib.nsh
 
# Just three pages - license agreement, install location, and installation
page license
page directory
page instfiles
 
function .onInit
	setShellVarContext all
    SetAutoClose true
functionEnd
 
section "install"
	# Files for the install directory - to build the installer, these should be in 
    # the same directory as the install script (this file)
	setOutPath $INSTDIR
	file /r "fief\\*"
    
    # Set environment variables
    ${{EnvVarUpdate}} $0 "PATH" "P" "HKCU" "$INSTDIR" 
    ${{EnvVarUpdate}} $0 "PATH" "P" "HKCU" "$INSTDIR\\bin"
    ${{EnvVarUpdate}} $0 "PATH" "P" "HKCU" "$INSTDIR\\msys\\1.0\\bin"
    
	# Uninstaller - See function un.onInit and section "uninstall" for configuration
	writeUninstaller "$INSTDIR\${{APPNAME}}-uninstall.exe"
sectionEnd
 
# Uninstaller
function un.onInit
	SetShellVarContext all
    SetAutoClose true
 
	#Verify the uninstaller - last chance to back out
	MessageBox MB_OKCANCEL "Permanantly remove ${{APPNAME}}?" IDOK next
		Abort
	next:
functionEnd
 
section "uninstall"
    # Remove environment variables
    ${{un.EnvVarUpdate}} $0 "PATH" "R" "HKCU" "$INSTDIR" 
    ${{un.EnvVarUpdate}} $0 "PATH" "R" "HKCU" "$INSTDIR\\bin"
    ${{un.EnvVarUpdate}} $0 "PATH" "R" "HKCU" "$INSTDIR\msys\\1.0\\bin"

	# Remove files, somewhat dangerously
	rmdir /r $INSTDIR
 
    # a safe, less complete way is here.
    #delete $INSTDIR\\*
	#delete $INSTDIR\uninstall.exe  # Always delete uninstaller as the last action
	#rmDir $INSTDIR # Try to remove the install directory - this will only happen if it is empty
sectionEnd
"""
                           
def run_nsis():
    shutil.copyfile(os.path.join(BOOTSTRAP, 'license.rtf'), 
                    os.path.join(BUILD, 'license.rtf'))
    shutil.copyfile(os.path.join(BOOTSTRAP, 'EnvVarUpdate.nsh'), 
                    os.path.join(BUILD, 'EnvVarUpdate.nsh'))
    installsize = dirsize(FIEF) / 1024  # size in kB 
    nsikw = {'version_major': 0, 'version_minor': 1, 'version_micro': 0,
             'installsize': installsize}
    fief_nsi = FIEF_NSI_TEMPLATE.format(**nsikw)
    nsipath = os.path.join(BUILD, 'fief.nsi')
    with open(nsipath, 'w') as f:
        f.write(fief_nsi)
    rtn = subprocess.check_call([MAKENSIS, nsipath])
    
def main():
    setup()
    mingw_install()
    python_install()
    fief_install()
    run_nsis()

if __name__ == '__main__':
    main()
