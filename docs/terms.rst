Terminology 
============
The following terms are used consistently throughout the fief code base:

* **pkg**: a package name which may contain many interfaces, e.g. 'zlib' or 'hdf5'.
* **pkgs**: a flat collection of package names, e.g. ``['zlib', 'hdf5']``.
* **ifc**: an interface name, e.g. 'zlib' or 'hdf5-parallel'.
* **ifcs**: a flat collection of interface names, e.g. ``['zlib', 'hdf5-parallel']``.
* **ifc2pkg**: a mapping of interface names to a unique packages, e.g.
  ``{'zlib': 'zlib', 'mpi3': 'mpich'}``.
* **interfaces**: a ditionary mapping an interface name to an interface ``ifc()``
  instance, e.g. ``{'zlib': ifc(libs='z')}``.
* **pkginterfaces**: a ditionary mapping package names to interfaces, e.g.
  ``{'hdf5': {'hdf5': ifc(...), 'hdf5-parallel': ifc(...)}, 'zlib': {'zlib': ifc()}}``.
