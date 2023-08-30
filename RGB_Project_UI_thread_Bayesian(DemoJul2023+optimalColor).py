''' User Interface of the RGB color optimzation project 
    Jiaxun Xie

    May, 2023
    Modifications and updates based on RGB_Project_UI_thread_variedStep_random.py:
    1. Added Bayesian algorithm in the program, to be run alone or in parallel with
    the gradient descnet algorithm

    Todo:
    1. Add vary BO parameter kappa, decrease kappa if min(costs) is small => exploit more
                                    increase kappa if min(costs) is large => explore more
    2. Add scale the scout steps rates to sum(rates)=600


'''

import matplotlib
matplotlib.use('Agg')
from matplotlib.ticker import MaxNLocator
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import (FigureCanvasTkAgg, NavigationToolbar2Tk)
from matplotlib.lines import Line2D
import tkinter as tk
from tkinter import ttk
import tkinter.colorchooser
from serial.tools.list_ports import comports
import os
import time
import datetime
import math
import numpy as np
import logging
import threading
from threading import Timer
import scipy
import queue
from bayes_opt import BayesianOptimization, UtilityFunction
from scipy.optimize import NonlinearConstraint

from seabreeze.spectrometers import Spectrometer
from colormath.color_objects import SpectralColor, CMYColor, sRGBColor
from colormath.color_conversions import convert_color
from pump import *
import RGB_Project_Automation as auto
import optimization_4steps as opt
import RGB_Project_ScaleNewRates as scale

            


def from_rgb(rgb):
    """translates an rgb tuple of int to a tkinter friendly color code
    """
    return "#%02x%02x%02x" % tuple(rgb)

def serial_ports():
    ''' get available com ports '''
    return comports()

class PrgmLogger():
    ''' log experiment informationm and save data to local

    Directory content:
    - RGB_Optimization_(datetime):
        - Ref_(datetime).npy
        - BG_(datetime).npy
        - Experiment_(datetime):
            - Log.log
            - rgb_tracking.log
            - plot.png
            - Data:
                - Spec_(itr#)_(datetime).npy
                    :
                    :
    '''

    def __init__(self):
        self.path = os.getcwd()
        self.run_path = ''
        self.exp_path = ''
        self.data_path = ''
        self.info_log_file = ''
        self.rgb_log_file = ''
        self.ref_file = ''
        self.bg_file = ''
        self.spec_file = ''

    def setup_logger(self, name, log_file, level=logging.INFO):

        handler = logging.FileHandler(log_file)        
        handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)-8s %(message)s'))

        logger = logging.getLogger(name)
        logger.setLevel(level)
        logger.addHandler(handler)

        return logger
    
    def create(self,type=''):
        # create folder or file path
        cur_time = datetime.datetime.now()
        if type == 'RGB':
            self.run_path = self.path+cur_time.strftime('\Data\RGB_Optimization_%Y-%m-%d_%H-%M-%S')
            os.makedirs(self.run_path, exist_ok=True)
        if type == 'Experiment':
            if self.run_path == '':
                print('run path does not exist')
            else:
                self.exp_path = self.run_path+cur_time.strftime('\Experiment_%Y-%m-%d_%H-%M-%S')
                os.makedirs(self.exp_path, exist_ok=True)

        if type == 'Data':
            if self.exp_path == '':
                print('exp path does not exist')
            else:
                self.data_path = self.exp_path + '\Data'
                os.makedirs(self.data_path, exist_ok=True)

        if type == 'Log':
            if self.exp_path == '':
                print('exp path does not exist')
            else:
                self.info_log_file = cur_time.strftime(self.exp_path+'\Log.log')
                self.rgb_log_file = cur_time.strftime(self.exp_path+'\RGB_history.log')
                self.info_logger = self.setup_logger('info_logger', self.info_log_file)
                self.rgb_logger = self.setup_logger('rgb_logger', self.rgb_log_file)
                self.info_logger.info('Color Optimization in RGB Program -- RUN')
                self.rgb_logger.info('R, G, B')
                
    def log(self,type='', input=''):
        # write to log files
        if type == 'log':
            try:
                self.info_logger.info(str(input))
            except AttributeError:
                print('logger not created')
        if type == 'rgb':
            try:
                self.rgb_logger.info(str(input))
            except AttributeError:
                print('logger not created')

    def save_data(self,type='',input=None):
        # save data to local
        cur_time = datetime.datetime.now()
        if type == 'ref':
            if self.run_path == '':
                print('run path does not exist')
            else:
                self.ref_file = cur_time.strftime(self.run_path+'\Reference_%Y-%m-%d_%H-%M-%S')
                np.save(self.ref_file, input)
        if type == 'bg':
            if self.run_path == '':
                print('run path does not exist')
            else:
                self.bg_file = cur_time.strftime(self.run_path+'\Background_%Y-%m-%d_%H-%M-%S')
                np.save(self.bg_file, input)
        if type == 'spec':
            if self.data_path == '':
                print('data path does not exist')
            else:
                self.spec_file = cur_time.strftime(self.data_path+'\Spect_%Y-%m-%d_%H-%M-%S')
                np.save(self.spec_file, input)
        if type == 'avgspec':
            if self.data_path == '':
                print('data path does not exist')
            else:
                self.avg_spec_file = cur_time.strftime(self.data_path+'\AverageSpect_%Y-%m-%d_%H-%M-%S')
                np.save(self.avg_spec_file, input)
        if type == 'trans':
            if self.data_path == '':
                print('data path does not exist')
            else:
                self.trans_file = cur_time.strftime(self.data_path+'\Spect_%Y-%m-%d_%H-%M-%S')
                np.save(self.trans_file, input)
        if type == 'avgtrans':
            if self.data_path == '':
                print('data path does not exist')
            else:
                self.avg_trans_file = cur_time.strftime(self.data_path+'\AverageTrans_%Y-%m-%d_%H-%M-%S')
                np.save(self.avg_trans_file, input)

    def save_img(self,input=None):
        ''' save mse and rgb images to local '''
        plot_fig = input
        if self.exp_path != '':
            plot_file = self.exp_path + '\plot.png'
            try:
                plot_fig.savefig(plot_file)
            except:
                pass




class App(tk.Tk):
    def __init__(self): 
        super().__init__()

        self.target_color_UI = tk.StringVar()
        self.pumps=[]
        self.pump_conn_bool = tk.BooleanVar(self,0)
        self.spec_conn_bool = tk.BooleanVar(self,0)
        self.spec = None
        self.wavelength=[]
        self.bg_spec=[]
        self.bg_spec_bool = tk.BooleanVar(self,0) # bg spec taken? T/F
        self.ref_spec=[]
        self.ref_spec_bool = tk.BooleanVar(self,0) # ref spec taken? T/F
        self.tube_dist = 200 #mm (i.e. 20cm)
        self.tube_dia = 0.254 #mm
        self.flush_all_rates = [100, 100, 100, 100] # rates to flush
        self.fill_water_rates = [0, 0, 400, 0] # [wrate, mrate, yrate, crate]
        self.init_integ_time = 10000 #microsecond. Initial integration time of spectrometer
        self.integ_time = 0
        self.no_of_avg = 3 # number of spectra to average before converting to an rgb_avg
        self.scout_size_rdm_bool = tk.IntVar(self,False)
        #self.init_rates = [150.0, 150.0, 150.0, 150.0] # initial flow rates
        self.init_rates = [5.0, 5.0, 600.0, 5.0] # initial flow rates
        self.no_iter = 21 # max number of iterations
        self.optimal_rates_gd=[0.0, 0.0, 0.0, 0.0] # initial optimial rates by gradient descent
        self.optimal_rates_bo=[0.0, 0.0, 0.0, 0.0] # initial optimial rates by bayesian optimization

        # create queues to pass values between the main thread (UI) and run experiment thread
        self.qplot = queue.Queue() # plot queue
        self.qmsg = queue.Queue()  # message queue


        # window setup
        self.geometry('800x700')
        self.title('RGB Optimization Program')
        self.title_label = tk.Label(self,text="Color Optimization in RGB",bd=4,font='bold')
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # create a status display
        self.status_string = tk.StringVar(self,'Welcome! Select a color to start.')
        self.status_label = tk.Label(self, textvariable=self.status_string, wraplength=500, height=2)

        # create a button to select a target color from color space
        self.pick_btn=tk.Button(self,
                                text='Pick a color',
                                width = 18,
                                command=self.target_RGB)

        # create an option menu to select the algorithm
        self.algo = tk.StringVar(self,'Pick Algorithm')
        self.algo_menu = tk.OptionMenu(self, self.algo, *['Gradient Descent', 'Bayesian Optim', 'Both'])
        self.algo_menu.config(width=16)

        # create an option menu to select com port of syringe pumps
        ports = [str(port).split(' ')[0] for port in serial_ports()]
        self.com_port = tk.StringVar(self, 'Select Port')
        self.com_menu=tk.OptionMenu(self,self.com_port,*ports)
        self.com_menu.config(width=16)

        # Hidden. For future use
        ## create an option menu to select number of pumps 
        #self.no_of_pumps = tk.StringVar(self,'no. of pumps')
        #self.no_of_pump_menu = tk.OptionMenu(self, self.no_of_pumps, *range(1,7))
        #self.no_of_pump_menu.config(width=16)

        # create a button to connect to pumps
        self.connect_btn = tk.Button(self,
                                      text = 'Connect',
                                      width = 18,
                                      command=self.port_select)
        
        ## create an entry to set syringes diameter
        #self.syringe_diam_txt = tk.Label(self,text='CMY Syringe Diameter(mm)')
        #self.syringe_diam = tk.Entry(self, state='disabled')
        #self.syringe_diam.config(width=22)
        #self.syringe_diam.bind('<Return>', self.set_diam)

        #self.water_syringe_diam_txt = tk.Label(self,text='Water Syringe Diameter(mm)')
        #self.water_syringe_diam = tk.Entry(self, state='disabled')
        #self.water_syringe_diam.config(width=22)
        #self.water_syringe_diam.bind('<Return>', self.set_diam_water)

        # create a button to flush all
        self.flush_all_btn = tk.Button(self,
                                   text = 'Flush All',
                                   width = 18,
                                   command=self.flush_all,
                                   state='disabled')

        # create a button to fill with water
        self.fill_water_btn = tk.Button(self,
                                    text = 'Fill with Water',
                                    width = 18,
                                    command=self.fill_water,
                                    state='disabled')

        # create a button to optimize spectrometer integration time
        self.integ_time_btn = tk.Button(self,
                                  text='Optimize Integ Time',
                                  width = 18,
                                  command=self.find_integ_time,
                                  state="disabled")

        # create a button to take reference spectrum
        self.take_ref = tk.Button(self,
                                  text='Capture Reference',
                                  width = 18,
                                  command=lambda button='ref': self.get_spectrum(button),
                                  state="disabled")

        # create a button to take background spectrum
        self.take_bg = tk.Button(self,
                                 text='Capture Background',
                                 width = 18,
                                 command=lambda button='bg': self.get_spectrum(button),
                                 state="disabled")

        # create a button to start the experiment
        self.start_btn=tk.Button(self,
                                 text='Start',
                                 width=18,
                                 command=self._start_signal, 
                                 state="disabled")

        # create a checkbutton to pick randomize scout steps size or not
        self.rdm_size_check = tk.Checkbutton(self,
                                text = 'random scout steps size',
                                width = 18,
                                variable=self.scout_size_rdm_bool)

        # create a button to run optimal color by gradient descent
        self.optimal_gd_btn=tk.Button(self,
                                 text='Run Optimal GD',
                                 width=18,
                                 command=lambda widget="btn_gd": self.run_optimal(widget),
                                 #state="disabled")
                                 )

        # create a button to run optimal color by gradient descent
        self.optimal_bo_btn=tk.Button(self,
                                 text='Run Optimal BO',
                                 width=18,
                                 command=lambda widget="btn_bo": self.run_optimal(widget),
                                 #state="disabled")
                                 )

        # display mse and rgb figure
        self.fig = plt.Figure(figsize = (5, 5.2),
                   dpi = 100)

        # create the Tkinter canvas containing the Matplotlib figure
        self.canvas = FigureCanvasTkAgg(self.fig,
                                master =self)  
        self.canvas.draw()

        # create two subfigures
        self.mse_fig = self.fig.add_subplot(3,1,1)
        self.mse_fig.xaxis.set_major_locator(MaxNLocator(integer=True, min_n_ticks=1))
        self.mse_fig.yaxis.set_major_locator(MaxNLocator(integer=True, min_n_ticks=1))
        self.mse_fig.set_title('MSE Cost', fontsize=10)
        self.mse_fig.xaxis.set_tick_params(labelsize=8)
        self.mse_fig.yaxis.set_tick_params(labelsize=8)
        self.mse_fig.set_facecolor('#ededed')
        self.legend_elements = [Line2D([0], [0], marker='o', color='k', label='gd',
                          markerfacecolor='w'),
                          Line2D([0], [0], marker='^', color='k', label='bo',
                          markerfacecolor='w')]
        self.mse_fig.legend(handles=self.legend_elements, bbox_to_anchor=(1, 1.02),loc="lower right")
        self.rgb_fig = self.fig.add_subplot(3,1,(2,3),projection='3d')
        self.rgb_fig.set_xlabel('R')
        self.rgb_fig.set_ylabel('G')
        self.rgb_fig.set_zlabel('B')
        self.rgb_fig.xaxis.set_tick_params(labelsize=8)
        self.rgb_fig.yaxis.set_tick_params(labelsize=8)
        self.rgb_fig.zaxis.set_tick_params(labelsize=8)
        # show toolbar
        #toolbar = NavigationToolbar2Tk(canvas, self)
        #toolbar.update()
        self.fig.subplots_adjust(top=0.88,bottom=0.05,hspace=0.15)


        # UI layout
        self.columnconfigure(0,weight=1)
        self.columnconfigure(1,weight=3)

        self.title_label.grid(columnspan=2,pady=5)
        self.status_label.grid(columnspan=2,pady=5)
        self.pick_btn.grid(pady=5)
        self.algo_menu.grid()
        self.rdm_size_check.grid()
        self.com_menu.grid()
        #self.no_of_pump_menu.grid()  # Hidden. For future use
        self.connect_btn.grid()
        #self.syringe_diam_txt.grid(sticky='s')
        #self.syringe_diam.grid(sticky="n")
        #self.water_syringe_diam_txt.grid(sticky='n')
        #self.water_syringe_diam.grid()
        self.flush_all_btn.grid()
        self.fill_water_btn.grid()
        self.integ_time_btn.grid()
        self.take_ref.grid()
        self.take_bg.grid()
        self.start_btn.grid()
        self.optimal_gd_btn.grid()
        self.optimal_bo_btn.grid()
        self.canvas.get_tk_widget().grid(row=2,column=1, rowspan=12)

        self.ref_spec_bool.trace('w',self.enable_start) # condition1/3 to enable start button
        self.bg_spec_bool.trace('w',self.enable_start) # condition2/3 to enable start button
        self.target_color_UI.trace('w',self.enable_start) #condition3/3 to enable start button

        # Create logger
        self.logger = PrgmLogger()
        self.logger.create('RGB')


    def on_closing(self): 
        ''' close application '''
        if tk.messagebox.askokcancel("Quit", "Do you want to quit?"):
            self.destroy()

    def port_select(self):
        ''' estabilish connection with the hardware '''
        self.connect_pump()
        self.connect_spect()
        if self.pump_conn_bool.get() and self.spec_conn_bool.get():
            self.status_string.set('Pumps and spectrometer are connected')
            self.connect_btn.config(text="Connected")
            # disable buttons
            self.com_menu['state'] = 'disabled'
            #self.no_of_pump_menu['state'] = 'disabled'
            self.connect_btn['state'] = 'disabled'


    def connect_pump(self):
        ''' connect to pumps chain '''
        pump_port = self.com_port.get()
        #no_of_pumps = int(self.no_of_pumps.get())
        no_of_pumps = 4 # fixed number of pumps
        pumps = self.pumps

        if len(pumps)==0:
            try:
                chain = Chain(port=pump_port)
                for i in range(no_of_pumps):
                    pumps.append(Pump(chain, address=i))
                # stop all pumps
                for pump in pumps:
                    pump.stop()
                    time.sleep(0.1)

                # return pumps chain
                self.pumps = pumps

                # enable buttons
                #self.syringe_diam['state']='normal'
                #self.water_syringe_diam['state']='normal'
                self.flush_all_btn['state']='normal'
                self.fill_water_btn['state']='normal'
                self.optimal_gd_btn['state']='normal'
                self.optimal_gd_btn['state']='normal'

                self.pump_conn_bool.set(1)
                 
            except serial.serialutil.SerialException as msg:
                tk.messagebox.showerror(title='Pump Connection Error', message=msg)


            # set diameter (since JUL2023 demo)
            diameter = [14.57, 14.57, 23.0, 14.57]
            for i in range(4):
                try:
                    pumps[i].set_diameter(diameter[i])
                    print(pumps[i].read_cur_dia())
                    self.status_string.set('CMY Syringes diameter is set')
                except Exception as msg:
                    tk.messagebox.showerror(title='Pump Error', message=msg)



    def connect_spect(self):
        ''' connect to spectrometer '''
        
        if self.spec == None:
            try:
                self.spec = Spectrometer.from_first_available()
                # enable buttons
                for button in [self.take_bg,self.take_ref,self.integ_time_btn]:
                    button['state']='normal'

                self.spec_conn_bool.set(1)
            except Spectrometer._backend.SeaBreezeError as msg:
                tk.messagebox.showerror(title='Spectrometer Connection Error', message=msg)

    def set_diam(self,event):
        ''' set diameter of the syringes '''
        syr_dia = float(self.syringe_diam.get())
        cmypumps = [self.pumps[0],self.pumps[1],self.pumps[3]]
        if not cmypumps:
            tk.messagebox.showerror(title='Pump Error', message='Pumps are not connected!')
        else:
            for pump in cmypumps:
                try:
                    pump.set_diameter(syr_dia)
                    self.status_string.set('CMY Syringes diameter is set')
                except Exception as msg:
                    tk.messagebox.showerror(title='Pump Error', message=msg)

    def set_diam_water(self,event):
        ''' set diameter of the syringes '''
        syr_dia = float(self.water_syringe_diam.get())
        waterpump = self.pumps[2]
        if not waterpump:
            tk.messagebox.showerror(title='Pump Error', message='Pumps are not connected!')
        else:
            try:
                waterpump.set_diameter(syr_dia)
                self.status_string.set('Water Syringe diameter is set')
            except Exception as msg:
                tk.messagebox.showerror(title='Pump Error', message=msg)
            
    def flush_all(self):
        ''' flush all four pumps together'''
        if self.flush_all_btn['relief'] == 'raised':
            # turn off filling with water if currently running
            if self.fill_water_btn['relief']=='sunken':
                #auto.stop_all(self.pumps)
                self.fill_water_btn['bg'] = '#f0f0f0'
                self.fill_water_btn.config(relief='raised')
            # flush all 
            try:
                auto.set_pump_rates(self.pumps,self.flush_all_rates)
                auto.infuse_all(self.pumps)
                # change button appearance
                self.flush_all_btn['bg']='#00ff00'
                self.flush_all_btn.config(relief='sunken')
                # display status message
                self.status_string.set("Flushing all at "+str(self.flush_all_rates))
            except Exception as msg:
                tk.messagebox.showerror(title='Pump Error', message=msg)
        else:
            # stop all
            auto.stop_all(self.pumps)
            self.flush_all_btn['bg'] = '#f0f0f0'
            self.flush_all_btn.config(relief='raised')
            self.status_string.set('')

    def fill_water(self):
        ''' fill the tubes with water '''
        if self.fill_water_btn['relief'] == 'raised':
            # turn off flushing all if currently running
            if self.flush_all_btn['relief'] == 'sunken':
                #auto.stop_all(self.pumps)
                self.flush_all_btn['bg'] = '#f0f0f0'
                self.flush_all_btn.config(relief='raised')
            try:
                auto.set_pump_rates(self.pumps, self.fill_water_rates)
                auto.infuse_all(self.pumps)
                # change button appearance
                self.fill_water_btn['bg']='#00ff00'
                self.fill_water_btn.config(relief='sunken')
                self.status_string.set("Filling with water at "+str(self.fill_water_rates))
            except Exception as msg:
                tk.messagebox.showerror(title='Pump Error', message=msg)
        else:
            # stop all
            auto.stop_all(self.pumps)
            self.fill_water_btn['bg'] = '#f0f0f0'
            self.fill_water_btn.config(relief='raised')
            self.status_string.set('')

    def find_integ_time(self):
        ''' auto set the uv-vis integration time '''
        integr_time = self.init_integ_time

        try:
            self.status_string.set('Optimizing spectrometer integration time...')
            self.spec.integration_time_micros(integr_time)
            time.sleep(2)
            intensities = self.spec.spectrum()[1]

            while max(intensities) < 55000 and integr_time < 1000000:
                # max integration time: 1sec
                # target max intensity in range(55000, 60000)
                integr_time += 10000
                self.spec.integration_time_micros(integr_time)
                time.sleep(2)
                intensities = self.spec.spectrum()[1]
                if max(intensities) > 60000:
                    integr_time -= 10000
                    self.spec.integration_time_micros(integr_time)
                    time.sleep(2)
                    self.spec.spectrum()
                    break

            self.integ_time = integr_time
            self.status_string.set('Integration time is set to '+str(integr_time)+'microsecond')
        except Exception as msg:
            tk.messagebox.showerror(title='Spectrometer Error', message=msg)

    def get_spectrum(self, button):
        ''' acquire one background/reference spectrum '''
        try:
            self.wavelength, spectrum = self.spec.spectrum()
            if button == 'bg':
                self.bg_spec = spectrum
                self.bg_spec_bool.set(1)
                self.logger.save_data('bg',self.bg_spec)
                self.status_string.set('Background spectrum captured')
                plt.title("Background Spectrum")
            if button == 'ref':
                self.ref_spec = spectrum
                self.ref_spec_bool.set(1)
                self.logger.save_data('ref',self.ref_spec)
                self.status_string.set('Reference spectrum captured')
                plt.title("Reference Spectrum")
            plt.plot(self.wavelength, spectrum)
            plt.pause(0.05)
        except Exception as msg:
            tk.messagebox.showerror(title='Spectrometer Error', message=msg)

    def target_RGB(self):
        ''' set the target RGB from UI selection '''
        try:
            self.target_color_UI.set(tk.colorchooser.askcolor()[0])
            target = np.array([int(i) for i in eval(self.target_color_UI.get())])
            self.target_label = tk.Label(self, text='R: '+str(target[0])+'\n'\
                            +'G: '+str(target[1])+'\n'\
                            +'B: '+str(target[2]),\
                            bg=from_rgb(target)).place(x=170, y=90)
            # Plot target rgb in the 3d plot
            self.rgb_fig.cla()
            self.rgb_fig.set_xlabel('R')
            self.rgb_fig.set_ylabel('G')
            self.rgb_fig.set_zlabel('B')
            self.rgb_fig.scatter(*target, color=target/255.0, marker='*')
            self.canvas.draw()

            self.status_string.set('Color selected!')
        except: # pass if selection is canceled
            pass

    
    def run_optimal(self, widget):
        ''' run the pumps at the flowrates of optimal color'''
        if widget == "btn_gd":
            if self.optimal_gd_btn['relief'] == 'raised':
                # turn off filling with water if currently running
                if self.optimal_bo_btn['relief']=='sunken':
                    self.optimal_bo_btn['bg'] = '#f0f0f0'
                    self.optimal_bo_btn.config(relief='raised')
                try:
                    auto.set_pump_rates(self.pumps,self.optimal_rates_gd)
                    auto.infuse_all(self.pumps)
                    # change button appearance
                    self.optimal_gd_btn['bg']='#00ff00'
                    self.optimal_gd_btn.config(relief='sunken')
                    # display status message
                    self.status_string.set("Running optimal color of GD at "+str(self.optimal_rates_gd))
                except Exception as msg:
                    tk.messagebox.showerror(title='Pump Error', message=msg)
            else:
                # stop all
                auto.stop_all(self.pumps)
                self.optimal_gd_btn['bg'] = '#f0f0f0'
                self.optimal_gd_btn.config(relief='raised')
                self.status_string.set('')

        if widget == "btn_bo":
            if self.optimal_bo_btn['relief'] == 'raised':
                # turn off filling with water if currently running
                if self.optimal_gd_btn['relief']=='sunken':
                    self.optimal_gd_btn['bg'] = '#f0f0f0'
                    self.optimal_gd_btn.config(relief='raised')
                try:
                    auto.set_pump_rates(self.pumps,self.optimal_rates_bo)
                    auto.infuse_all(self.pumps)
                    # change button appearance
                    self.optimal_bo_btn['bg']='#00ff00'
                    self.optimal_bo_btn.config(relief='sunken')
                    # display status message
                    self.status_string.set("Running optimal color of BO at "+str(self.optimal_rates_bo))
                except Exception as msg:
                    tk.messagebox.showerror(title='Pump Error', message=msg)
            else:
                # stop all
                auto.stop_all(self.pumps)
                self.optimal_bo_btn['bg'] = '#f0f0f0'
                self.optimal_bo_btn.config(relief='raised')
                self.status_string.set('')
      
    def enable_start(self,*arg):
        ''' check if the conditions are met to enable "start" button '''
        cond1 = self.ref_spec_bool.get()   # reference spectrum saved
        cond2 = self.bg_spec_bool.get()    # background spectrum saved
        cond3 = len(self.target_color_UI.get())!=0 # target color selected
        if cond1 and cond2 and cond3:
            self.start_btn.config(state="normal")
    

    def run(self):
        ''' run optimization process '''

        # disable all other buttons 
        self.pick_btn['state']='disabled'
        #self.syringe_diam['state']='disabled'
        #self.water_syringe_diam['state']='disabled'
        self.flush_all_btn['state']='disabled'
        self.fill_water_btn['state']='disabled'        
        self.integ_time_btn['state']='disabled'
        self.take_ref['state']='disabled'
        self.take_bg['state']='disabled'
        self.optimal_gd_btn['state']='disabled'
        self.optimal_bo_btn['state']='disabled'

        # create data folder
        self.logger.create('Experiment')
        self.logger.create('Data')
        self.logger.create('Log')

        # get user selected target rgb
        target = np.array([int(i) for i in eval(self.target_color_UI.get())])

        # Initialize variables
        self.prev_cost = 1 # cost of previous iteration
        self.iteration = 0 # iteration index of while loop. itr=0 : run initial condition
        self.min_gd_cost = 100000 # initial minimum gd cost, start from large value
        self.min_bo_cost = 100000 # initial minimum bo cost, start from large value
        self.optimal_rates_gd=[0.0, 0.0, 0.0, 0.0] # initial optimial rates by gradient descent
        self.optimal_rates_bo=[0.0, 0.0, 0.0, 0.0] # initial optimial rates by bayesian optimization

        # Set constants
        small_step_size = 30.0 # first size of small steps for each pump before a real step
        learning_rate = 0.6 # learning rate of the gradient descent optimization
        #diffuse_time = 0.5*0.254**2/(5.75*10**-4) # estimated time to sufficiently diffuse
        diffuse_time = 5
        kappa = 10 # BO parameter to indicate how close the next parameters are sampled


        self.logger.log('log','Experiment START!')
        self.logger.log('log', 'Spectra Integration Time: '+str(self.integ_time))
        self.logger.log('log','Number of Spectra to Average RGB: '+str(self.no_of_avg))
        self.logger.log('log','Diffusion Time: '+str(diffuse_time)+' sec')
        self.logger.log('log','Initial Scout Step Size: '+str(small_step_size))
        self.logger.log('log','Target RGB: '+str(target))
        # Get run experiment thread
        self.run_thread = threading.currentThread()


        def get_one_data(crate, mrate, wrate, yrate, prev_cost = self.prev_cost, iteration = self.iteration, algo="gd"):
            ''' Acquire one real data for GD
                Target function for BO '''
            
            rgb = []

            rates = [crate, mrate, wrate, yrate]
            #rates = [wrate, mrate, yrate, crate]
            
            # create an automation  object
            run_cond = auto.AcquireData(self.pumps,rates,self.tube_dist,self.tube_dia,self.spec,self.ref_spec,
                                                self.bg_spec,self.wavelength,self.no_of_avg,self.logger,diffuse_time)

            # run one step
            run_cond.run_one_cond()
            self.status_string.set("Running at flow rates: "+str([int(i) for i in run_cond.rates])+' for '
                        +str(int(run_cond.wait_sec))+' sec...'
                        #+'\n and diffuse for '
                        #+str(int(diffuse_time))+' sec...'
                        )
            
            # wait to complete one step and get the rgb values
            while len(rgb) == 0:
                # abort if stop button pressed
                if not getattr(self.run_thread, "do_run", True):
                    run_cond.stop_timer()  
                    self.logger.save_img(self.fig)
                    self.logger.log('log','Experiment aborted')
                    self.status_string.set("Experiment Aborted")
                    return None
                # get the average rgb values
                rgb = run_cond.rgb_avg

            # calculate cost in MSE
            cost = opt.cal_cost(target, rgb)
            self.logger.log('log', 'Cost: ' + str(cost))
            #self.status_string.set(self.status_string.get()+' RGB: '+str(rgb)+' Cost: '+str(int(cost)))

            # add to queue to pass to self.updateUI(), looping every 0.1sec
            self.qplot.put([algo,iteration,cost,rgb])

            # update optimal rates for gd or bo
            if algo == "gd":
                if cost < self.min_gd_cost:
                    self.min_gd_cost = cost
                    self.optimal_rates_gd = rates
            if algo == 'bo':
                if cost < self.min_bo_cost:
                    self.min_bo_cost = cost
                    self.optimal_rates_bo = rates

            # show a warning if the cost increased
            if cost-prev_cost > 3000 and prev_cost > 1:
                self.qmsg.put(['Warning', 'Cost increased. Please check if bubbles are stuck in the zcell'])
                self.logger.log('log','Cost increased. Warned user to check bubbles in the tube.')

            # show a warning if the RGB is close to boundary
            boundary1 = rgb[1] <= 85
            boundary2 = rgb[2] > 180 and rgb[1] < 1.2*rgb[2] - 126
            boundary3 = rgb[0] < 150 and rgb[1] < 220-0.9*rgb[0]

            if boundary1 or boundary2 or boundary3:
                if algo == 'gd':
                    self.qmsg.put(['Warning', 'The algorithm is reaching the boundary, it may not converge further.'])
                    self.logger.log('log','Warned user the algorithm is reaching rgb boundary.')

            prev_cost = cost

            return cost

        def get_four_scout(rates, cost):
            ''' proceed to acquire four scout data points '''

            nonlocal small_step_size
            rgb_steps = [] # list to store scout steps rates

            # create an automation  object
            run_cond = auto.AcquireData(self.pumps,rates,self.tube_dist,self.tube_dia,self.spec,self.ref_spec,
                                        self.bg_spec,self.wavelength,self.no_of_avg,self.logger,diffuse_time)

            # get scout steps matrix
            if self.scout_size_rdm_bool.get() == True:
               small_steps_Q = auto.random_small_step_Q(rates) # random scout step size
            else: small_steps_Q = auto.small_step_Q(rates,small_step_size) # fixed scout step size
             
            ## scale scout steps matrix to sum=600
            #for i in range(4):
            #    small_steps_Q[i] *= 600.0/np.sum(small_steps_Q, axis=1)[i]

            self.logger.log('log','Flowrates with Small Step Size: '+str(small_steps_Q))
            
            # loop through scout steps
            for idx, small_step in enumerate(small_steps_Q):
                self.status_string.set("Running small step #"+str(idx+1)
                                        +" at: "+str([int(i) for i in small_step])+' for '
                                        +str(int(run_cond.wait_sec))+' sec...'
                                        #+'\n and diffuse for '
                                        #+str(int(diffuse_time))+' sec...'
                                        )
                # move one scout step
                rgb_step = []
                run_cond.rgb_avg = []
                run_cond.rates = small_step
                run_cond.run_one_cond()
                # wait to complete one big step
                while len(rgb_step) == 0:
                    # abort if stop button is pressed
                    if not getattr(self.run_thread, "do_run", True):
                        run_cond.stop_timer()  
                        self.logger.save_img(self.fig)
                        self.logger.log('log','Experiment aborted')
                        self.status_string.set("Experiment Aborted")
                        return None
                    rgb_step = run_cond.rgb_avg
                # add new rgb to list
                rgb_steps.append(rgb_step)

            # Gradient Descent
            # suggest next flow rates based on the gradients from scout steps
            delta_rates = np.empty(4) # change of rates between the new rates and current rates
            for i in range(len(rgb_steps)):
                delta_rates += opt.gradient_descent_4steps(target, rgb_steps[i], small_steps_Q[i], cost,
                                                    rates, learning_rate)

            # new rates before scaling
            rates_new = rates + delta_rates
            self.logger.log('log','Gradient Descent Predicted Flowrate (before rescale): '+str(rates_new))
            print('Predicted Flowrate (before rescale): '+str(rates_new))

            # scale new rates
            rates_new_scaled = scale.scale_rates(rates, delta_rates)

            self.logger.log('log', 'Gradient Descent Predicted Flowrate (after rescale): '+str(rates_new_scaled))
            print('Predicted Flowrate (after rescale): '+str(rates_new_scaled))

            # reduce scout step size
            small_step_size = 30.0
            #small_step_size = int((cost+1000)/200) # proportional scout step size
            # step size should be no smaller than 18 to ensure not overpowered by +-3% error on RGB measuring 
            if small_step_size < 18:
                small_step_size = 18
            return rates_new_scaled

                
        # Constraint for BO
        # !!! not used in bo.suggest
        def constraint_function(wrate, crate, mrate, yrate):
            ''' constraint inequality function is about the sum of rates '''
            return wrate+crate+mrate+yrate
        constraint_limit = 600 # total rates <= 600
        constraint = NonlinearConstraint(constraint_function, 0, constraint_limit)

        def run_BO():
            ''' bayesian optimization process '''

            iteration = self.iteration

            pbounds = { "crate":(0,600), "mrate":(0,600),"wrate":(0,600), "yrate":(0,600)}

            # create an optimizer
            bo = BayesianOptimization(f=get_one_data,
                                      constraint = constraint,
                                      pbounds = pbounds,
                                      verbose=2,
                                      random_state=None)
            # set acquisition function
            acquisition_function = UtilityFunction(kind="ucb", kappa=kappa)

            # initialize bo rates
            bo_rates = bo._space.array_to_params(self.init_rates)

            self.logger.log('log','Algorithm: BO')
            self.logger.log('log','Kappa: '+str(kappa))

            # optimize loop
            while iteration < self.no_iter:

                self.logger.log('log', 'Iteration ' + str(iteration))

                # BO
                try:
                    bo_cost = -get_one_data(**bo_rates, iteration=iteration,algo="bo")
                except TypeError:
                    break
                print("BO rates and MSE")
                print(bo_rates, bo_cost)
                bo.register(params=bo_rates, target=bo_cost,constraint_value=600)
                bo_rates = bo.suggest(acquisition_function)
                bo_rates_array = np.array(list(bo_rates.values()))
                bo_rates_array = 600*bo_rates_array/sum(bo_rates_array)
                bo_rates.update({'crate':bo_rates_array[0],
                                 'mrate':bo_rates_array[1],
                                 'wrate':bo_rates_array[2],
                                 'yrate':bo_rates_array[3]})
                bo_prev_cost = bo_cost
                self.logger.log('log', 'Bayesian Optimization Cost: '+str(bo_cost))
                self.logger.log('log', 'Bayesian Optimization Predicted Flowrate: '+str(bo_rates))
                print("BO predicted rates: " + str(bo_rates))
                
                iteration += 1

            if iteration >= self.no_iter:
                # if terminated because reached max no of iteration set
                self.logger.save_img(self.fig)
                self.logger.log('log','Experiment reached maximum number of iterations')
                self.status_string.set("Experiment reached maximum number of iterations")


        def run_GD():
            ''' run gradient descent process '''

            iteration = self.iteration
            prev_cost = self.prev_cost
            # initialize rates
            gd_rates = self.init_rates

            # log
            self.logger.log('log','Learning Rate: '+str(learning_rate))

            # optimization loop
            while iteration < self.no_iter:

                self.logger.log('log', 'Iteration ' + str(iteration))

                gd_cost = get_one_data(*gd_rates, iteration=iteration, algo="gd")
                # terminate if user stop from UI
                if gd_cost == None:
                    break
                # terminate if the cost is small enough
                if gd_cost < 150: # because the Blue Dye has a mse 838
                    auto.stop_all(self.pumps)
                    self.logger.save_img(self.fig)
                    self.status_string.set("Optimized flow rates are found at "+str(gd_rates))
                    self.logger.log('log','Completed! Found the flow rates with the possible minimum cost')
                    break
                gd_rates = get_four_scout(gd_rates, gd_cost)

                # terminate if user stop from UI
                if gd_rates is None:
                    break
                prev_cost = gd_cost
                self.logger.log('log', 'Gradient Descent Cost: '+str(gd_cost))
                self.logger.log('log', 'Gradient Descent Predicted Flowrate: '+str(gd_rates))

                iteration += 1

            if iteration >= self.no_iter:
                # if terminated because reached max no of iteration set
                self.logger.save_img(self.fig)
                self.logger.log('log','Experiment reached maximum number of iterations')
                self.status_string.set("Experiment reached maximum number of iterations")


        def run_both():
            ''' run bayesian optimization and gradient descent in parallel '''

            iteration = self.iteration
            prev_cost = self.prev_cost
            # initialize bo_rates and gd_rates
            gd_rates = self.init_rates

            # initialize bo_prev_cost and gd_prev_cost
            bo_prev_cost = prev_cost
            gd_prev_cost = prev_cost

            pbounds = { "crate":(0,600),"mrate":(0,600), "wrate":(0,600),"yrate":(0,600)}

            # create an optimizer
            bo = BayesianOptimization(f=get_one_data,
                                      constraint = constraint,
                                      pbounds = pbounds,
                                      verbose=2,
                                      random_state=None)
            
            # set acquisition function
            acquisition_function = UtilityFunction(kind="ucb", kappa=kappa)

            # initialize bo rates
            bo_rates = bo._space.array_to_params(self.init_rates)

            # log
            self.logger.log('log','Algorithm: BO & GD')
            self.logger.log('log','BO Kappa: '+str(kappa))
            self.logger.log('log','GD Learning Rate: '+str(learning_rate))

            # optimize loop
            while iteration < self.no_iter:

                self.logger.log('log', 'Iteration ' + str(iteration))

                # BO
                bo_cost = -get_one_data(**bo_rates, prev_cost=bo_prev_cost, iteration=iteration, algo="bo")
                if bo_cost == None: # abort if user stop from UI
                    break
                print("BO rates and MSE")
                print(bo_rates, bo_cost)
                bo.register(params=bo_rates, target=bo_cost, constraint_value=600)
                bo_rates = bo.suggest(acquisition_function)
                bo_rates_array = np.array(list(bo_rates.values()))
                bo_rates_array = 600*bo_rates_array/sum(bo_rates_array)
                bo_rates.update({'crate':bo_rates_array[0],
                                 'mrate':bo_rates_array[1],
                                 'wrate':bo_rates_array[2],
                                 'yrate':bo_rates_array[3]})
                bo_prev_cost = bo_cost
                self.logger.log('log', 'Bayesian Optimization Cost: '+str(bo_cost))
                self.logger.log('log', 'Bayesian Optimization Predicted Flowrate: '+str(bo_rates))
                
                print("BO predicted rates: " + str(bo_rates))
                
                # GD
                gd_cost = get_one_data(*gd_rates, gd_prev_cost, iteration=iteration,algo="gd")
                if gd_cost == None: # abort if user stop from UI
                    break
                gd_rates = get_four_scout(gd_rates, gd_cost)

                # reduce scout step size
                #small_step_size = 10.0
                # small_step_size = int((cost+1000)/200) # proportional scout step size

                if gd_rates is None: # abort if user stop from UI
                    break
                gd_prev_cost = gd_cost
                self.logger.log('log', 'Gradient Descent Cost: '+str(gd_cost))
                self.logger.log('log', 'Gradient Descent Predicted Flowrate: '+str(gd_rates))
                print("GD rates and MSE")
                print(gd_rates, gd_cost)

                iteration += 1

            if iteration >= self.no_iter:
                # if terminated because reached max no of iteration set
                self.logger.save_img(self.fig)
                self.logger.log('log','Experiment reached maximum number of iterations')
                self.status_string.set("Experiment reached maximum number of iterations")


        algo_pick = self.algo.get()
        if algo_pick == 'Gradient Descent':
            run_GD()
        elif algo_pick == 'Bayesian Optim':
            run_BO()
        elif algo_pick == 'Both':
            run_both()


        # Stop all pumps
        auto.stop_all(self.pumps)
        # enable all other buttons 
        self.pick_btn['state']='normal'
        #self.syringe_diam['state']='normal'
        #self.water_syringe_diam['state']='normal'
        self.flush_all_btn['state']='normal'
        self.fill_water_btn['state']='normal'        
        self.integ_time_btn['state']='normal'
        self.take_ref['state']='normal'
        self.take_bg['state']='normal'
        self.start_btn["text"] = "Start"
        self.optimal_gd_btn['state']='normal'
        self.optimal_bo_btn['state']='normal'


    def _start_signal(self):

        # create a thread of running experiment
        self.run_thread = threading.Thread(target=self.run)
        self.run_thread.setDaemon(True)

        # start runnning experiment
        if self.start_btn["text"] == "Start":
            # clear plots
            target = np.array([int(i) for i in eval(self.target_color_UI.get())])
            self.rgb_fig.cla()
            self.rgb_fig.set_xlabel('R')
            self.rgb_fig.set_ylabel('G')
            self.rgb_fig.set_zlabel('B')
            self.rgb_fig.scatter(*target, color=target/255.0, marker='*')
            self.mse_fig.cla()
            self.mse_fig.legend(handles=self.legend_elements, bbox_to_anchor=(1, 1.02),loc="lower right")
            self.mse_fig.xaxis.set_major_locator(MaxNLocator(integer=True, min_n_ticks=1))
            self.mse_fig.yaxis.set_major_locator(MaxNLocator(integer=True, min_n_ticks=1))
            self.mse_fig.set_title('MSE Cost', fontsize=10)
            self.mse_fig.xaxis.set_tick_params(labelsize=8)
            self.mse_fig.yaxis.set_tick_params(labelsize=8)
            self.canvas.draw()
            # toggle start button
            self.start_btn["text"] = "Stop"
            self.pick_btn["state"] = "disabled"
            self.status_string.set("Experiment START!")
            # start run experiment thread
            self.run_thread.start()


        else:
            # ========> Set run experiment condition flag, to break loop <==========
            self.start_btn["text"] = "Start"
            self.pick_btn["state"] = "normal"
            # set thread property to stop run experiment thread
            self.run_thread.do_run = False




    def updateUI(self):
        # update the mse and rgb image
        # notice: tkinter does not allow plotting outside the main thread.
        # in order to scatter while running the run experiment thread,
        # need to pass [iteration, cost, [rgb]] value to a queue
        # this function loops every 0.1sec to update the plot from values in the queue
        try:
            # get value from queue
            [algo,iteration,cost,rgb] = self.qplot.get(False)

            if algo == "gd":
                marker = 'o'
            else:
                marker = '^'

            # plot mse 
            self.mse_fig.scatter(int(iteration), int(cost), label=algo,marker=marker,color=rgb/255.0)
            self.mse_fig.annotate(int(cost), xy=(int(iteration),int(cost)), fontsize=8, xycoords='data')

            # plot rgb 
            self.rgb_fig.scatter(*rgb, label=algo,marker=marker,color=rgb/255.0)

            self.canvas.draw()
        except queue.Empty:
            # Handle empty queue here
            pass

        try:
            [title, message] = self.qmsg.get(False)
            tk.messagebox.showinfo(title=title, message=message)
        except queue.Empty:
            pass


        root.after(100, self.updateUI)

        






if __name__ == "__main__":
    root = App()
    root.after(100, root.updateUI()) 
    root.mainloop()


