Terminology 
============
The following terms are used consistently throughout the fief code base:

* **ifc**: an interface name, e.g. 'zlib' or 'hdf5-parallel'.
* **interfaces**: a ditionary mapping an interface name to an interface ``ifc()``
  instance, e.g. ``{'zlib': ifc(libs='z')}``.
* **pkginterfaces**: a ditionary mapping package names to interfaces, e.g.
  ``{'hdf5': {'hdf5': ifc(...), 'hdf5-parallel': ifc(...)}, 'zlib': {'zlib': ifc()}}``.
