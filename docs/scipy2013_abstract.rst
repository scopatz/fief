SciPy 2013 Abstract
===================

:title: But How Do It Package? Lessons Learned From Fief

:author: Scopatz, Anthony, The University of Chicago & NumFOCUS, Inc;

:bio: Anthony Scopatz is a Research Scientist at the FLASH Center at the
      University of Chicago as well as being the treasurer for NumFOCUS.
      With interests spanning the domains of science and computation,
      Anthony is guaranteed to deliver.      

:email: scopatz@gmail.com

:talk summary: Packaging scientific software across the spectrum is and awful mess.
    This talk is a plea in the form of a rant masquerading as a call-to-action.  It 
    will deliver my thoughts, concerns, and requirements for the current state of the
    art.  This talk will serve as a vehicle to discuss the numerous lessons learned 
    during the ongoing attempt to write fief.

    First, I draw the hard distinction between two related solutions: package 
    managers and software distributions. In terms of reproducibility, only true 
    package managers are interesting.  This is because the software stack is broad
    and deep, both the code and machine that are used may be experimental (nothing
    is sacred), and notions of what it means to install software vary widely.

    A seemingly reasonable strategy is to minimize the assumed stack that the package
    manager itself depends on to just Python and a C compiler.  Even if these are of 
    wrong or outdated versions, a decent package manager will be able to bootstrap 
    up to more recent code bases.  However, even this falls short on some major 
    platforms (e.g. Windows & HPC).

    Enter fief: a user-space, cross-platform, branched (multi-versioned), 
    asynchronous, package manager for scientific computing. It aims to address the 
    issues of total or partial stack reproducibility while providing a 
    consistent interface across posix, Windows, Mac OSX (darwin), and HPC systems. 
    Both source and binary packages are handled easily in the fief model. As with 
    many package mangers, fief is written primarily in Python (and some BASH). 

    I will compare the fief meritocratic model to other alternatives, such as 
    hashdist, conda, the various distribution options, binary-based system package 
    managers (apt-get, mac ports), source-based package managers (portage, pacman), 
    language-specific tools (pip, easy_install, gems), and single project tools 
    (yt, VisIt).  In this process I hope to justify why scientists need our own 
    tool already.  If done properly, the right package manager will sneak 
    reproducibility into the daily workflow scientists under the guise of easily 
    providing them with the software they need to do research.

:submission references: https://github.com/scopatz/fief
    https://s3.amazonaws.com/fief/index.html

:submission type: Talk Only

:track: Tools for reproducibility

:domain symposia: None
