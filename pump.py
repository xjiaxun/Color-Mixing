import serial
import re
import warnings


class Chain(serial.Serial):
    """ Create a serial connection with the daisy-chained pumps 
    
    Chain is a subclass of serial.Serial. Chain creates a serial.Serial
    instance with the required parameters, flushes input and output
    buffers (found during testing that this fixes a lot of problems) and
    logs creation of the Chain.
    """

    def __init__(self, port):
        serial.Serial.__init__(self, port=port, baudrate=115200, timeout=1, writeTimeout=1)
        self.reset_output_buffer()
        self.reset_input_buffer()

class Pump:
    """driver lirbary for controlling Harvard Apparatus phd utltra syringe pumps"""

    # A pump object should following parameters: pump serial port (chain object),
    # (optional) address of the pump.
    def __init__(self, chain, address=0):

        self.serialcon = chain
        self.address = '{0:02.0f}'.format(address)
        self.diameter = None
        self.flowrate = None
        self.targetvolume = None

        
        # Query the version number of the firmware to ensure the connection was 
        # established. 
        try:
            self.write('VER')
            resp = self.read()
            print(resp)
            #model = re.search('ELITE', resp)
            addr = re.findall(r'(\d+)(:|>|<)', resp)[0][0]

            if addr != self.address:
                raise PumpError('No response from pump at \
                address %s' % self.address)
        except PumpError:
            self.serialcon.close()
            raise

        # try writing a cmd to check if connection is well established
        # turn off echoing the written commands 
        try:
            self.write('echo off')
        except serial.SerialTimeoutException:
            print('Write command failed')
        else:
            self.read()


        
    # format write commands
    def write(self, command):
        self.serialcon.write((self.address + command + '\r').encode())

    # read feedback from pump and convert to string
    def read(self):
        resp = self.serialcon.read(1024).decode("ISO-8859-1")

        if len(resp) == 0:
            warnings.warn("no response")
        else:
            return resp

    def query(self):
        ''' get pump attention, response: [##:] '''
        self.write('')
        return self.read()


    def set_diameter(self, diameter):
        # &&& Add check diameter range
        self.write(command=('diameter %.2f' % diameter))
        # &&& Add check if diameter is set
        return self.read()

    def set_infuse_rate(self, flowrate, unit='ul/min'):
        ''' query response: [##:]'''

        # &&& Add check flowrate range within infuse_rate_min and infuse_rate_max
        command=('irate %.2f %s' % (flowrate,unit))
        #print('write: '+command)
        self.write(command)
        raw_resp = self.read()
        return raw_resp

    
    def set_withdraw_rate(self, flowrate, unit='ul/min'):
        ''' query response: [##:]'''
        # &&& Add check flowrate range
        self.write(command=('wrate %s %s' % (flowrate,unit)))
        # &&& Add check if flowrate is set 
        return self.read()

    def set_target_vol(self, volume, unit='ul'):
        # set the target volume
        # &&& Add check with syringe volume
        self.write(('tvolume %s %s' % (volume,unit)))
        # &&& Add check if target volume is set
        return self.read()

    def set_syringe(self):
        syr_model = input('\nChoose model from: (Please refer to the manual for a complete list of syringe models)'\
            +self.read_syr_models())
        self.write('syrm %s ?' % syr_model)
        resp = self.read()
        while re.search('Argument error', resp):
            print('\nInvalid model')
            syr_model = input('\nChoose model from: (Please refer to the manual for a complete list of syringe models)'\
            +self.read_syr_models())
            self.write('syrm %s ?' % syr_model)
            resp = self.read()
        syr_vol = input('Choose syringe size from: '+resp)

        self.write('syrm %s %s' % (syr_model, syr_vol))
        return self.read_cur_syringe()


    def read_cur_syringe(self):
        ''' display the current syringe setting
            query: [##:] {manufacturer}, {diameter} mm
            example: 00:Hamilton, 10 ml, 14.567 mm
        '''
        self.write('syrm')
        return self.read()

    def read_syr_models(self):
        # display a list of manufacurers with their associated 3-letter code
        self.write('syrm ?')
        return self.read()

    def read_rate_range(self):
        # display the flowrate range limits
        self.write(command='irate lim')
        infuse_rate_range = self.read()
        self.write(command='wrate lim')
        withdraw_rate_range = self.read()
        # &&& Add extracting numbers from self.read, assign to\
        # infuse_rate_min and infuse_rate_max
        return [infuse_rate_range, withdraw_rate_range]

    def read_cur_rate(self):
        '''display the current rate that the pump is running at.
            A valid response is returned only in dynamic situations (while the pump is running).
            query: ##:]Infusing at # xl/xxx<cr>  OR  [##:]Withdrawing at # xl/xxx<cr>'
            example: 00:Infusing at 0 ml/min
        '''
        self.write('crate')
        resp = self.read()
        cur_rate = re.findall('[:|>|<]|\w+\/\w+|\w+', resp)[4]
        return cur_rate
        

    def read_cur_dia(self):
        ''' display the current diameter in mm
            query: [##:]#.#### mm
            example: 00:14.5670 mm
        '''
        self.write('diameter')
        resp = self.read()
        dia = re.findall(r'[:|>|<]|\d+\.\d*|\w+', resp)[2]
        return dia

    def read_syringe_vol(self):
        # display the syringe volume
        self.write('svolume')
        return self.read()

    def read_infused_vol(self):
        # display the infused volume
        self.write('ivolume')
        return self.read()
    
    def read_withdrawn_vol(self):
        # display the withdrawn volume
        self.write('wvolume')
        return self.read()

    def read_target_vol(self):
        # display the target volume
        self.write('tvolume')
        return self.read()
    
    def read_infused_time(self):
        # display the infused time
        self.write('itime')
        return self.read()

    def read_withdrawn_time(self):
        # display the withdrawn time
        self.write('wtime')
        return self.read()

    def read_target_time(self):
        # display the target time
        self.write('ttime')
        return self.read()

    def read_raw_status(self):
        # display the raw status 
        self.write('status')
        #&&& Add parse raw status
        return self.read()


    def infuse(self):
        # run the pump in the infuse direction
        self.write(command='irun')

    def withdraw(self):
        # run the pump in the withdraw direction
        self.write(command='wrun')

    def stop(self):
        # stop the pump
        self.write(command='stop')


    def clear_vol(self):
        # clear both the infused and withdrawn volumes
        self.write('cvolume')

    def clear_infused_vol(self):
        # clear the infused volume
        self.write('civolume')

    def clear_withdrawn_vol(self):
        # clear the withdrawn volume
        self.write('cwvolume')

    def clear_target_vol(self):
        # clear the target volume
        self.write('ctvolume')

    def clear_time(self):
        # clear both the infused and withdrawn time
        self.write('ctime')

    def clear_infused_time(self):
        # clear the infused time
        self.write('citime')

    def clear_withdrawn_time(self):
        self.write('cwtime')

    def clear_target_time(self):
        self.write('cttime')

    def clear_all(self):
        self.clear_infused_time()
        self.clear_infused_vol()
        self.clear_target_time()
        self.clear_target_vol()
        self.clear_time()
        self.clear_vol()
        self.clear_withdrawn_time()
        self.clear_withdrawn_vol()



class PumpError(Exception):
    pass