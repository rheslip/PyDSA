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

Also included is Rigol_view, a short Python script which grabs the sample buffer and shells to wfm_view to show the results. wfm_view shows the same spurs in the spectrum.  
wfm_view can be found at:  
http://meteleskublesku.cz/wfm_view/  

project blog: rheslip.blogspot.com

