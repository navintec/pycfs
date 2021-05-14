
pycfs Python cFS Tooling
========================

A Python library and set of tools for interacting with NASA Core Flight System
(cFS).

Modules:
- `pycfs`: Tools for constructing messages and communicating with a cFS system

Scripts:
- `cfssh`: The cFS Shell

## pycfs Module

Load the message ids and structs from a given bundle and set of apps:

```python
import pycfs
MID,CC,MSG = pycfs.load_bundle(path, mission, apps):
```

Afterwards, the objects `MID`, `CC`, and `MSG` will be populated with the
relevant definitions.

## cfssh Shell

cFSSh ("see-fish") is an interactive Python shell for interacting with NASA
Core Flight System (cFS) executables.

For example `cfssh` can be used to construct and send a UDP command to the `TO_LAB` app:
```
cfssh --bundle . --mission sample --target linux-x86-cpu1 to_lab ci_lab
In [1]: cfac = CommandFactory('little')
In [2]: cmdr = UDPCommander('10.42.0.150',1234)
In [3]: cmdr.send(cfac.pack(MID.TO_LAB_CMD_MID, CC.TO_OUTPUT_ENABLE_CC,MSG.TO_LAB_EnableOutput_Payload_t, dest_IP='10.42.0.1'))
```

The fields of a given message can also be inspected like the following:

```python
In [3]: MSG.TO_LAB_EnableOutput_Payload_t.members
Out[3]: [(u'dest_IP', Type(u'char', [16]), None)]
```

The name of a message ID can also be looked up in reverse from its code:
```python
In [4]: MID.inv(0x1880)
Out[4]: u'TO_LAB_CMD_MID'
```


## Installing

```sh
python -m pip install .
```
