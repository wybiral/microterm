from base64 import b64encode, b64decode
import cmd
from functools import wraps
import serial
from serial.tools.list_ports import comports
from serial.tools.miniterm import Miniterm
import sys
import keyboard

VERSION = '0.0.1'

# used to restore stdout/stderr after miniterm
STDOUT = sys.stdout
STDERR = sys.stderr

def connected(method):
    # decorator for commands that require a connected device
    @wraps(method)
    def wrapped(self, *args, **kwargs):
        if self.device is None:
            print('ERROR: must be connected to a device')
            return
        try:
            out = method(self, *args, **kwargs)
        except serial.SerialException:
            print('ERROR: device disconnected')
            self.device.disconnect()
            self.device = None
            out = None
        return out
    return wrapped


class MinitermPatched(Miniterm):

    def reader(self):
        # patch the reader thread method to prevent exception
        try:
            while self.alive and self._reader_alive:
                # read all that is there or wait for one byte
                data = self.serial.read(self.serial.in_waiting or 1)
                if data:
                    if self.raw:
                        self.console.write_bytes(data)
                    else:
                        text = self.rx_decoder.decode(data)
                        for transformation in self.rx_transformations:
                            text = transformation.rx(text)
                        self.console.write(text)
        except serial.SerialException:
            self.alive = False
            self.console.cancel()


class MicroDevice:

    def __init__(self, device):
        self.serial = serial.Serial(device, 115200, timeout=1.0)

    def connect(self):
        # send ctrl-C twice to stop any running code
        self.serial.write(b'\r\x03\x03')
        self.enter_raw()
        self.serial.flush()
        self.execute(b'import os\n')
        self.execute(b'from ubinascii import a2b_base64, b2a_base64\n')

    def disconnect(self):
        # disconnect from device
        self.serial.close()

    def read_until(self, x):
        # read from serial until byte string x found
        b = b''
        while True:
            b += self.serial.read(1)
            if b.endswith(x):
                return b

    def enter_raw(self):
        # enter raw REPL mode
        self.serial.write(b'\r\x01')
        self.serial.flush()
        self.read_until(b'raw REPL; CTRL-B to exit\r\n')

    def exit_raw(self):
        # exit raw REPL mode
        self.serial.write(b'\r\x02')
        self.serial.flush()

    def execute_raw(self, code):
        # execute code in raw REPL mode
        self.read_until(b'>')
        self.serial.write(code)
        self.serial.write(b'\x04')
        self.serial.flush()
        resp = self.serial.read(2)
        assert resp == b'OK'

    def read_response(self):
        # read response from command in raw REPL mode
        data = self.read_until(b'\x04')
        err = self.read_until(b'\x04')
        return data[:-1], err[:-1]

    def execute(self, code):
        # enter raw mode, execute code, exit raw mode, return results and error
        #self.enter_raw()
        self.execute_raw(code)
        data, err = self.read_response()
        if err:
            print(err)
        #self.exit_raw()
        return data, err

    def start_repl(self):
        m = MinitermPatched(self.serial)
        m.exit_character = chr(0x03)
        m.set_rx_encoding('utf-8')
        m.set_tx_encoding('utf-8')
        m.start()
        try:
            m.join(True)
        finally:
            # fix bug(?) in miniterm
            sys.stdout = STDOUT
            sys.stderr = STDERR


class Microterm(cmd.Cmd):

    version = VERSION
    intro = f'''Microterm {version} MicroPython terminal
Type "help" for a list of commands.'''
    prompt = '(Microterm)> '

    def __init__(self, *args, **kwargs):
        super(Microterm, self).__init__(*args, **kwargs)
        self.device = None

    def default(self, arg):
        self.stdout.write(f'ERROR: unknown command: {arg}\n')

    def emptyline(self):
        # don't repeat last command
        pass

    def parseline(self, line):
        # custom parseline for executing python scripts
        line = line.strip()
        parts = line.split(' ')
        if not line:
            return None, None, line
        elif line[0] == '?':
            line = 'help ' + line[1:]
        if len(parts) == 1 and line.endswith('.py'):
            line = 'python ' + line
        i, n = 0, len(line)
        while i < n and line[i] in self.identchars:
            i = i+1
        cmd = line[:i]
        arg = line[i:].strip()
        return cmd, arg, line

    def do_help(self, arg):
        ''' List available commands or details for a specific command.
            Usage: help [COMMAND]
        '''
        if arg:
            try:
                doc = getattr(self, 'do_' + arg).__doc__
            except AttributeError:
                self.default(arg)
            else:
                doc = doc.strip()
                lines = [line.strip() for line in doc.split('\n')]
                self.stdout.write('\n'.join(lines) + '\n')
            return
        names = set(x for x in dir(self.__class__) if x.startswith('do_'))
        topics = []
        for name in sorted(names):
            if getattr(self, name).__doc__:
                topics.append(name[3:])
        self.stdout.write('Commands ("help <command>" for details):\n')
        self.columnize(topics, 79)

    @connected
    def do_cat(self, arg):
        ''' Print contents of file from MicroPython device.
            Usage: cat FILENAME
        '''
        name = repr(arg)
        code = f'''with open({name}) as f:
    while True:
        b = f.read(256)
        if not b:
            break
        print(b, end='')\n'''
        out, err = self.device.execute(code.encode())
        print(out.decode())

    @connected
    def do_cd(self, arg):
        ''' Change current MicroPython directory.
            Usage: cd PATH
        '''
        path = repr(arg)
        self.device.execute(f'os.chdir({path})\n'.encode())

    def do_connect(self, arg):
        ''' Connect to MicroPython device.
            Usage: connect DEVICE
        '''
        try:
            self.device = MicroDevice(arg)
            self.device.connect()
        except:
            self.device = None
            print('ERROR: unable to connect to device')

    def do_devices(self, arg):
        ''' List serial devices.
            Usage: devices
        '''
        for device in comports():
            print(device)

    @connected
    def do_disconnect(self, arg):
        ''' Disconnect from current MicroPython device.
            Usage: disconnect
        '''
        self.device.disconnect()
        self.device = None

    def do_exit(self, arg):
        ''' Exit Microterm.
            Usage: exit
        '''
        return True

    @connected
    def do_get(self, arg):
        ''' Download file from MicroPython device.
            Usage: get SRC_FILE [DST_FILE]
        '''
        args = arg.split()
        if len(args) == 1:
            src = repr(args[0])
            dst = args[0]
        else:
            src = repr(args[0])
            dst = args[1]
        self.device.execute(f'''f=open({src},'rb')\n'''.encode())
        f = open(dst, 'wb')
        while True:
            self.device.execute(f'''d=str(b2a_base64(f.read(256)),'ascii')\n'''.encode())
            data, err = self.device.execute(f'''print(d.strip(),end='')'''.encode())
            data = b64decode(data.decode(), validate=False)
            if not data:
                break
            f.write(data)
        f.close()
        self.device.execute(b'f.close()\ndel f\n')

    @connected
    def do_ls(self, arg):
        ''' List contents of current directory from MicroPython device.
            Usage: ls
        '''
        cyan = '\033[96m'
        endc = '\033[0m'
        data, err = self.device.execute(b'''for f in os.ilistdir('.'):
    print(f[0], end='/ ' if f[1] & 0x4000 else ' ')
        ''')
        out = []
        for x in data.decode().strip().split():
            out.append(cyan + x + endc if x.endswith('/') else x)
        self.columnize(out)

    @connected
    def do_mkdir(self, arg):
        ''' Make new directory on MicroPython device.
            Usage: mkdir DIR_NAME
        '''
        path = repr(arg)
        self.device.execute(f'os.mkdir({path})'.encode())

    @connected
    def do_mv(self, arg):
        ''' Move or rename a file or directory on MicroPython device.
            Usage: mv SRC_PATH DST_PATH
        '''
        args = arg.split()
        src = repr(args[0])
        dst = repr(args[1])
        self.device.execute(f'os.rename({src}, {dst})'.encode())

    @connected
    def do_put(self, arg):
        ''' Upload file to MicroPython device.
            Usage: put SRC_FILE [DST_FILE]
        '''
        args = arg.split()
        if len(args) == 1:
            src = args[0]
            dst = repr(args[0])
        else:
            src = args[0]
            dst = repr(args[1])
        self.device.execute(f'''f=open({dst},'wb')
w=lambda x:f.write(a2b_base64(x))\n'''.encode())
        f = open(src, 'rb')
        while True:
            x = f.read(256)
            if not x:
                break
            data = b64encode(x)
            self.device.execute(f'''w({data})\n'''.encode())
        f.close()
        self.device.execute(b'f.close()\ndel w\ndel f\n')

    @connected
    def do_pwd(self, arg):
        ''' Print working directory of MicroPython device.
            Usage: pwd
        '''
        data, err = self.device.execute(b'''print(os.getcwd(),end='')\n''')
        print(data.decode())

    @connected
    def do_python(self, arg):
        ''' Enter MicroPython REPL mode or execute a script.
            Usage: python
            Usage: python script.py
        '''
        print('Press CTRL+C to return to Microterm')
        self.device.exit_raw()
        if arg:
            script = repr(arg)
            code = f'exec(open({script}).read())#microterm19870627\r'.encode()
            self.device.serial.write(code)
            self.device.serial.flush()
            # don't show the exec line in the console
            self.device.read_until(b'#microterm19870627\r\n')
        else:
            self.device.read_until(b'\r\n')
        self.device.start_repl()
        self.device.connect()
        print('')

    @connected
    def do_reboot(self, arg):
        ''' Reboot MicroPython device (soft reboot).
            Usage: reboot
        '''
        print('Press CTRL+C to return to Microterm')
        self.device.exit_raw()
        self.device.serial.write(b'\x04')
        self.device.serial.flush()
        self.device.read_until(b'soft reboot\r\n')
        self.device.start_repl()
        self.device.connect()
        print('')

    @connected
    def do_rm(self, arg):
        ''' Remove a single file from MicroPython device.
            Usage: rm FILENAME
        '''
        path = repr(arg)
        self.device.execute(f'os.remove({path})'.encode())

    @connected
    def do_rmdir(self, arg):
        ''' Remove directory from MicroPython device.
            Usage: rmdir DIRNAME
        '''
        path = repr(arg)
        self.device.execute(f'os.rmdir({path})'.encode())
