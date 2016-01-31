# SpectrumAnalyzer-v01a.py(w)  (09-12-2011)
# For Python version 2.6 or 2.7
# With external module pyaudio (for Python version 2.6 or 2.7); NUMPY module (for used Python version)
# Created by Onno Hoekstra (pa2ohh)
#
# 17/9/15 Rich Heslip VE3MKC
# modified to capture samples from Rigol DS1102E scope for a basic 100Mhz SA
#
# This version slightly has a modified Sweep() routine for the DS1054Z by Kerr Smith Jan 31 2016
#
import math
import time
import numpy
import tkFont
import sys
import visa
from time import sleep
from Tkinter import *
from tkFileDialog import askopenfilename
from tkSimpleDialog import askstring
from tkMessageBox import *


NUMPYenabled = True         # If NUMPY installed, then the FFT calculations is 4x faster than the own FFT calculation

# Values that can be modified
GRWN = 1024                  # Width of the grid
GRHN = 512                  # Height of the grid
X0L = 20                    # Left top X value of grid
Y0T = 25                    # Left top Y value of grid

Vdiv = 8                    # Number of vertical divisions

TRACEmode = 1               # 1 normal mode, 2 max hold, 3 average
TRACEaverage = 10           # Number of average sweeps for average mode
TRACEreset = True           # True for first new trace, reset max hold and averageing
SWEEPsingle = False         # flag to sweep once

SAMPLErate = 1000000        # scope sample rate, read from scope when we read the buffer
SAMPLEsize = 16384          # default sample size
SAMPLEdepth = 0             # 0 normal, 1 long
UPDATEspeed = 1.1           # Update speed can be increased when problems if PC too slow, default 1.1
ZEROpadding = 0             # ZEROpadding for signal interpolation between frequency samples (0=none)

DBdivlist = [1, 2, 3, 5, 10, 20] # dB per division
DBdivindex = 5              # 20 dB/div as initial value

DBlevel = 0                 # Reference level

LONGfftsize = 262144        # FFT to do on long buffer. larger FFT takes more time
fftsamples = 16384           # size of FFT we are using - recalculated in DoFFT()

# Colors that can be modified
COLORframes = "#000080"     # Color = "#rrggbb" rr=red gg=green bb=blue, Hexadecimal values 00 - ff
COLORcanvas = "#000000"
COLORgrid = "#808080"
COLORtrace1 = "#00ff00"
COLORtrace2 = "#ff8000"
COLORtext = "#ffffff"
COLORsignalband = "#ff0000"
COLORaudiobar = "#606060"
COLORaudiook = "#00ff00"
COLORaudiomax = "#ff0000"
COLORred = "#ff0000"
COLORyellow = "#ffff00"
COLORgreen = "#00ff00"
COLORmagenta = "#00ffff"

# Button sizes that can be modified
Buttonwidth1 = 12
Buttonwidth2 = 8


# Initialisation of general variables
STARTfrequency = 0.0        # Startfrequency
STOPfrequency = 10000000.0     # Stopfrequency

SNenabled= False            # If Signal to Noise is enabled in the software
CENTERsignalfreq = 1000     # Center signal frequency of signal bandwidth for S/N measurement
STARTsignalfreq = 950.0     # Startfrequency of signal bandwidth for S/N measurement
STOPsignalfreq = 1050.0     # Stopfrequency of signal bandwidth for S/N measurement
SNfreqstep = 100            # Frequency step S/N frequency
SNmeasurement = True       # True for signal to noise measurement between signal and displayed bandwidth
SNresult = 0.0              # Result of signal to noise measurement
SNwidth = 0


# Other global variables required in various routines
GRW = GRWN                  # Initialize GRW
GRH = GRHN                  # Initialize GRH

CANVASwidth = GRW + 2 * X0L # The canvas width
CANVASheight = GRH + 80     # The canvas height

SIGNAL1 = []                # trace channel 1

FFTresult = []              # FFT result
T1line = []                 # Trace line channel 1
T2line = []                 # Trace line channel 2

S1line = []                 # Line for start of signal band indication
S2line = []                 # line for stop of signal band indication

RUNstatus = 1               # 0 stopped, 1 start, 2 running, 3 stop now, 4 stop and restart
STOREtrace = False          # Store and display trace
FFTwindow = 4               # FFTwindow 0=None (rectangular B=1), 1=Cosine (B=1.24), 2=Triangular non-zero endpoints (B=1.33),
                            # 3=Hann (B=1.5), 4=Blackman (B=1.73), 5=Nuttall (B=2.02), 6=Flat top (B=3.77)
SIGNALlevel = 0.0            # Level of audio input 0 to 1

Marker1x = 0                # marker pip 1 location
Marker1y = 0

Marker2x = 0                # marker pip 2
Marker2y = 0

if NUMPYenabled == True:
    try:
        import numpy.fft
    except:
        NUMPYenabled = False


# =================================== Start widgets routines ========================================
def Bnot():
    print "Routine not made yet"

def on_click(self, event):
        # Last click in absolute coordinates
        self.prev_var.set('%s:%s' % self.last_point)
        # Current point in relative coordinates
        self.curr_var.set('%s:%s' % (event.x - self.last_point[0], event.y - self.last_point[1]))
        self.last_point = event.x, event.y

# handle markers when mouse is clicked in middle frame
def Bmarker1(event):
    global Marker1x
    global Marker1y

    Marker1x=event.x
    Marker1y=event.y

def Bmarker2(event):
    global Marker2x
    global Marker2y

    Marker2x=event.x
    Marker2y=event.y
    #print "button 2 clicked at", event.x, event.y

def BNormalmode():
    global TRACEmode

    TRACEmode = 1
    UpdateScreen()          # Always Update


def BMaxholdmode():
    global TRACEmode
    global TRACEreset

    TRACEreset = True       # Reset trace peak and trace average
    TRACEmode = 2
    UpdateScreen()          # Always Update


def BAveragemode():
    global TRACEmode
    global TRACEaverage
    global TRACEreset
    global RUNstatus

    #if (RUNstatus != 0):
    #    showwarning("WARNING","Stop sweep first")
    #    return()

    TRACEreset = True       # Reset trace peak and trace average
    TRACEmode = 3


    s = askstring("Power averaging", "Value: " + str(TRACEaverage) + "x\n\nNew value:\n(1-n)")

    if (s == None):         # If Cancel pressed, then None
        return()

    try:                    # Error if for example no numeric characters or OK pressed without input (s = "")
        v = int(s)
    except:
        s = "error"

    if s != "error":
        TRACEaverage = v

    if TRACEaverage < 1:
        TRACEaverage = 1
    UpdateScreen()          # Always Update


def BFFTwindow():
    global FFTwindow
    global TRACEreset

    FFTwindow = FFTwindow + 1
    if FFTwindow > 6:
        FFTwindow = 0
    TRACEreset = True    # Reset trace peak and trace average
    UpdateAll()          # Always Update


def BSampledepth():
    global SAMPLEdepth
    global RUNstatus

    if (RUNstatus != 0):
        showwarning("WARNING","Stop sweep first")
        return()

    if SAMPLEdepth == 0:
        SAMPLEdepth = 1
    else:
        SAMPLEdepth = 0
    if RUNstatus == 0:      # Update if stopped
        UpdateScreen()


def BSTOREtrace():
    global STOREtrace
    global T1line
    global T2line
    if STOREtrace == False:
        T2line = T1line
        STOREtrace = True
    else:
        STOREtrace = False
    UpdateTrace()           # Always Update


def BSINGLEsweep():
    global SWEEPsingle
    global RUNstatus

    if (RUNstatus != 0):
        showwarning("WARNING","Stop sweep first")
        return()
    else:
        SWEEPsingle = True
        RUNstatus = 1       # we are stopped, start
    UpdateScreen()          # Always Update

def BSNmode():
    global RUNstatus
    global SNmeasurement
    global SNresult
    global SNwidth

    if SNwidth == 0:
        SNwidth = 1
        SNmeasurement = True
    elif SNwidth == 1:
        SNwidth = 2
        SNmeasurement = True
    elif SNwidth == 2:
        SNwidth = 5
        SNmeasurement = True
    elif SNwidth == 5:
        SNwidth = 10
        SNmeasurement = True
    elif SNwidth == 10:
        SNwidth = 0
        SNmeasurement = False

    if RUNstatus == 0:      # Update if stopped
        UpdateTrace()


def BSNfreq1():
    global RUNstatus
    global CENTERsignalfreq
    global SNfreqstep
    global SNmeasurement

    if SNmeasurement == False:      # Only if SN measurement is running
        return()

    CENTERsignalfreq = CENTERsignalfreq - SNfreqstep
    if CENTERsignalfreq < 0:
        CENTERsignalfreq = 0

    if RUNstatus == 0:              # Update if stopped
        UpdateTrace()


def BSNfreq2():
    global RUNstatus
    global CENTERsignalfreq
    global SNfreqstep
    global SNmeasurement

    if SNmeasurement == False:      # Only if SN measurement is running
        return()

    CENTERsignalfreq = CENTERsignalfreq + SNfreqstep
    if CENTERsignalfreq > 1e6:
        CENTERsignalfreq = 1e6

    if RUNstatus == 0:              # Update if stopped
        UpdateTrace()


def BSNfstep1():
    global SNfreqstep
    global SNmeasurement

    if SNmeasurement == False:      # Only if SN measurement is running
        return()

    elif SNfreqstep == 10:
        SNfreqstep = 1
    elif SNfreqstep == 100:
        SNfreqstep = 10
    elif SNfreqstep == 1000:
        SNfreqstep = 100


def BSNfstep2():
    global SNfreqstep
    global SNmeasurement

    if SNmeasurement == False:      # Only if SN measurement is running
        return()

    if SNfreqstep == 1:
        SNfreqstep = 10
    elif SNfreqstep == 10:
        SNfreqstep = 100
    elif SNfreqstep == 100:
        SNfreqstep = 1000


def BStart():
    global RUNstatus

    if (RUNstatus == 0):
        RUNstatus = 1
    UpdateScreen()          # Always Update


def Blevel1():
    global RUNstatus
    global DBlevel

    DBlevel = DBlevel - 1

    if RUNstatus == 0:      # Update if stopped
        UpdateTrace()


def Blevel2():
    global RUNstatus
    global DBlevel

    DBlevel = DBlevel + 1

    if RUNstatus == 0:      # Update if stopped
        UpdateTrace()


def Blevel3():
    global RUNstatus
    global DBlevel

    DBlevel = DBlevel - 10

    if RUNstatus == 0:      # Update if stopped
        UpdateTrace()


def Blevel4():
    global RUNstatus
    global DBlevel

    DBlevel = DBlevel + 10

    if RUNstatus == 0:      # Update if stopped
        UpdateTrace()


def BStop():
    global RUNstatus

    if (RUNstatus == 1):
        RUNstatus = 0
    elif (RUNstatus == 2):
        RUNstatus = 3
    elif (RUNstatus == 3):
        RUNstatus = 3
    elif (RUNstatus == 4):
        RUNstatus = 3
    UpdateScreen()          # Always Update


def BSetup():
    global SAMPLErate
    global ZEROpadding
    global RUNstatus
    global SIGNAL1
    global T1line
    global TRACEreset

    #if (RUNstatus != 0):
   #    showwarning("WARNING","Stop sweep first")
    #    return()

    s = askstring("Zero padding","For better interpolation of levels between frequency samples.\nIncreases processing time!\n\nValue: " + str(ZEROpadding) + "\n\nNew value:\n(0-5, 0 is no zero padding)")

    if (s == None):         # If Cancel pressed, then None
        return()

    try:                    # Error if for example no numeric characters or OK pressed without input (s = "")
        v = int(s)
    except:
        s = "error"

    if s != "error":
        if v < 0:
            v = 0
        if v > 5:
            v = 5
        ZEROpadding = v

    TRACEreset = True       # Reset trace peak and trace average
    UpdateAll()          #  Update FFT and screen


def BStartfrequency():
    global STARTfrequency
    global STOPfrequency
    global RUNstatus

    # if (RUNstatus != 0):
    #    showwarning("WARNING","Stop sweep first")
    #    return()

    s = askstring("Startfrequency: ","Value: " + str(STARTfrequency) + " Hz\n\nNew value:\n")

    if (s == None):         # If Cancel pressed, then None
        return()

    try:                    # Error if for example no numeric characters or OK pressed without input (s = "")
        v = float(s)
    except:
        s = "error"

    if s != "error":
        STARTfrequency = abs(v)

    if STOPfrequency <= STARTfrequency:
        STOPfrequency = STARTfrequency + 1

    if RUNstatus == 0:      # Update if stopped
        UpdateTrace()


def BStopfrequency():
    global STARTfrequency
    global STOPfrequency
    global RUNstatus

    # if (RUNstatus != 0):
    #    showwarning("WARNING","Stop sweep first")
    #    return()

    s = askstring("Stopfrequency: ","Value: " + str(STOPfrequency) + " Hz\n\nNew value:\n")

    if (s == None):         # If Cancel pressed, then None
        return()

    try:                    # Error if for example no numeric characters or OK pressed without input (s = "")
        v = float(s)
    except:
        s = "error"

    if s != "error":
        STOPfrequency = abs(v)

    if STOPfrequency < 10:  # Minimum stopfrequency 10 Hz
        STOPfrequency = 10

    if STARTfrequency >= STOPfrequency:
        STARTfrequency = STOPfrequency - 1

    if RUNstatus == 0:      # Update if stopped
        UpdateTrace()


def BDBdiv1():
    global DBdivindex
    global RUNstatus

    if (DBdivindex >= 1):
        DBdivindex = DBdivindex - 1
    if RUNstatus == 0:      # Update if stopped
        UpdateTrace()


def BDBdiv2():
    global DBdivindex
    global DBdivlist
    global RUNstatus

    if (DBdivindex < len(DBdivlist) - 1):
        DBdivindex = DBdivindex + 1
    if RUNstatus == 0:      # Update if stopped
        UpdateTrace()




# ============================================ Main routine ====================================================

def Sweep():   # Read samples and store the data into the arrays
    global X0L          # Left top X value
    global Y0T          # Left top Y value
    global GRW          # Screenwidth
    global GRH          # Screenheight
    global SIGNAL1
    global RUNstatus
    global SWEEPsingle
    global SMPfftlist
    global SMPfftindex
    global SAMPLErate
    global SAMPLEsize
    global SAMPLEdepth
    global UPDATEspeed
    global STARTfrequency
    global STOPfrequency
    global COLORred
    global COLORcanvas
    global COLORyellow
    global COLORgreen
    global COLORmagenta

    while (True):                                           # Main loop


        # RUNstatus = 1 : Open Stream
        if (RUNstatus == 1):
            if UPDATEspeed < 1:
                UPDATEspeed = 1.0

            TRACESopened = 1

            try:
# Get the USB device, e.g. 'USB0::0x1AB1::0x0588::DS1ED141904883'
                instruments = visa.get_instruments_list()
                usb = filter(lambda x: 'USB' in x, instruments)
                if len(usb) != 1:
                    print 'Bad instrument list', instruments
                    sys.exit(-1)
                scope = visa.instrument(usb[0], timeout=20, chunk_size=1024000) # bigger timeout for long mem

                RUNstatus = 2
            except:                                         # If error in opening audio stream, show error
                RUNstatus = 0
                #txt = "Sample rate: " + str(SAMPLErate) + ", try a lower sample rate.\nOr another audio device."
                showerror("VISA Error","Cannot open scope")

# get metadata
            #sample_rate = float(scope.ask(':ACQ:SAMP?'))
            #timescale = float(scope.ask(":TIM:SCAL?"))
            #timeoffset = float(scope.ask(":TIM:OFFS?"))
            #voltscale = float(scope.ask(':CHAN1:SCAL?'))
            #voltoffset = float(scope.ask(":CHAN1:OFFS?"))

            UpdateScreen()                                  # UpdateScreen() call


        # RUNstatus = 2: Reading audio data from soundcard
        if (RUNstatus == 2):
        # Grab the raw data from channel 1
            #try:
# Set the scope the way we want it
            if SAMPLEdepth == 0:
                scope.write(':ACQ:MDEP 12000') # normal memory type
            else:
                scope.write(':ACQ:MDEP 120000') # long memory type
            #scope.write(':CHAN1:COUP DC') # DC coupling
            #scope.write(':CHAN1:DISP ON') # Channel 1 on
            #scope.write(':CHAN2:DISP ON') # Channel 2 off
            #scope.write(':CHAN1:SCAL 1') # Channel 1 vertical scale 1 volts
            #scope.write(':CHAN1:OFFS -2') # Channel 1 vertical offset 2 volts
            #scope.write(':TIM:SCAL 0.001') # time interval
            #scope.write(':TIM:OFFS .05') # Offset time 50 ms

            #scope.write(':TRIG:EDGE:SOUR CHAN1') # Edge-trigger from channel 1
            #scope.write(':TRIG:EDGE:SWE SING') # Single trigger
            #scope.write(':TRIG:EDGE:COUP AC') # trigger coupling
            #scope.write(':TRIG:EDGE:SLOP NEG') # Trigger on negative edge
            #scope.write(':TRIG:EDGE:LEV 0.01') # Trigger  volts
            scope.write(":RUN")

            #txt = "Trig"
            #x = X0L + 250
            #y = Y0T+GRH+32
            #IDtxt  = ca.create_text (x, y, text=txt, anchor=W, fill=COLORyellow)
            #root.update()       # update screen

           # while scope.ask(':TRIG:STAT?') != 'STOP':
               # sleep(0.1)
            #sleep(0.1)
    # Grab the raw data from channel 1, which will take a few seconds for long buffer mode
           # sleep(0.1)
            scope.write(":STOP")
            scope.write(":WAV:SOUR CHAN1")
            scope.write(":WAV:MODE RAW")
            scope.write(":WAV:FORM BYTE")
            scope.write(":WAV:STAR 1")
            if SAMPLEdepth == 0:
                scope.write(":WAV:STOP 12000")
            else:
                scope.write(":WAV:STOP 120000")

            txt = "->Acquire"
            x = X0L + 275
            y = Y0T+GRH+32
            IDtxt  = ca.create_text (x, y, text=txt, anchor=W, fill=COLORgreen)
            root.update()       # update screen


            signals= scope.ask(":WAV:DATA?")  #do this first
            data_size = len(signals)

            SAMPLErate = scope.ask_for_values(':ACQ:SRAT?')[0] #do this second
            #print 'Data size:', SAMPLEsize, "Sample rate:", SAMPLErate



            # sleep(0.1)

# convert data from (inverted) bytes to an array of scaled floats
# this magic from Matthew Mets
            SIGNAL1 = numpy.frombuffer(signals, 'B')
            #print SIGNAL1
            SIGNAL1 = (SIGNAL1 * -1 + 255) -130  # invert
            #print SIGNAL1
            SIGNAL1 = SIGNAL1/127.0 # scale 10 +-1, has a slight DC offset
            #print SIGNAL1

            UpdateAll()                                     # Update Data, trace and screen

            if SWEEPsingle == True:  # single sweep mode, sweep once then stop
                SWEEPsingle = False
                RUNstatus = 3

        # RUNstatus = 3: Stop
        # RUNstatus = 4: Stop and restart
        if (RUNstatus == 3) or (RUNstatus == 4):
            scope.write(":KEY:FOR")
            scope.close()
            if RUNstatus == 3:
                RUNstatus = 0                               # Status is stopped
            if RUNstatus == 4:
                RUNstatus = 1                               # Status is (re)start
            UpdateScreen()                                  # UpdateScreen() call


        # Update tasks and screens by TKinter
        root.update_idletasks()
        root.update()                                       # update screens


def UpdateAll():        # Update Data, trace and screen
    DoFFT()             # Fast Fourier transformation
    MakeTrace()         # Update the traces
    UpdateScreen()      # Update the screen


def UpdateTrace():      # Update trace and screen
    MakeTrace()         # Update traces
    UpdateScreen()      # Update the screen


def UpdateScreen():     # Update screen with trace and text
    MakeScreen()        # Update the screen
    root.update()       # Activate updated screens


def DoFFT():            # Fast Fourier transformation
    global SIGNAL1
    global SAMPLEsize
    global TRACEmode
    global TRACEaverage
    global TRACEreset
    global ZEROpadding
    global FFTresult
    global fftsamples
    global SIGNALlevel
    global FFTwindow
    global NUMPYenabled
    global SMPfftlist
    global SMPfftindex
    global LONGfftsize

#show what we are doing on the screen
# FFT can take a long time!
    txt = "->FFT"
    x = X0L + 333
    y = Y0T+GRH+32
    IDtxt  = ca.create_text (x, y, text=txt, anchor=W, fill=COLORred)
    root.update()       # update screen

    T1 = time.time()                        # For time measurement of FFT routine

    REX = []
    IMX = []



    # No FFT if empty or too short array of audio samples
    if len(SIGNAL1) >= 1048576: # ensure only valid buffer sizes
        fftsamples = LONGfftsize # can set this to be less than buffer size to make it faster
    elif len(SIGNAL1) >= 16384: # ensure only valid buffer sizes
        fftsamples = 16384
    elif len(SIGNAL1) >= 8192: # ensure only valid buffer sizes
        fftsamples = 8192
    else:
        return  # not a valid buffer size
    #print "Buffersize:" + str(len(SIGNAL1)) + " FFTsize: " + str(fftsamples)
    SAMPLEsize= fftsamples

    n = 0
    SIGNALlevel = 0.0
    v = 0.0
    m = 0                                   # For calculation of correction factor
    while n < fftsamples:

        v=SIGNAL1[n]
        # Check for overload
        va = abs(v)                         # Check for too high audio input level
        #print v
        if va > SIGNALlevel:
            SIGNALlevel = va

        # Cosine window function
        # medium-dynamic range B=1.24
        if FFTwindow == 1:
            w = math.sin(math.pi * n / (fftsamples - 1))
            v = w * v * 1.571

        # Triangular non-zero endpoints
        # medium-dynamic range B=1.33
        if FFTwindow == 2:
            w = (2.0 / fftsamples) * ((fftsamples / 2.0) - abs(n - (fftsamples - 1) / 2.0))
            v = w * v * 2.0

        # Hann window function
        # medium-dynamic range B=1.5
        if FFTwindow == 3:
            w = 0.5 - 0.5 * math.cos(2 * math.pi * n / (fftsamples - 1))
            v = w * v * 2.000

        # Blackman window, continuous first derivate function
        # medium-dynamic range B=1.73
        if FFTwindow == 4:
            w = 0.42 - 0.5 * math.cos(2 * math.pi * n / (fftsamples - 1)) + 0.08 * math.cos(4 * math.pi * n / (fftsamples - 1))
            v = w * v * 2.381

        # Nuttall window, continuous first derivate function
        # high-dynamic range B=2.02
        if FFTwindow == 5:
            w = 0.355768 - 0.487396 * math.cos(2 * math.pi * n / (fftsamples - 1)) + 0.144232 * math.cos(4 * math.pi * n / (fftsamples - 1))- 0.012604 * math.cos(6 * math.pi * n / (fftsamples - 1))
            v = w * v * 2.811

        # Flat top window,
        # medium-dynamic range, extra wide bandwidth B=3.77
        if FFTwindow == 6:
            w = 1.0 - 1.93 * math.cos(2 * math.pi * n / (fftsamples - 1)) + 1.29 * math.cos(4 * math.pi * n / (fftsamples - 1))- 0.388 * math.cos(6 * math.pi * n / (fftsamples - 1)) + 0.032 * math.cos(8 * math.pi * n / (fftsamples - 1))
            v = w * v * 1.000

        # m = m + w / fftsamples                # For calculation of correction factor
        REX.append(v)                           # Append the value to the REX array
        IMX.append(0.0)                       # Append 0 to the imagimary part

        n = n + 1

    # if m > 0:                               # For calculation of correction factor
    #     print 1/m                           # For calculation of correction factor

    # Zero padding of array for better interpolation of peak level of signals
    ZEROpaddingvalue = int(math.pow(2,ZEROpadding) + 0.5)
    fftsamples = ZEROpaddingvalue * fftsamples       # Add zero's to the arrays
    #fftsamples = ZEROpaddingvalue * fftsamples -1      # Add zero's to the arrays

    # The FFT calculation with NUMPY if NUMPYenabled == True or with the FFT calculation below
    fftresult = numpy.fft.fft(REX, n=fftsamples)# Do FFT+zeropadding till n=fftsamples with NUMPY if NUMPYenabled == True
    REX=fftresult.real
    IMX=fftresult.imag


    # Make FFT result array
    Totalcorr = float(ZEROpaddingvalue)/ fftsamples         # For VOLTAGE!
    Totalcorr = Totalcorr * Totalcorr                       # For POWER!

    FFTmemory = FFTresult
    FFTresult = []

    #print len(FFTmemory)

    n = 0
    while (n <= fftsamples / 2):
        # For relative to voltage: v = math.sqrt(REX[n] * REX[n] + IMX[n] * IMX[n])    # Calculate absolute value from re and im
        v = REX[n] * REX[n] + IMX[n] * IMX[n]               # Calculate absolute value from re and im relative to POWER!
        v = v * Totalcorr                                   # Make level independent of samples and convert to display range

        if TRACEmode == 1:                                  # Normal mode, do not change v
            pass

        if TRACEmode == 2 and TRACEreset == False:          # Max hold, change v to maximum value
            if v < FFTmemory[n]:
                v = FFTmemory[n]

        if TRACEmode == 3 and TRACEreset == False:          # Average, add difference / TRACEaverage to v
            v = FFTmemory[n] + (v - FFTmemory[n]) / TRACEaverage

        FFTresult.append(v)                                 # Append the value to the FFTresult array

        n = n + 1

    TRACEreset = False                                      # Trace reset done

    T2 = time.time()
    # print (T2 - T1)                                         # For time measurement of FFT routine


def MakeTrace():        # Update the grid and trace
    global FFTresult
    global T1line
    global T2line
    global S1line
    global S2line
    global STOREtrace
    global X0L          # Left top X value
    global Y0T          # Left top Y value
    global GRW          # Screenwidth
    global GRH          # Screenheight
    global Vdiv         # Number of vertical divisions
    global STARTfrequency
    global STOPfrequency
    global CENTERsignalfreq
    global STARTsignalfreq
    global STOPsignalfreq
    global SNenabled
    global SNmeasurement
    global SNresult
    global SNwidth
    global DBdivlist    # dB per division list
    global DBdivindex   # Index value
    global DBlevel      # Reference level
    global SAMPLErate


    # Set the TRACEsize variable
    TRACEsize = len(FFTresult)      # Set the trace length

    if TRACEsize == 0:              # If no trace, skip rest of this routine
        return()


    # Vertical conversion factors (level dBs) and border limits
    Yconv = float(GRH) / (Vdiv * DBdivlist[DBdivindex])     # Conversion factors from dBs to screen points 10 is for 10 * log(power)
    #Yc = float(Y0T) + GRH + Yconv * (DBlevel -90)           # Zero postion and -90 dB for in grid range
    Yc = float(Y0T) + GRH + Yconv * (DBlevel -(Vdiv * DBdivlist[DBdivindex]))
    Ymin = Y0T                                              # Minimum position of screen grid (top)
    Ymax = Y0T + GRH                                        # Maximum position of screen grid (bottom)


    # Horizontal conversion factors (frequency Hz) and border limits
    Fpixel = float(STOPfrequency - STARTfrequency) / GRW    # Frequency step per screen pixel
    Fsample = float(SAMPLErate / 2) / (TRACEsize - 1)       # Frequency step per sample

    T1line = []
    n = 0
    Slevel = 0.0            # Signal level
    Nlevel = 0.0            # Noise level
    while n < TRACEsize:
        F = n * Fsample

        if F >= STARTfrequency and F <= STOPfrequency:
            x = X0L + (F - STARTfrequency)  / Fpixel
            T1line.append(int(x + 0.5))
            try:
                y =  Yc - Yconv * 10 * math.log10(float(FFTresult[n]))  # Convert power to DBs, except for log(0) error
            except:
                y = Ymax

            if (y < Ymin):
                y = Ymin
            if (y > Ymax):
                y = Ymax
            T1line.append(int(y + 0.5))

            if SNenabled == True and (F < STARTsignalfreq or F > STOPsignalfreq):               # Add to noise if outside signal band
                Nlevel = Nlevel + float(FFTresult[n])

        if SNenabled == True and (F >= STARTsignalfreq and F <= STOPsignalfreq):                # Add to signal if inside signal band
            Slevel = Slevel + float(FFTresult[n])

        n = n + 1

    try:
        SNresult = 10 * math.log10(Slevel / Nlevel)
    except:
        SNresult = -999


    # Make the SIGNAL band lines
    S1line = []
    S2line = []

    if  SNenabled == True and SNmeasurement == True:
        STARTsignalfreq = CENTERsignalfreq - CENTERsignalfreq * float(SNwidth) / 100
        STOPsignalfreq = CENTERsignalfreq + CENTERsignalfreq * float(SNwidth) / 100

        if STARTsignalfreq >= STARTfrequency and STARTsignalfreq <= STOPfrequency:
            x = X0L + (STARTsignalfreq - STARTfrequency)  / Fpixel
            S1line.append(int(x + 0.5))
            S1line.append(int(Ymin))
            S1line.append(int(x + 0.5))
            S1line.append(int(Ymax))

        if STOPsignalfreq >= STARTfrequency and STOPsignalfreq <= STOPfrequency:
            x = X0L + (STOPsignalfreq - STARTfrequency)  / Fpixel
            S2line.append(int(x + 0.5))
            S2line.append(int(Ymin))
            S2line.append(int(x + 0.5))
            S2line.append(int(Ymax))


def MakeScreen():       # Update the screen with traces and text
    global X0L          # Left top X value
    global Y0T          # Left top Y value
    global GRW          # Screenwidth
    global GRH          # Screenheight
    global T1line
    global T2line
    global S1line
    global S2line
    global STOREtrace
    global Vdiv         # Number of vertical divisions
    global RUNstatus    # 0 stopped, 1 start, 2 running, 3 stop now, 4 stop and restart
    global SAMPLEdepth  # 0 norm, 1 long
    global UPDATEspeed
    global STARTfrequency
    global STOPfrequency
    global CENTERsignalfreq
    global STARTsignalfreq
    global STOPsignalfreq
    global SNenabled
    global SNmeasurement
    global SNresult
    global DBdivlist    # dB per division list
    global DBdivindex   # Index value
    global DBlevel      # Reference level
    global SAMPLErate
    global SAMPLEsize
    global TRACEmode    # 1 normal 2 max 3 average
    global TRACEaverage # Number of traces for averageing
    global SIGNALlevel   # Level of signal input 0 to 1
    global FFTwindow
    global fftsamples   # size of FFT
    global COLORgrid    # The colors
    global COLORtrace1
    global COLORtrace2
    global COLORtext
    global COLORsignalband
    global COLORaudiobar
    global COLORaudiook
    global COLORaudiomax
    global CANVASwidth
    global CANVASheight


    # Delete all items on the screen
    de = ca.find_enclosed ( 0, 0, CANVASwidth+1000, CANVASheight+1000)
    for n in de:
        ca.delete(n)


    # Draw horizontal grid lines
    i = 0
    x1 = X0L
    x2 = X0L + GRW
    x3 = x1+2     # db labels X location
    db= DBlevel

    while (i <= Vdiv):
        y = Y0T + i * GRH/Vdiv
        Dline = [x1,y,x2,y]
        ca.create_line(Dline, fill=COLORgrid)
        txt = str(db) # db labels
        idTXT = ca.create_text (x3, y-5, text=txt, anchor=W, fill=COLORtext)
        db = db - DBdivlist[DBdivindex]
        i = i + 1


    # Draw vertical grid lines
    i = 0
    y1 = Y0T
    y2 = Y0T + GRH
    freq= STARTfrequency
    freqstep= (STOPfrequency-STARTfrequency)/10
    while (i < 11):
        x = X0L + i * GRW/10
        Dline = [x,y1,x,y2]
        ca.create_line(Dline, fill=COLORgrid)
        txt = str(freq/1000000) # freq labels in mhz
        txt= txt + "M"
        idTXT = ca.create_text (x-10, y2+10, text=txt, anchor=W, fill=COLORtext)
        freq=freq+freqstep
        i = i + 1


    # Draw traces
    if len(T1line) > 4:                                     # Avoid writing lines with 1 coordinate
        ca.create_line(T1line, fill=COLORtrace1)            # Write the trace 1

    if STOREtrace == True and len(T2line) > 4:              # Write the trace 2 if active
        ca.create_line(T2line, fill=COLORtrace2)            # and avoid writing lines with 1 coordinate


    # Draw SIGNAL band lines
    if SNmeasurement == True:
        if len(S1line) > 3:                                 # Avoid writing lines with 1 coordinate
            ca.create_line(S1line, fill=COLORsignalband)    # Write the start frequency line of the signal band

        if len(S2line) > 3:                                 # Avoid writing lines with 1 coordinate
            ca.create_line(S2line, fill=COLORsignalband)    # Write the stop frequency line of the signal band


    # General information on top of the grid


    txt = "             Sample rate: " + str(SAMPLErate/1000000) +" MHz"
    #txt = txt + "    FFT samples: " + str(SMPfftlist[SMPfftindex])
    txt = txt + "    FFT size: " + str(fftsamples)
    txt = txt + "    RBW: " + str(int((SAMPLErate/SAMPLEsize)/2))+" Hz"

    if FFTwindow == 0:
        txt = txt + "    Rectangular (no) window (B=1) "
    if FFTwindow == 1:
        txt = txt + "    Cosine window (B=1.24) "
    if FFTwindow == 2:
        txt = txt + "    Triangular window (B=1.33) "
    if FFTwindow == 3:
        txt = txt + "    Hann window (B=1.5) "
    if FFTwindow == 4:
        txt = txt + "    Blackman window (B=1.73) "
    if FFTwindow == 5:
        txt = txt + "    Nuttall window (B=2.02) "
    if FFTwindow == 6:
        txt = txt + "    Flat top window (B=3.77) "

    x = X0L
    y = 12
    idTXT = ca.create_text (x, y, text=txt, anchor=W, fill=COLORtext)


    # Start and stop frequency and dB/div and trace mode
    txt = str(STARTfrequency/1000000) + " to " + str(STOPfrequency/1000000) + " MHz"
    txt = txt +  "    " + str(DBdivlist[DBdivindex]) + " dB/div"
    txt = txt + "    Level: " + str(DBlevel) + " dB "

    if TRACEmode == 1:
        txt = txt + "    Normal mode "

    if TRACEmode == 2:
        txt = txt + "    Maximum hold mode "

    if TRACEmode == 3:
        txt = txt + "    Power average  mode (" + str(TRACEaverage) + ") "

    if SNenabled == True and SNmeasurement == True:
        txt1 = str(int(SNresult * 10))
        while len(txt) < 2:
            txt1 = "0" + txt1
        txt1 = txt1[:-1] + "." + txt1[-1:]
        txt = txt + "    Signal to Noise ratio (dB): " + txt1

    x = X0L +500
    y = Y0T+GRH+32
    idTXT = ca.create_text (x, y, text=txt, anchor=W, fill=COLORtext)


    # Soundcard level bargraph
    txt1 = "||||||||||||||||||||"   # Bargraph
    le = len(txt1)                  # length of bargraph

    t = int(math.sqrt(SIGNALlevel) * le)

    n = 0
    txt = ""
    while(n < t and n < le):
        txt = txt + "|"
        n = n + 1

    x = X0L
    y = Y0T+GRH+32

    IDtxt = ca.create_text (x, y, text=txt1, anchor=W, fill=COLORaudiobar)

    if SIGNALlevel >= 1.0:
        IDtxt = ca.create_text (x, y, text=txt, anchor=W, fill=COLORaudiomax)
    else:
        IDtxt = ca.create_text (x, y, text=txt, anchor=W, fill=COLORaudiook)


    # Runstatus and level information
    if (SAMPLEdepth == 1):
        txt = "LONG"
    else:
        txt = "NORM"

    if (RUNstatus == 0) or (RUNstatus == 3):
        txt = txt + " Sweep stopped"
    else:
        txt = txt + " Sweep running"



    x = X0L + 100
    y = Y0T+GRH+32
    IDtxt  = ca.create_text (x, y, text=txt, anchor=W, fill=COLORtext)

# show the values at the mouse cursor
# note the magic numbers below were determined by looking at the cursor values
# not sure why they don't correspond to X0T and Y0T
    cursorx = (STARTfrequency + (root.winfo_pointerx()-root.winfo_rootx()-X0L-4) * (STOPfrequency-STARTfrequency)/GRW) /1000000
    cursory = DBlevel - (root.winfo_pointery()-root.winfo_rooty()-Y0T-50) * Vdiv*DBdivlist[DBdivindex] /GRH

    txt = "Cursor " + str(cursorx)  + " MHz   " + str(cursory) + " dB"

    x = X0L+800
    y = 12
    idTXT = ca.create_text (x, y, text=txt, anchor=W, fill=COLORtext)
"""
    Marker1valid=False
    if ((Marker1x > 20) & (Marker1y >20)): # show on screen markers
        Marker1valid=True
        idTXT = ca.create_text (Marker1x-3, Marker1y+4, text="^", anchor=W, fill=COLORMarker1)
        Marker1freq = (STARTfrequency + (Marker1x-19) * (STOPfrequency-STARTfrequency)/GRW) /1000000
        Marker1db = DBlevel - (Marker1y-20) * Vdiv*DBdivlist[DBdivindex] /GRH
        txt = "Marker1 " + str(Marker1freq)  + " MHz   " + str(Marker1db) + " dB"
        x = X0L + 300
        y = Y0T -10
        idTXT = ca.create_text (x, y, text=txt, anchor=W, fill=COLORMarker1)

    Marker2valid=False
    if ((Marker2x > 20) & (Marker2y >20)): # show on screen markers
        Marker2valid=True
        idTXT = ca.create_text (Marker2x-3, Marker2y+4, text="^", anchor=W, fill=COLORMarker2)
        Marker2freq = (STARTfrequency + (Marker2x-19) * (STOPfrequency-STARTfrequency)/GRW) /1000000
        Marker2db = DBlevel - (Marker2y-20) * Vdiv*DBdivlist[DBdivindex] /GRH
        txt = "Marker2 " + str(Marker2freq)  + " MHz   " + str(Marker2db) + " dB"
        x = X0L + 520
        y = Y0T -10
        idTXT = ca.create_text (x, y, text=txt, anchor=W, fill=COLORMarker2)

    # show marker delta only if both are valid
    if (Marker1valid & Marker2valid):
        Deltafreq = abs(Marker2freq-Marker1freq)
        Deltadb = abs(Marker2db-Marker1db)
        txt = "Delta " + str(Deltafreq)  + " MHz   " + str(Deltadb) + " dB"
        x = X0L + 750
        y = Y0T -10
        idTXT = ca.create_text (x, y, text=txt, anchor=W, fill=COLORtext)

"""

# ================ Make Screen ==========================

root=Tk()
root.title("Rigol Spectrum Analyzer V1.0 09-19-2015 VE3MKC")

root.minsize(100, 100)

frame1 = Frame(root, background=COLORframes, borderwidth=5, relief=RIDGE)
frame1.pack(side=TOP, expand=1, fill=X)

frame2 = Frame(root, background="black", borderwidth=5, relief=RIDGE)
frame2.pack(side=TOP, expand=1, fill=X)

if SNenabled == True:
    frame2a = Frame(root, background=COLORframes, borderwidth=5, relief=RIDGE)
    frame2a.pack(side=TOP, expand=1, fill=X)

frame3 = Frame(root, background=COLORframes, borderwidth=5, relief=RIDGE)
frame3.pack(side=TOP, expand=1, fill=X)

ca = Canvas(frame2, width=CANVASwidth, height=CANVASheight, background=COLORcanvas)
ca.pack(side=TOP)

b = Button(frame1, text="Normal mode", width=Buttonwidth1, command=BNormalmode)
b.pack(side=LEFT, padx=5, pady=5)

b = Button(frame1, text="Max hold", width=Buttonwidth1, command=BMaxholdmode)
b.pack(side=LEFT, padx=5, pady=5)

b = Button(frame1, text="Average", width=Buttonwidth1, command=BAveragemode)
b.pack(side=LEFT, padx=5, pady=5)

b = Button(frame1, text="Zero Padding", width=Buttonwidth1, command=BSetup)
b.pack(side=LEFT, padx=5, pady=5)

b = Button(frame1, text="FFTwindow", width=Buttonwidth1, command=BFFTwindow)
b.pack(side=LEFT, padx=5, pady=5)

b = Button(frame1, text="Store trace", width=Buttonwidth1, command=BSTOREtrace)
b.pack(side=RIGHT, padx=5, pady=5)


if SNenabled == True:
    b = Button(frame2a, text="S/N mode", width=Buttonwidth1, command=BSNmode)
    b.pack(side=LEFT, padx=5, pady=5)

    b = Button(frame2a, text="S/N freq-", width=Buttonwidth1, command=BSNfreq1)
    b.pack(side=LEFT, padx=5, pady=5)

    b = Button(frame2a, text="S/N freq+", width=Buttonwidth1, command=BSNfreq2)
    b.pack(side=LEFT, padx=5, pady=5)

    b = Button(frame2a, text="Fstep-", width=Buttonwidth1, command=BSNfstep1)
    b.pack(side=LEFT, padx=5, pady=5)

    b = Button(frame2a, text="Fstep+", width=Buttonwidth1, command=BSNfstep2)
    b.pack(side=LEFT, padx=5, pady=5)

b = Button(frame3, text="Start", width=Buttonwidth2, command=BStart)
b.pack(side=LEFT, padx=5, pady=5)

b = Button(frame3, text="Stop", width=Buttonwidth2, command=BStop)
b.pack(side=LEFT, padx=5, pady=5)

b = Button(frame3, text="NORM/LONG", width=Buttonwidth1, command=BSampledepth)
b.pack(side=LEFT, padx=5, pady=5)

b = Button(frame3, text="Single", width=Buttonwidth1, command=BSINGLEsweep)
b.pack(side=LEFT, padx=5, pady=5)

b = Button(frame3, text="Startfreq", width=Buttonwidth2, command=BStartfrequency)
b.pack(side=LEFT, padx=5, pady=5)

b = Button(frame3, text="Stopfreq", width=Buttonwidth2, command=BStopfrequency)
b.pack(side=LEFT, padx=5, pady=5)

b = Button(frame3, text="+dB/div", width=Buttonwidth2, command=BDBdiv2)
b.pack(side=RIGHT, padx=5, pady=5)

b = Button(frame3, text="-dB/div", width=Buttonwidth2, command=BDBdiv1)
b.pack(side=RIGHT, padx=5, pady=5)

b = Button(frame3, text="LVL+10", width=Buttonwidth2, command=Blevel4)
b.pack(side=RIGHT, padx=5, pady=5)

b = Button(frame3, text="LVL-10", width=Buttonwidth2, command=Blevel3)
b.pack(side=RIGHT, padx=5, pady=5)

b = Button(frame3, text="LVL+1", width=Buttonwidth2, command=Blevel2)
b.pack(side=RIGHT, padx=5, pady=5)

b = Button(frame3, text="LVL-1", width=Buttonwidth2, command=Blevel1)
b.pack(side=RIGHT, padx=5, pady=5)

# ================ Call main routine ===============================
root.update()               # Activate updated screens
#SELECTaudiodevice()
Sweep()




