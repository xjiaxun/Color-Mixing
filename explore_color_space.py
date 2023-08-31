
import tkinter as tk
from tkinter import ttk
import tkinter.colorchooser
from serial.tools.list_ports import comports
from matplotlib.ticker import MaxNLocator
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import (FigureCanvasTkAgg, NavigationToolbar2Tk)
import os
import time
import datetime
import math
import numpy as np
from numpy import save
#import logging
#import threading
#from threading import Timer
from scipy import interpolate
import csv


from seabreeze.spectrometers import Spectrometer
from colormath.color_objects import SpectralColor, CMYColor, sRGBColor
from colormath.color_conversions import convert_color
from pump import *
import RGB_Project_Automation as auto
import optimization_4steps as opt
import RGB_Project_ScaleNewRates as scale


# Connect to spectrometer
spec = Spectrometer.from_first_available()
print(spec)

# acquire a spectrum
# set integration time
spec.integration_time_micros(1000000)  # 1.5 seconds
spec.spectrum()
spec.spectrum()

if input("Scan reference"):
    wavelengths, ref_intensities = spec.spectrum()
    plt.plot(wavelengths, ref_intensities)
    plt.xlabel('Wavelengths in (nm)')
    plt.ylabel('Intensity in (a.u.)')
    plt.show()
    if input('save? [y/n]') == 'y':
        title = input("save as title: ")
        save(str(title)+'.npy',ref_intensities)

if input("Scan background"):
    wavelengths, bg_intensities = spec.spectrum()
    plt.plot(wavelengths, bg_intensities)
    plt.xlabel('Wavelengths in (nm)')
    plt.ylabel('Intensity in (a.u.)')
    plt.show()
    if input('save? [y/n]') == 'y':
        title = input("save as title: ")
        save(str(title)+'.npy',bg_intensities)


save('wavelength.npy',wavelengths)




# Connect to pumps
chain = Chain(port='COM8')
no_of_pumps = 4
pumps = [Pump(chain, address=i) for i in range(no_of_pumps)]  #Create a list of pump objects

# Set syringe diameter
syr_dia = 14.57
for pump in pumps:
    pump.set_diameter(syr_dia)


# Set Constants
explore_rates = [0, 30, 60, 90, 120, 150] # ul/min
explore_ratio = [3,2,1,0] # ratio of flowrates
tube_dist = 1000 #mm
extra_waiting = 10 #sec
sum_rates = 600 # constant sum flowrates

# Open Data csv
with open('Nov3 Parameter Scan ratio_w 0.csv', 'w', newline='') as datacsv:
    datawriter = csv.writer(datacsv, delimiter=',')
    datawriter.writerow(["Qwater", "Qmagenta", "Qyellow", "Qcyan", "R", "G", "B", datetime.datetime.now()])


    # Set rates based on flowrates intervals
    #for rate_W in explore_rates:
    #    pumps[0].set_infuse_rate(rate_W)
    #    for rate_M in explore_rates:
    #        pumps[1].set_infuse_rate(rate_M)
    #        for rate_Y in explore_rates:
    #            pumps[2].set_infuse_rate(rate_Y)
    #            for rate_C in explore_rates:
    #                pumps[3].set_infuse_rate(rate_C)

    # Set rates based on ratio intervals 
    for W in [0]:
        for M in explore_ratio:
            for Y in explore_ratio:
                for C in explore_ratio:
                    if W+M+Y+C == 0:
                        continue
                    rates = [sum_rates/(W+M+Y+C)*i for i in [W, M, Y, C]]

                    for i in range(4):
                        pumps[i].set_infuse_rate(rates[i])
                    

                    #(keep the repeating rates ratio, e.g. 30:30:30:30 and 60:60:60:60
                    # to check the data precision. Precision error should be <+-3)

                    # run pumps
                    for pump in pumps:
                        pump.infuse()
                        time.sleep(0.1)


                    wait_time = auto.calc_time_to_travel(rates, tube_dist, 0.254, extra_waiting)
                    time.sleep(wait_time)

                    intensities = spec.spectrum()[1]
                    save('intensity_of_'+str(rates)+'.npy', intensities)
            
                    transmittance = (intensities-bg_intensities)/(ref_intensities-bg_intensities)
                    # ignore transmittance out of range, which is due to the noise
                    transmittance[transmittance>1]=1
                    transmittance[transmittance<0]=0

                    f = interpolate.interp1d(wavelengths,transmittance)
                    wavelengths_new = np.arange(340, 840, 10)
                    transmittance_new = f(wavelengths_new)
                    spectral = SpectralColor(*transmittance_new,observer='10')
                    rgb = convert_color(spectral, sRGBColor).get_upscaled_value_tuple()
                    rgb = np.asarray(rgb)
                    rgb[rgb>255]=255

                    rgb_info = [*rates, *rgb]

                    # save to csv
                    datawriter.writerow(rgb_info)

            
for pump in pumps:
    pump.stop()
    time.sleep(0.1)