# SpectrumAnalyzer-v01a.py(w)  (09-12-2011)
# For Python version 3.9 (updated from 2.6 by KK1L)
# With external module pyaudio (for Python version 2.6 or 2.7); NUMPY module (for used Python version)
# Created by Onno Hoekstra (pa2ohh)
#
# 17/9/15 Rich Heslip VE3MKC
# modified to capture samples from Rigol DS1102E scope for a basic 100Mhz SA
#
# This version slightly has a modified Sweep() routine for the DS1054Z by Kerr Smith Jan 31 2016
#
# This version modified for Python 3.9 by Ron Rossi Jan 17 2021
# pyvisa ".ask" is now ".query"
# significantly updated how to wait for waveform to be acquired and display
#
# Jul 16 2021 KK1L
#   Added Clear button to remove the waveforms and reset averaging/max-hold
#   Added toggle button to choose channel 1 or 2
#   On screen progress feedback for scope read, FFT, and display
#   Warning trap when scope not triggered
#   Added peak detect
#   Added autoscale
#   Put averaging back to accumulate mode
#   Autoscale works with all displayed waveforms
#   Changing divisions or shifting works with all displayed waveforms
#   Allow up to 7 stored waveforms
#   Calibration option
#   Scale is in dBm and is accurate when calibrated with known magnitude sine
#
import math
import time
import numpy
#import tkinter
import tkinter.font as tkfont
import sys
import pyvisa as visa
from time import sleep
from tkinter import *
from tkinter.simpledialog import *
from tkinter.messagebox import *
import array 


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
SAMPLEsize = 16384          # default sample size ROSSI - irrelevant now. Read from scope.
ChannelChoice = 1             # 1 channel 1, 2 channel 2 ROSSI. Now used for channel selection
UPDATEspeed = 1.1           # Update speed can be increased when problems if PC too slow, default 1.1
ZEROpadding = 0             # ZEROpadding for signal interpolation between frequency samples (0=none)

DBdivlist = [1, 2, 3, 5, 10, 20] # dB per division
DBdivindex = 5              # 20 dB/div as initial value

DBlevel = 0                 # Reference level
CalibFactor = 7.4           # Trial and error value using 1MHz 632mVp-p for 0dBm and 2.00Vp-p for 10dBm.
PeakValuedBm = -9999.0      # Peak determined during operation.
PeakFrequency = 0
MinValuedBm =   9999.0      # Min determined during operation.
BestdBdivIndex = 5          # Initial best value for autoscale
ASPeakValuedBm  = -9999.0   # AutoScale peak tracks the peak across all waves including stored
ASMinValuedBm = 9999.0      # AutoScale min track the peak across all waves including stored

LONGfftsize = 262144        # FFT to do on long buffer. larger FFT takes more time ROSSI - No longer used.
fftsamples = 16384           # size of FFT we are using - ROSSI - irrelevant now. Calculated from data read.

# Colors that can be modified
COLORframes = "#000080"     # Color = "#rrggbb" rr=red gg=green bb=blue, Hexadecimal values 00 - ff
COLORcanvas = "#000000"
COLORgrid = "#808080"
COLORtrace1 = "#00ff00"
ColorStoredTrace = ["#ff8000", "#ffff00", "#00ff00", "#00ffff", "#ff00ff", '#0080ff', '#cce5ff']
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
STARTfrequency = 1000000.0     # Startfrequency
STOPfrequency = 30000000.0     # Stopfrequency

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
PrimaryTrace = []           # Primary trace line
StoredTraces = [[]]*8       # Stored traces
StoredFFT = [[]]*8          # Stored FFT data to make scaling easier. Use for input to MakeTrace
MaxStoredTraces = 7
CurrentStoredTrace = -1      # set to zero indicates no stored traces

S1line = []                 # Line for start of signal band indication
S2line = []                 # line for stop of signal band indication

RUNstatus = 0               # 0 stopped, 1 start, 2 running, 3 stop now, 4 stop and restart.
STOREtrace = False          # Store and display trace
FFTwindow = 4               # FFTwindow 0=None (rectangular B=1), 1=Cosine (B=1.24), 2=Triangular non-zero endpoints (B=1.33),
                            # 3=Hann (B=1.5), 4=Blackman (B=1.73), 5=Nuttall (B=2.02), 6=Flat top (B=3.77)
SIGNALlevel = 0.0            # Level of audio input 0 to 1 ROSSI Not used.

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
    print("Routine not made yet")

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
    #print ("button 2 clicked at", event.x, event.y)

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

    s = askinteger("Power averaging", "Value: " + str(TRACEaverage) + "x\n\nNew value:\n(1-n)")

    if ((s == None) or (s == " ")):         # If Cancel pressed, then None
        return()

    try:                    # Error if for example no numeric characters)
        v = int(s)
    except:
        s = "error"

    if s != "error":
        TRACEaverage = v

    if TRACEaverage < 1:
        TRACEaverage = 1
    UpdateScreen()          # Always Update

def BCalibration():
    global CalibFactor

    s = askfloat("Calibration Factor", "Value: " + str(CalibFactor) + "x\n\nNew value:\n(1-n)")

    if (s == None):         # If Cancel pressed, then None
        return()

    #try:                    # Error if for example no numeric characters or OK pressed without input (s = "")
    #    v = int(s)
    #except:
    #    s = "error"

    #if s != "error":
    CalibFactor = s

    if CalibFactor < 0.1:
        CalibFactor = 1
    UpdateScreen()          # Always Update

def BAutoScale():
    global DBlevel
    global DBdivindex
    global FFTresult
    global PrimaryTrace
    global StoredTraces
    # Save the "live" wave
    TempPrimaryFFT = FFTresult.copy()
    # Set up to figure the graticle shift and scaling

    if ASPeakValuedBm > -9999: #check to see if waveform is already acquired (requirement for this to work)
        # already calculated best dB per div. Now need to find what to shift the top of screen value to.
        BestdBLevel = -1000 #use a low value divisible by all possible db/div settings (1, 2, 5, 10, 20)
        while int(ASPeakValuedBm) > BestdBLevel:
            BestdBLevel = BestdBLevel + DBdivlist[BestdBdivIndex]
        DBdivindex = BestdBdivIndex
        DBlevel = BestdBLevel
    #now recreate traces from the FFT data. Start with stored so the last Primary is the real Primary
    Index = 0
    if CurrentStoredTrace != -1:
        while Index <= CurrentStoredTrace:
            FFTresult = StoredFFT[Index].copy()
            MakeTrace() #makes PrimaryTrace from FFTresult
            StoredTraces[Index] = PrimaryTrace.copy() #store PrimaryTrace in correct StoredTraces
            Index = Index + 1
    FFTresult = TempPrimaryFFT.copy() # scale and shift each stored FFT
    UpdateTrace() #makes PrimaryTrace from FFTresult and then MakeScreen for all traces

def BFFTwindow():
    global FFTwindow
    global TRACEreset

    FFTwindow = FFTwindow + 1
    if FFTwindow > 6:
        FFTwindow = 0
    TRACEreset = True    # Reset trace peak and trace average
    UpdateAll()          # Always Update


def BChannelChoice():
    global ChannelChoice
    global RUNstatus

    #if (RUNstatus != 0):
    #    showwarning("WARNING","Stop sweep first")
    #    return()

    if ChannelChoice == 2:
        ChannelChoice = 1
    else:
        ChannelChoice = 2
    #if RUNstatus == 0:      # Update if stopped
    UpdateScreen()


def BSTOREtrace():
    global STOREtrace
    global PrimaryTrace
    global StoredTraces
    global MaxStoredTraces
    global CurrentStoredTrace
    global ASPeakValuedBm
    global ASMinValuedBm
    global PeakValuedBm
    global MinValuedBm
     # Save overall peak and minimum
    if PeakValuedBm > ASPeakValuedBm:
        ASPeakValuedBm = PeakValuedBm
    if MinValuedBm < ASMinValuedBm:
        ASMinValuedBm = MinValuedBm
    PeakValuedBm = -9999.0
    MinValuedBm = 9999.0
    CST_OnEntry = CurrentStoredTrace
    try:
        if CurrentStoredTrace >= -1 and CurrentStoredTrace < 5:
            CurrentStoredTrace = CurrentStoredTrace + 1
            StoredTraces[CurrentStoredTrace] = PrimaryTrace.copy()
            StoredFFT[CurrentStoredTrace] = FFTresult.copy()
            STOREtrace = True
        else:
            STOREtrace = False
    except:
        CurrentStoredTrace = CST_OnEntry

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
        TRACEreset = True    # Reset trace peak and trace average
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
    global FFTresult
    global PrimaryTrace
    global StoredTraces    
    # Save the "live" wave
    TempPrimaryFFT = FFTresult.copy()
    DBlevel = DBlevel - 1
    #now recreate traces from the FFT data. Start with stored so the last Primary is the real Primary
    Index = 0
    if CurrentStoredTrace != -1:
        while Index <= CurrentStoredTrace:
            FFTresult = StoredFFT[Index].copy()
            MakeTrace() #makes PrimaryTrace from FFTresult
            StoredTraces[Index] = PrimaryTrace.copy() #store PrimaryTrace in correct StoredTraces
            Index = Index + 1
    FFTresult = TempPrimaryFFT.copy() # scale and shift each stored FFT
    UpdateTrace() #makes PrimaryTrace from FFTresult and then MakeScreen for all traces
    
    #if RUNstatus == 0:      # Update if stopped
    #    UpdateTrace()


def Blevel2():
    global RUNstatus
    global DBlevel
    global FFTresult
    global PrimaryTrace
    global StoredTraces
    # Save the "live" wave
    TempPrimaryFFT = FFTresult.copy()
    DBlevel = DBlevel + 1
    #now recreate traces from the FFT data. Start with stored so the last Primary is the real Primary
    Index = 0
    if CurrentStoredTrace != -1:
        while Index <= CurrentStoredTrace:
            FFTresult = StoredFFT[Index].copy()
            MakeTrace() #makes PrimaryTrace from FFTresult
            StoredTraces[Index] = PrimaryTrace.copy() #store PrimaryTrace in correct StoredTraces
            Index = Index + 1
    FFTresult = TempPrimaryFFT.copy() # scale and shift each stored FFT
    UpdateTrace() #makes PrimaryTrace from FFTresult and then MakeScreen for all traces
    
    #if RUNstatus == 0:      # Update if stopped
    #    UpdateTrace()


def Blevel3():
    global RUNstatus
    global DBlevel
    global FFTresult
    global PrimaryTrace
    global StoredTraces
    # Save the "live" wave
    TempPrimaryFFT = FFTresult.copy()
    DBlevel = DBlevel - 10
    #now recreate traces from the FFT data. Start with stored so the last Primary is the real Primary
    Index = 0
    if CurrentStoredTrace != -1:
        while Index <= CurrentStoredTrace:
            FFTresult = StoredFFT[Index].copy()
            MakeTrace() #makes PrimaryTrace from FFTresult
            StoredTraces[Index] = PrimaryTrace.copy() #store PrimaryTrace in correct StoredTraces
            Index = Index + 1
    FFTresult = TempPrimaryFFT.copy() # scale and shift each stored FFT
    UpdateTrace() #makes PrimaryTrace from FFTresult and then MakeScreen for all traces

    #if RUNstatus == 0:      # Update if stopped
    #    UpdateTrace()


def Blevel4():
    global RUNstatus
    global DBlevel
    global FFTresult
    global PrimaryTrace
    global StoredTraces
    # Save the "live" wave
    TempPrimaryFFT = FFTresult.copy()
    DBlevel = DBlevel + 10
    #now recreate traces from the FFT data. Start with stored so the last Primary is the real Primary
    Index = 0
    if CurrentStoredTrace != -1:
        while Index <= CurrentStoredTrace:
            FFTresult = StoredFFT[Index].copy()
            MakeTrace() #makes PrimaryTrace from FFTresult
            StoredTraces[Index] = PrimaryTrace.copy() #store PrimaryTrace in correct StoredTraces
            Index = Index + 1
    FFTresult = TempPrimaryFFT.copy() # scale and shift each stored FFT
    UpdateTrace() #makes PrimaryTrace from FFTresult and then MakeScreen for all traces

    #if RUNstatus == 0:      # Update if stopped
    #    UpdateTrace()


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
    global PrimaryTrace
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

def BClearTraces():
    global PrimaryTrace
    global StoredTraces
    global STOREtrace
    global CurrentStoredTrace
    global PeakValuedBm
    global FFTresult
    #FFTresult = []
    PrimaryTrace = []
    StoredTraces = [[]]*6
    STOREtrace = False
    CurrentStoredTrace = -1
    PeakValuedBm = -9999.0
    ca.delete("peak_marker")
    UpdateScreen()
    #root.update()

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
    global PrimaryTrace
    global StoredTraces
    global FFTresult
    # Save the "live" wave
    TempPrimaryFFT = FFTresult.copy()    
    if (DBdivindex >= 1):
        DBdivindex = DBdivindex - 1
    #now recreate traces from the FFT data. Start with stored so the last Primary is the real Primary
    Index = 0
    if CurrentStoredTrace != -1:
        while Index <= CurrentStoredTrace:
            FFTresult = StoredFFT[Index].copy()
            MakeTrace() #makes PrimaryTrace from FFTresult
            StoredTraces[Index] = PrimaryTrace.copy() #store PrimaryTrace in correct StoredTraces
            Index = Index + 1
    FFTresult = TempPrimaryFFT.copy() # scale and shift each stored FFT
    UpdateTrace() #makes PrimaryTrace from FFTresult and then MakeScreen for all traces


def BDBdiv2():
    global DBdivindex
    global DBdivlist
    global RUNstatus
    global PrimaryTrace
    global StoredTraces
    global FFTresult
    # Save the "live" wave
    TempPrimaryFFT = FFTresult.copy()
    if (DBdivindex < len(DBdivlist) - 1):
        DBdivindex = DBdivindex + 1
    #now recreate traces from the FFT data. Start with stored so the last Primary is the real Primary
    Index = 0
    if CurrentStoredTrace != -1:
        while Index <= CurrentStoredTrace:
            FFTresult = StoredFFT[Index].copy()
            MakeTrace() #makes PrimaryTrace from FFTresult
            StoredTraces[Index] = PrimaryTrace.copy() #store PrimaryTrace in correct StoredTraces
            Index = Index + 1
    FFTresult = TempPrimaryFFT.copy() # scale and shift each stored FFT
    UpdateTrace() #makes PrimaryTrace from FFTresult and then MakeScreen for all traces

def SetTrackingGen():
    global X0L          # Left top X value
    global Y0T          # Left top Y value
    global GRW          # Screenwidth
    global GRH          # Screenheight
    global SIGNAL1
    global RUNstatus
    global SWEEPsingle
    global SAMPLErate
    global SAMPLEsize
    global UPDATEspeed
    global STARTfrequency
    global STOPfrequency
    global COLORred
    global COLORcanvas
    global COLORyellow
    global COLORgreen
    global COLORmagenta
    global ColorStoredTrace

    ZerodBmm = 0.632        #Volts for 0dBm
    TrackingIncrement = 1   #frequency step in kHz
    #scope.write(":SOUR1:FUNC:SIN")          #set generator to sinusoid for sweeping
    #scope.write(":SOUR1:VOLT ", ZerodBm)
    #scope.write(":SOUR1:FREQ:", STARTfrequency)
    scope.write(":SOUR1:MOD 0")             #turn off modulation
    scope.write(":SOUR1:OUTP:IMP OMEG")     #high impedance mode
    scope.write("SOUR1:APPL:SIN ", STARTfrequency, ",", ZerodBmm)
    scope.write(":SOUR1:OUTP ON")           #turn sourcen
    


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
    global ChannelChoice
    global UPDATEspeed
    global STARTfrequency
    global STOPfrequency
    global COLORred
    global COLORcanvas
    global COLORyellow
    global COLORgreen
    global COLORmagenta
    global ColorStoredTrace

    while (True):                                           # Main loop

        #print("Runstatus: ", RUNstatus)
        # RUNstatus = 1 : Open Stream
        if (RUNstatus == 1):
            if UPDATEspeed < 1:
                UPDATEspeed = 1.0

            TRACESopened = 1

            try:
                # Rossi code to open first resource
                rm = visa.ResourceManager()
                instruments = rm.list_resources()
                #print( res )
                #scope = rm.open_resource( res[0] ) # !scope = rm.open_resource()

                # Get the USB device, e.g. 'USB0::0x1AB1::0x0588::DS1ED141904883'
                #instruments = visa.get_instruments_list()
                #print ( 'List of instruments ', instruments )
                #print( 'Instrument 0 = ', instruments[0])
                #VXI = filter(lambda x: 'TCPIP' in x, instruments)
                #if len(VXI) != 1:
                #    print ('Bad instrument list', instruments)
                #    sys.exit(-1)
                #print ( 'TCPIP variable = ', VXI )
                #scope = visa.instrument(VXI[0], timeout=200, chunk_size=1024000) # bigger timeout for long mem
                scope = rm.open_resource( instruments[0] )
                RUNstatus = 2
            except:
                RUNstatus = 0
                showerror("VISA Error","Cannot open scope")

            UpdateScreen()            # UpdateScreen() call


        # RUNstatus = 2: Reading data from scope
        try:
            if (RUNstatus == 2):
                #set up the scope to acquire with correct parms
                scope.write(":STST:BEEP 0") #turn off scope sounds                 
                #sample and data set from current scope setting
                SAMPLErate = scope.query_ascii_values(':ACQ:SRAT?')[0] #do this second
                try:
                    data_length = scope.query_ascii_values(':ACQ:MDEP?')[0]
                except:
                    #if data_length == "AUTO":
                    scope.write(":ACQ:MDEP 6000000")
                data_length = int(scope.query_ascii_values(':ACQ:MDEP?')[0])
                #print('Data length from scope:', data_length, "Sample rate from scope:", SAMPLErate)
                #print('Will sample with command:',":WAV:SOUR CHAN" + str(ChannelChoice))
                scope.write(":WAV:SOUR CHAN" + str(ChannelChoice))
                scope.write(":STOP")
                scope.write(":TRIG:SWE SING") #set single trigger mode so STOP plus acquire time can be used to read wave from screen
                #print("end of commands after STOP")
                txt = "->Acquiring wave from scope"
                x = X0L + 275
                y = Y0T+GRH+32
                ca.create_text (x, y, text=txt, anchor=W, fill=COLORgreen, tag="aquire_status")
                root.update()       # update screen

                #Force single trigger and wait for the waveform to fully capture
                scope.write(':SING')
                sleep(0.5) #give scope a chance to settle on a status
                trigger_status = scope.query(":TRIG:STAT?")
                #print("1st char", trigger_status[0], "full status", trigger_status)
                #if sample rate is 5Ms/sec or slower, then scope is slow and needs check for completion
                #this is a pretty hokie solution!
                T1 = time.time() #log time to give warning to check scope trigger
                if SAMPLErate <= 2000000:
                    # need to compare to first character only since there is some extra char at end of string
                    while trigger_status[0] != ("R" or "W" or "T"): #loop to wait to enter RUN state
                        trigger_status = scope.query(":TRIG:STAT?") 
                        sleep(0.1)
                        #print("Wait for Run. 1st char", trigger_status[0], "full status", trigger_status)
                        T2 = time.time()
                        if T2 - T1 > 10:  #give screen warning and stop acquire
                            Warning = TRUE
                            txt = ">>> CHECK SCOPE TRIGGER! <<<"
                            x = X0L + 275
                            y = Y0T+GRH+32
                            ca.delete("aquire_status")
                            ca.create_text (x, y, text=txt, anchor=W, fill=COLORred, tag="check_trigger")
                            root.update()       # update screen
                            sleep(10) #give some time for warning to show
                            RUNstatus = 0 #set stop status
                            ca.delete("check_trigger")
                            dummyvariable = 1/0 #throw an error to exit to "except:"
                while trigger_status[0] != "S": #loop to wait for STOP state (wave completly captured)
                    trigger_status = scope.query(":TRIG:STAT?") 
                    sleep(0.1)
                    #print("Wait for Stop. 1st char", trigger_status[0], "full status", trigger_status)
                    T2 = time.time()
                    if T2 - T1 > 10:  #give screen warning and stop acquire
                        Warning = TRUE
                        txt = ">>> CHECK SCOPE TRIGGER! <<<"
                        x = X0L + 275
                        y = Y0T+GRH+32
                        ca.delete("aquire_status")
                        ca.create_text (x, y, text=txt, anchor=W, fill=COLORred, tag="check_trigger")
                        root.update()       # update screen
                        sleep(10) #give some time for warning to show
                        RUNstatus = 0 #set stop status
                        ca.delete("check_trigger")
                        dummyvariable = 1/0 #throw an error to exit to "except:"
                #this grabs an array of bytes
                #if larger than 250,000 then need to break up reads
                scope.write(":WAV:MODE NORM")
                scope.write(":WAV:FORM ASC")                
                wave_parms = []
                wave_parms.extend(scope.query_ascii_values(":WAV:PRE?"))
                Wave_Format = wave_parms.pop(0)
                Wave_Type = wave_parms.pop(0)
                Wave_Points = wave_parms.pop(0)
                Wave_Count = wave_parms.pop(0)
                Wave_XInc = wave_parms.pop(0)
                Wave_XOrig = wave_parms.pop(0)
                Wave_XRef = wave_parms.pop(0)
                Wave_YInc = wave_parms.pop(0)
                Wave_YOrig = wave_parms.pop(0)
                Wave_YRef = wave_parms.pop(0)
                scope.write(":WAV:MODE RAW")
                scope.write(":WAV:FORM BYTE")
                if data_length < 250000:
                    read_length = data_length
                else:
                    read_length = 250000         
                NumReads = int(data_length/read_length) #will leave some points unread if not even divide
                reads = 0
                signals = []
                data_size = len(signals)
                #print ( 'Cleared data size = ', data_size)
                #get waveform parameters

                T1 = time.time() 
                while reads < NumReads:
                    start_read = read_length * reads + 1 
                    stop_read = start_read + read_length - 1
                    scope.write(":WAV:STAR " + str(start_read))
                    scope.write(":WAV:STOP " + str(stop_read))
                    #print("data length:", data_length,"start:", start_read, "stop:",stop_read, "read length:",read_length)
                    #signals.extend(scope.query_binary_values(":WAV:DATA?", datatype='s', data_points=read_length))
                    #option "is_big_endian"=True/False default is FALSE to reverse order of data if needed
                    #chunk_size matching data_length speeds reads by 33% for long data
                    signals.extend(scope.query_binary_values(":WAV:DATA?", datatype='s', chunk_size=read_length, is_big_endian=False))
                    #for count in "0,1,2,3,4,5,6,7,8,9,10":
                    #    header = signals.pop(0) #discard the 11 bytes of header before the wave data
                    #No need! the VIVisa function accounts for an ieee header in the data transfer
                    #print ("current data length=",len(signals))
                    reads = reads + 1
                    x = X0L+275
                    y = Y0T+GRH+48
                    ca.delete ("read_status") #delete canvas object tag=read_status
                    root.update()       # update screen     
                    txt = "read " + str(stop_read) + " of " + str(data_length) + " bytes"
                    ca.create_text (x, y, text=txt, anchor=W, fill=COLORgreen, tag="read_status")
                    root.update()       # update screen                
                data_size = len(signals)
                T2 = time.time()
                #print("Data read time: ",T2 - T1, "s")
                #print( 'Final data size = ', data_size)
                ca.delete ("read_status")
                root.update()       # update screen  

                #check for min/max readings to indicate clipping
                max_reading = 0
                min_reading = 255
                reads = 0
                while reads < data_size:
                    if signals[reads] > max_reading:
                        max_reading = signals[reads]
                    if signals[reads] < min_reading:
                        min_reading = signals[reads]
                    reads = reads + 1
                if min_reading == 0 or max_reading == 255:
                    txt = "!!CLIPPING DETECTED!!"
                    ca.create_text (x, y, text=txt, anchor=W, fill=COLORred, tag="clipping_status")
                    root.update()       # update screen
                    sleep(5)
                    ca.delete ("clipping_status")
                    root.update()       # update screen      
                
                SIGNAL1 = signals
                #Use the YOrigin, YReference, and YIncrement data to convert to volts
                # (Data - YOrig - YRef) * Yinc
                SIGNAL1 = numpy.subtract(SIGNAL1, Wave_YOrig)
                SIGNAL1 = numpy.subtract(SIGNAL1, Wave_YRef)
                SIGNAL1 = numpy.multiply(SIGNAL1, Wave_YInc)
                SIGNAL1 = numpy.multiply(SIGNAL1, CalibFactor) #adjust so dBm values are correct
                #print (signals[0],signals[1],signals[2],signals[3])
                #print (SIGNAL1[0],SIGNAL1[1],SIGNAL1[2],SIGNAL1[3])

                UpdateAll()  # Update Data, trace and screen

                if SWEEPsingle == True:  # single sweep mode, sweep once then stop
                    SWEEPsingle = False
                    RUNstatus = 3

                # RUNstatus = 3: Stop
                # RUNstatus = 4: Stop and restart
                #if (RUNstatus == 3) or (RUNstatus == 4):
                #    scope.write(":KEY:FOR")
                #    scope.close()
                if RUNstatus == 3:
                    RUNstatus = 0   # Status is stopped
                if RUNstatus == 4:
                    RUNstatus = 1   # Status is (re)start
                UpdateScreen()          # UpdateScreen() call
        except:
            pass #way to "clean" exit when there is some scope issue
        # Update tquerys and screens by TKinter
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
    ca.delete ("aquire_status")
    txt = "->Processing FFT"
    x = X0L + 275
    y = Y0T+GRH+32
    ca.create_text (x, y, text=txt, anchor=W, fill=COLORgreen, tag="fft_status")
    root.update()       # update screen

    T1 = time.time()                        # For time measurement of FFT routine

    REX = []
    IMX = []


    #scale fftsamples
    fftexponent = 0
    data_size = len(SIGNAL1)
    for fftexponent in range(13,24):
        fftsamples = 2**fftexponent
        if fftsamples*2 >= data_size: #check to see if one more take it above
            break
        fftexponent = fftexponent + 1
        #print("fftsamples: ", fftsamples)
    
    #print("Buffersize:" + str(len(SIGNAL1)) + " FFTsize: " + str(fftsamples))
    SAMPLEsize= fftsamples

    n = 0
    SIGNALlevel = 0.0
    v = 0.0
    m = 0                                   # For calculation of correction factor
    while n < fftsamples:

        v=SIGNAL1[n]
        # Check for overload
        va = abs(v)                         # Check for peak input level
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

    FFTmemory = FFTresult  #save prevous result for comparison
    FFTresult = [] #clear current list for new data

    #print len(FFTmemory)
    T2 = time.time()
    #print("FFT calc time: ",T2 - T1, "s") # For time measurement of FFT routine
    T1 = time.time()
    ca.delete ("fft_status")
    root.update()
    txt = "->Creating waveform"
    x = X0L + 275
    y = Y0T+GRH+32
    ca.create_text (x, y, text=txt, anchor=W, fill=COLORgreen, tag="waveform_status")
    root.update()

    n = 0
    while (n <= fftsamples / 2):
        # For relative to voltage: v = math.sqrt(REX[n] * REX[n] + IMX[n] * IMX[n])    # Calculate absolute value from re and im
        v = REX[n] * REX[n] + IMX[n] * IMX[n]               # Calculate absolute value from re and im relative to POWER!

        v = v * Totalcorr                    # Make level independent of samples and convert to display range

     

        if TRACEmode == 2 and PeakValuedBm != -9999.0: # and TRACEreset == True:          # Max hold, change v to maximum value
            if v < FFTmemory[n]:
                v = FFTmemory[n]

        if TRACEmode == 3 and PeakValuedBm != -9999.0: # and TRACEreset == True:          # Average, add difference / TRACEaverage to v
            # add difference from previous scaled by TRACEaverage entry
            v = FFTmemory[n] + (v - FFTmemory[n]) / TRACEaverage
        
        FFTresult.append(v)    # Append the value to the FFTresult array
        n = n + 1

            ##a rolling average across TraceAverage values
            #i_fft = n
            #v_avg = 0
            #while ((i_fft - n) < TRACEaverage):
            #    v_avg = v_avg + ((REX[i_fft] * REX[i_fft] + IMX[i_fft] * IMX[i_fft]) * Totalcorr)
            #    i_fft = i_fft + 1
            #v = v_avg / TRACEaverage
            #
            #
            #i_fft = n
            #v_avg = 0
            #while ((i_fft - n) < TRACEaverage):
            #    FFTresult.append(v)    # Append the value to the FFTresult array
            #    i_fft = i_fft + 1
            #n = n + TRACEaverage

    TRACEreset = False                                      # Trace reset done

    T2 = time.time()
    #print("FFT smoothing time: ",T2 - T1, "s") # For time measurement of FFT routine



def MakeTrace():        # Update the grid and trace
    global FFTresult
    global PrimaryTrace
    global StoredTraces
    global CurrentStoredTrace
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
    global PeakValuedBm
    global MinValuedBm
    global ASPeakValuedBm
    global ASMinValuedBm
    global BestdBdivIndex
    global PeakFrequency
    global xPeak
    global yPeak


    # Set the TRACEsize variable
    TRACEsize = len(FFTresult)      # Set the trace length
    #print("FFTresult length: ", len(FFTresult))
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
    #print("FPixel: ", Fpixel,"FSample:", Fsample)
    PrimaryTrace = []
    n = 0
    Slevel = 0.0            # Signal level
    Nlevel = 0.0            # Noise level
    PeakValuedBm = -9999.0
    MinValuedBm = 9999.0
    while n < TRACEsize:
        F = n * Fsample

        if F >= STARTfrequency and F <= STOPfrequency:
            x = X0L + (F - STARTfrequency)  / Fpixel
            PrimaryTrace.append(int(x + 0.5))
            try:
                ydB =  10 * math.log10(float(FFTresult[n]))  # Convert power to DBs, except for log(0) error
                y =  Yc - Yconv * ydB  # Convert to screen location
                # Find peak 
                #Ya = abs(y)
                if ydB > PeakValuedBm:
                    PeakValuedBm = ydB
                    PeakFrequency = F 
                if ydB < MinValuedBm:
                    MinValuedBm = ydB                    
            except:
                y = Ymax

            if (y < Ymin):
                y = Ymin
            if (y > Ymax):
                y = Ymax
            PrimaryTrace.append(int(y + 0.5))

            if SNenabled == True:         
                Slevel = Slevel + float(FFTresult[n]) # Add to signal if inside signal band
        #print("FPixel: ", Fpixel,"FSample:", Fsample, "X: ", x, "Y: ",y)
        n = n + 1
            
        if SNenabled == True and (F < STARTsignalfreq or F > STOPsignalfreq):   # Add to noise if outside signal band
            Nlevel = Nlevel + float(FFTresult[n])

    # Calculate right values for autoscale of all waves
    if CurrentStoredTrace != -1: #a stored wave exists, so AS values are valid
        SignaldBRange = ASPeakValuedBm - ASMinValuedBm #Signal range to use for autoscale
    else:
        SignaldBRange = PeakValuedBm - MinValuedBm #Signal range to use for autoscale
        ASPeakValuedBm = PeakValuedBm #safe if no stored wave. Value is used in autoscale
        ASMinValuedBm = MinValuedBm
    SignaldBDiv = SignaldBRange / Vdiv
    for dBdivIndex in range(1,len(DBdivlist)):
        if SignaldBDiv <= DBdivlist[dBdivIndex]:
            BestdBdivIndex = dBdivIndex
            break #found right value so exit for
    
    #calculate marker at peak location. It gets drawn with the trace in MakeScreen
    yPeak =  Yc - Yconv * PeakValuedBm
    xPeak = X0L + (PeakFrequency - STARTfrequency)  / Fpixel
    
    #print ("Range:", SignaldBRange, " Best Div:", BestdBDiv)

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
    global PrimaryTrace
    global StoredTraces
    global CurrentStoredTrace
    global S1line
    global S2line
    global STOREtrace
    global Vdiv         # Number of vertical divisions
    global RUNstatus    # 0 stopped, 1 start, 2 running, 3 stop now, 4 stop and restart
    global ChannelChoice  # 1 or 2
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
    global ColorStoredTrace
    global COLORtext
    global COLORsignalband
    global COLORaudiobar
    global COLORaudiook
    global COLORaudiomax
    global CANVASwidth
    global CANVASheight
    global PeakValuedBm
    global PeakFrequency
    global xPeak
    global yPeak


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
        ca.create_text (x3, y-5, text=txt, anchor=W, fill=COLORtext)
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
        ca.create_text (x-10, y2+10, text=txt, anchor=W, fill=COLORtext)
        freq=freq+freqstep
        i = i + 1

    # Draw traces
    if len(PrimaryTrace) > 4:                                     # Avoid writing lines with 1 coordinate
        ca.create_line(PrimaryTrace, fill=COLORtrace1)            # Write the trace 1

    Index = 0
    if CurrentStoredTrace != -1:
        while Index <= CurrentStoredTrace:
            ca.create_line(StoredTraces[Index], fill=ColorStoredTrace[Index])   # Write each stored trace
            Index = Index + 1

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
    ca.create_text (x, y, text=txt, anchor=W, fill=COLORtext)

    if PeakValuedBm > -9999:
        #make message at top of screen
        x = X0L + 550
        txt = "Peak = " + str("{:.2f}".format(PeakValuedBm)) + " dBm @" + str("{:.3f}".format(PeakFrequency/1e6)) + "MHz"
        ca.create_text (x, y, text=txt, anchor=W, fill=COLORtext, tag="peakdB_status")
        #put marker at peak
        ca.create_polygon(xPeak-3,yPeak, xPeak,yPeak-3, xPeak+3,yPeak, xPeak,yPeak+3, outline=COLORred, width=2, tag="peak_marker")

    # Start and stop frequency and dB/div and trace mode
    txt = str(STARTfrequency/1000000) + " to " + str(STOPfrequency/1000000) + " MHz"
    txt = txt +  "    " + str(DBdivlist[DBdivindex]) + " dBm/div"
    txt = txt + "    Level: " + str(DBlevel) + " dBm "

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
    ca.create_text (x, y, text=txt, anchor=W, fill=COLORtext)


    # Soundcard level bargraph  ROSSI Useless for scope FFT
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

    ca.create_text (x, y, text=txt1, anchor=W, fill=COLORaudiobar)

    if SIGNALlevel >= 1.0:
        ca.create_text (x, y, text=txt, anchor=W, fill=COLORaudiomax)
    else:
        ca.create_text (x, y, text=txt, anchor=W, fill=COLORaudiook)


    # Runstatus and level information
    if (ChannelChoice == 1):
        txt = "Channel 1"
    else:
        txt = "Channel 2"

    if (RUNstatus == 0) or (RUNstatus == 3):
        txt = txt + " Sweep stopped"
    else:
        txt = txt + " Sweep running"

    x = X0L + 100
    y = Y0T+GRH+32
    ca.create_text (x, y, text=txt, anchor=W, fill=COLORtext)

# show the values at the mouse cursor
# note the magic numbers below were determined by looking at the cursor values
# not sure why they don't correspond to X0T and Y0T
    cursorx = (STARTfrequency + (root.winfo_pointerx()-root.winfo_rootx()-X0L-4) * (STOPfrequency-STARTfrequency)/GRW) /1000000
    cursory = DBlevel - (root.winfo_pointery()-root.winfo_rooty()-Y0T-50) * Vdiv*DBdivlist[DBdivindex] /GRH

    txt = "Cursor " + str("{:.3f}".format(cursorx))  + " MHz   " + str(cursory) + " dBm"

    x = X0L+800
    y = 12
    ca.create_text (x, y, text=txt, anchor=W, fill=COLORtext)
"""
    Marker1valid=False
    if ((Marker1x > 20) & (Marker1y >20)): # show on screen markers
        Marker1valid=True
        ca.create_text (Marker1x-3, Marker1y+4, text="^", anchor=W, fill=COLORMarker1)
        Marker1freq = (STARTfrequency + (Marker1x-19) * (STOPfrequency-STARTfrequency)/GRW) /1000000
        Marker1db = DBlevel - (Marker1y-20) * Vdiv*DBdivlist[DBdivindex] /GRH
        txt = "Marker1 " + str(Marker1freq)  + " MHz   " + str(Marker1db) + " dB"
        x = X0L + 300
        y = Y0T -10
        ca.create_text (x, y, text=txt, anchor=W, fill=COLORMarker1)

    Marker2valid=False
    if ((Marker2x > 20) & (Marker2y >20)): # show on screen markers
        Marker2valid=True
        ca.create_text (Marker2x-3, Marker2y+4, text="^", anchor=W, fill=COLORMarker2)
        Marker2freq = (STARTfrequency + (Marker2x-19) * (STOPfrequency-STARTfrequency)/GRW) /1000000
        Marker2db = DBlevel - (Marker2y-20) * Vdiv*DBdivlist[DBdivindex] /GRH
        txt = "Marker2 " + str(Marker2freq)  + " MHz   " + str(Marker2db) + " dB"
        x = X0L + 520
        y = Y0T -10
        ca.create_text (x, y, text=txt, anchor=W, fill=COLORMarker2)

    # show marker delta only if both are valid
    if (Marker1valid & Marker2valid):
        Deltafreq = abs(Marker2freq-Marker1freq)
        Deltadb = abs(Marker2db-Marker1db)
        txt = "Delta " + str(Deltafreq)  + " MHz   " + str(Deltadb) + " dB"
        x = X0L + 750
        y = Y0T -10
        ca.create_text (x, y, text=txt, anchor=W, fill=COLORtext)

"""

# ================ Make Screen ==========================

root=Tk()
root.title("Rigol Spectrum Analyzer V1.5 01-20-2021 KK1L")

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

b = Button(frame1, text="Calibration", width=Buttonwidth1, command=BCalibration)
b.pack(side=RIGHT, padx=5, pady=5)

b = Button(frame1, text="AutoScale", width=Buttonwidth1, command=BAutoScale)
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



b = Button(frame3, text="Channel", width=Buttonwidth1, command=BChannelChoice)
b.pack(side=LEFT, padx=5, pady=5)

b = Button(frame3, text="Single", width=Buttonwidth1, command=BSINGLEsweep)
b.pack(side=LEFT, padx=5, pady=5)

b = Button(frame3, text="Startfreq", width=Buttonwidth2, command=BStartfrequency)
b.pack(side=LEFT, padx=5, pady=5)

b = Button(frame3, text="Stopfreq", width=Buttonwidth2, command=BStopfrequency)
b.pack(side=LEFT, padx=5, pady=5)

b = Button(frame3, text="Clear", width=Buttonwidth2, command=BClearTraces)
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
UpdateScreen() # try this here to show screen
Sweep()




