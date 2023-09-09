# Microterm
CLI tool for interacting with MicroPython devices

## Installation

Install microterm from the command line using pip.
```
pip install microterm
```

## Getting Started

Launch the microterm terminal from the Python module.
```
python -m microterm
```

## Usage Examples

Display command list.
```
Microterm> help
Commands ("help <command>" for details):
cat  connect  disconnect  get   ls     mv   pwd     reboot  rmdir
cd   devices  exit        help  mkdir  put  python  rm
```

Get help for a specific command.
```
Microterm> help connect
Connect to MicroPython device.
Usage: connect DEVICE
```

List serial devices.
```
Microterm> devices
COM7 - USB Serial Device (COM7)
```

Connect to device.
```
Microterm> connect com7
```

List files on device.
```
Microterm> ls
main.py  settings.txt
```

Copy file from host machine (such as a laptop running Microterm) to the connected MicroPython device.
```
Microterm> put main.py
```

Copy file from connected MicroPython device to the host machine.
```
Microterm> get main.py
```

Read contents of a file.
```
Microterm> cat main.py
print('Hello world!')
```

Execute script on MicroPython device.
```
Microterm> python main.py
Press CTRL+C to return to Microterm
Hello world!
```

Enter MicroPython REPL.
```
Microterm> python
Press CTRL+C to return to Microterm
MicroPython v1.20.0 on 2023-04-26; SparkFun Pro Micro RP2040 with RP2040
Type "help()" for more information.
>>>
```
