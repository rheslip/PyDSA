Updated version using Python 3.9 and latest PyVisa and NumPy
The code is updated with more function and robust interaction with the scope.

Spectrum Analyzer for the Rigol DS1000 series digital scopes    
  
RF Spectrum Analyzer in Python. This is a modified version of PA2OHH's audio spectrum analyzer:  
http://www.qsl.net/pa2ohh/11sa.htm  
  
It uses National Instruments VISA driver to download samples from the scope, perform FFTs and show the results. I used the PyVISA 1.4 wrapper:  
http://pyvisa.readthedocs.org/en/latest/getting_nivisa.html  

Written for Python 2.7 under Windows 7, not tested in other environments  

Dependencies:    
PyVISA  1.4
math  
numpy  
Tkinter  

Changelog:  
9-20-2015 - first release  


TODO:  
-blows up with some combinations of FFT size, averaging and padding - looks like an array indexing bug  

-there are a lot of spurs in the spectrum. May be possible to fix in software but I think this is a limitation of the scope itself  

Notes:  

9-30-2015 - tried to make it work with PyVISA 1.8 but the interface has changed a lot and it broke LONG scope buffer mode. Went back to PyVISA 1.4 

Jan 31 2016 - included DS1054Z patch by Marcus and a full version for the DS1054Z by Kerr Smith

Also included is Rigol_view, a short Python script which grabs the sample buffer and shells to wfm_view to show the results. wfm_view shows the same spurs in the spectrum.  
wfm_view can be found at:  
http://meteleskublesku.cz/wfm_view/  

project blog: rheslip.blogspot.com

Kerr Smith provided these step by step installation instructions:

I first installed the latest National Instruments VISA runtime:

http://www.ni.com/download/ni-visa-run-time-engine-15.0/5379/en/NIVISA1500runtime.exe

Next I installed Python 2.7 making sure Python was added to the path (this is so you can run python from the command line from any directory):

https://www.python.org/downloads/release/python-2711/python-2.7.11.amd64.msi

Next I updated pip and setuptools as well as installing wheel as recommend on:
http://python-packaging-user-guide.readthedocs.org/en/latest/installing/#install-pip-setuptools-and-wheel
python -m pip install -U pip setuptools
pip install wheel

I now updated mock as I could not get any further due to an error (on next step) saying 'Requires setuptools >=17.1 to install properly', the following fixed this issue and seemed to update a couple of other things as well:

pip install mock

Next I installed pyvisa version 1.4 as recommend (the mock update above made this work):

pip install pyvisa==1.4

Next I installed numpy, this initially did not work and showed this 'error: Unable to find vcvarsall.bat', so I installed the Microsoft Visual C++ Compiler for Python 2.7:

https://www.microsoft.com/en-gb/download/details.aspx?id=44266
VCForPython27.msi

Now numpy installed, it took a while as it needed to compile and there was no real progress update so I just left it and after a few minutes it finished and said it had installed.

pip install numpy

Next I downloaded the PyDSA code from Github:

https://github.com/rheslip/PyDSA

The file to run is in the PyDSA directory and is called PyDSA.py

