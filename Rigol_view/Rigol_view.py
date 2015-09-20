#!/usr/bin/python

"""
Download data from a Rigol DS1052E oscilloscope channel 1 and
dump to a .wav file.
By Ken Shirriff, http://righto.com/rigol

9-20-15 Rich Heslip - added os call to wfm_view for viewing waveforms and spectrum
"""

import sys
import visa
import wave
import os

# Get the USB device, e.g. 'USB0::0x1AB1::0x0588::DS1ED141904883'
instruments = visa.get_instruments_list()
usb = filter(lambda x: 'USB' in x, instruments)
if len(usb) != 1:
    print 'Bad instrument list', instruments
    sys.exit(-1)
scope = visa.instrument(usb[0], timeout=20, chunk_size=1024000) # bigger timeout for long mem

# Grab the raw data from channel 1
scope.write(":STOP")
scope.write(":WAV:POIN:MODE RAW")
rawdata = scope.ask(":WAV:DATA? CHAN1")[10:]
data_size = len(rawdata)
sample_rate = scope.ask_for_values(':ACQ:SAMP?')[0]
print 'Data size:', data_size, "Sample rate:", sample_rate
scope.write(":KEY:FORCE")
scope.close()

# Dump data to the wav file
wav_file = wave.open("channel1.wav", "w")
nchannels = 1
sampwidth = 1
comptype = "NONE"
compname = "not compressed"
wav_file.setparams((nchannels, sampwidth, sample_rate, data_size,
    comptype, compname))
# Data will be written inverted
wav_file.writeframes(rawdata)
wav_file.close()
os.system("wfm_view channel1.wav")
