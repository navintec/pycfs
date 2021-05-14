
from __future__ import print_function

import struct

def get_padding(index, elem_size):
    return 'x' * ((elem_size - (index % elem_size)) % elem_size)

class CCSDS:
    """
    CCSDS standard serialization
    """
    class PRI:
        """
        Primary header

        ref: CCSDS 133.0-B-2 Section 4.1.3
        """

        # Binary packing format
        FORMAT = '>HHH'
        SIZE = 6

        CHUNK_CONFIG = 0
        CHUNK_SEQUENCE = 1
        CHUNK_DATA_LENGTH = 2
        N_CHUNKS = 3

        # Chunk 0: Version and Packet Identification
        # 16 bits
        MASK_VERSION    = 0xE000 # 1110 0000 0000 0000
        BIT_PKT_TYPE    = 0x1000 # 0001 0000 0000 0000
        BIT_SEC_HEADER  = 0x0800 # 0000 1000 0000 0000
        MASK_APID       = 0x07FF # 0000 0111 1111 1111

        # Version values
        VERSION_1    = 0x0000

        # Packet type values
        PKT_TYPE_TLM = 0x0000
        PKT_TYPE_CMD = 0x1000

        # Secondary header
        HAS_SEC_HEADER = 0x0800

        # Chunk 1: Sequence Control
        # 16 bits
        MASK_SEQUENCE_FLAGS   = 0xC000 # 1100 0000 0000 0000
        MASK_SEQUENCE_NUMBER  = 0x3FFF # 0011 1111 1111 1111

        SEQUENCE_CONTINUATION = 0x0000 # 0000 0000 0000 0000
        SEQUENCE_FIRST        = 0x4000 # 0100 0000 0000 0000
        SEQUENCE_LAST         = 0x8000 # 1000 0000 0000 0000
        SEQUENCE_UNSEGMENTED  = 0xC000 # 1100 0000 0000 0000

        # Chunk 2: Data length
        # 16 bits
        # Data field size in bytes -1
        # This includes the secondary header
        MASK_PAYLOAD_SIZE = 0xFFFF # 1111 1111 1111 1111

    class EXT:
        pass

class cFS:
    """
    cFS-Specific serialization
    """
    class CMD:
        class SEC:
            """
            cFS Command Secondary header
            """
            FORMAT = '>BB'
            SIZE = 2

            CHUNK_COMMAND_CODE = 0
            CHUNK_CHECKSUM = 1
            N_CHUNKS = 2

            # Chunk 1: command code
            MASK_CMD_CODE = 0x7F

            # Chunk 2: checksum
            MASK_CHECKSUM = 0xFF

    class TLM:
        class SEC:
            """
            cFS Telemetry Secondary header
            """

            FORMAT = '>IH'
            SIZE = 6
            PADDING = 4

            CHUNK_SEC = 0
            CHUNK_SUBSEC = 1

    def secsub_to_seconds(sec, subsec):
        return sec + (subsec / pow(2,16))

    @staticmethod
    def compute_checksum(payload):
        """Compute the checksum for a payload"""
        cksum = 0xFF
        for b in struct.unpack('B'*len(payload), payload):
            cksum ^= b
        return cksum


class CStruct(object):
    """
    an object representing a partially populated c structure
    """
    def __init__(self, spec, **kwargs):

        # Make sure all keyword arguments are in the specification
        bad_keys = [k for k in kwargs.keys()
                if k not in [n for n,_,_ in spec.members]
                ]

        if len(bad_keys) > 0:
            raise ValueError("Inappropriate fields for struct {}: {}".format(spec, bad_keys))

        self.spec = spec
        self.members = kwargs


class Formatter(object):
    """
    object for constructing format strings for packing and unpacking
    CStructs
    """
    def __init__(self, type_specs=None, payload_endianness='little'):
        """
        construct a formatter which supports the given type specs
        """
        self.payload_endianness = '<' if payload_endianness == 'little' else '>'
        self.specs = type_specs
        self.primitives = {
                'bool':     ('?', 1),
                '_Bool':    ('?', 1),
                'char':     ('c', 1),
                'int8':     ('b', 1),
                'int8_t':   ('b', 1),
                'uint8':    ('B', 1),
                'uint8_t':  ('B', 1),
                'int16':    ('h', 2),
                'int16_t':  ('h', 2),
                'uint16':   ('H', 2),
                'uint16_t': ('H', 2),
                'int32':    ('i', 4),
                'int32_t':  ('i', 4),
                'uint32':   ('I', 4),
                'uint32_t': ('I', 4),
                'int64':    ('q', 8),
                'int64_t':  ('q', 8),
                'uint64':   ('Q', 8),
                'uint64_t': ('Q', 8),
                'float':    ('f', 4),
                'double':   ('d', 8)
                }
        self.alignment = {v[0]:v[1] for k,v in self.primitives.items()}

        # resolve aliased primitive types
        specs_to_process = list(self.specs._fw.items())

        last_invalid_spec = None
        while len(specs_to_process) > 0:
            spec_name, spec_value = specs_to_process.pop()

            if last_invalid_spec == spec_name:
                break

            if type(spec_value) in [str,unicode]:
                if spec_value in self.primitives:
                    #print('spec {} is {}'.format(spec_name, spec_value))
                    self.primitives[spec_name] = self.primitives[spec_value]
                    last_invalid_spec = None
                else:
                    specs_to_process.insert(0,(spec_name, spec_value))
                    if last_invalid_spec == None:
                        last_invalid_spec = spec_name

    def make_cstruct(self, fields, spec):
        """
        recursively build a cstruct from fielsd and a given specification
        """

        cstruct = CStruct(spec)

        for m_name, m_type, _ in spec.members:

            n_values = (
                    m_type.declarators[0][0]
                    if (len(m_type.declarators) > 0)
                    else 1)

            if m_type.type_spec in self.primitives:
                if n_values == 1:
                    val = fields[0]
                    fields = fields[1:]
                else:
                    val = fields[0:n_values]
                    fields = fields[n_values:]
            else:
                if n_values == 1:
                    val,fields = self.make_cstruct(fields,
                            self.specs._fw[m_type.type_spec])
                else:
                    val = []
                    for i in range(n_values):
                        sub_cstruct, fields = self.make_cstruct(fields,
                                self.specs._fw[m_type.type_spec])
                        val.append(sub_cstruct)

            setattr(cstruct, m_name, val)

        return cstruct,fields

    def get_spec(self, type_name):
        """get a struct specification by type name"""
        if self.specs is None:
            raise Exception('Unknown type specifier: {}'.format(type_name))

        return getattr(self.specs, type_name)

    def get_padded_format(self, format_str):
        size = struct.calcsize(format_str)

        # Number of pad bytes to align to the boundary required for this
        # element size

        padded_format = ''
        index = 0
        for v in format_str:
            padded_format += get_padding(index, struct.calcsize(v)) + v

        #print('padded: "{}" --> "{}"'.format(format_str, padded_format))

        return padded_format

    def get_format(self, spec, padding=True):
        """get the struct.pack format specifier from a c struct specification
        """

        format_str = ''
        format_size = 0

        for m_name, m_type, _ in spec.members:
            # The packing format and size for this member
            m_padding = ''
            m_format_str = ''
            m_index = struct.calcsize(format_str)

            # Get the format string
            if m_type.type_spec in self.primitives:
                m_format_str = self.primitives[m_type.type_spec][0]
            else:
                m_format_str = self.get_format(self.get_spec(m_type.type_spec),
                        padding=padding)

            # Add padding
            if m_index > 0 and padding:

                # Get maximum alignment for all fields in this field or struct
                max_elem_alignment = max([
                    self.alignment[f]
                    for f
                    in m_format_str
                    if f in self.alignment])

                # Construct the padding format based on the alignment
                m_padding = get_padding(
                        m_index,
                        max_elem_alignment)

            # Get the multiplicity of the member
            if len(m_type.declarators) > 0:
                n = m_type.declarators[0][0]
                if n is None:
                    raise Exception("Can't determine size of field: {}".format(spec))
            else:
                n = 1

            # Accumulate format string
            format_str += m_padding + (m_format_str * n)

        max_elem_alignment = max([
            self.alignment[f]
            for f
            in format_str
            if f in self.alignment])

        format_str += get_padding(struct.calcsize(format_str), max_elem_alignment)

        return format_str

class CommandFactory(object):
    """
    command factory is used to construct command message bytestrings from
    CStruct objects
    """
    def __init__(self, type_specs, spacecraft_endianness='little'):
        """
        spacecraft_endianness: little/big
        """
        self.formatter = Formatter(type_specs, spacecraft_endianness)

    def pack(self, mid, cc, cstruct=None):
        """Create a command message"""

        if cstruct is not None:
            payload = self.pack_struct(cstruct)
        else:
            payload = ''

        header = self.pack_header(mid, cc, payload)

        return header + payload

    def pack_header(self, mid, cc, payload):
        """
        Create the header for a command given a payload

        TODO: Support sequences
        """

        # Construct primary header

        sequence = 0x0000

        ccsds_pri = struct.pack(
                CCSDS.PRI.FORMAT,
                # Version and identification
                (CCSDS.PRI.VERSION_1 |
                    CCSDS.PRI.PKT_TYPE_CMD |
                    CCSDS.PRI.HAS_SEC_HEADER |
                    (CCSDS.PRI.MASK_APID & mid)),
                # Sequence information
                sequence,
                # Total data bytes -1 (ref: CCSDS 133.0-B-2 Section 4.1.3.5.3)
                cFS.CMD.SEC.SIZE + len(payload) - 1)

        # Construct secondary header
        ccsds_sec = struct.pack(
                cFS.CMD.SEC.FORMAT,
                cFS.CMD.SEC.MASK_CMD_CODE & cc,
                cFS.compute_checksum(payload))

        return ccsds_pri + ccsds_sec

    def get_vector(self, type_spec, n_values, member_val):
        """get a vector of values with zeros in all unspecified values"""

        # Specil null character for char arrays
        null_vals = {'char': '\x00'}

        # Construct a fixed-size array of zero values
        val_padded = [null_vals.get(type_spec,0)] * n_values

        # If the argument is provided, fill as much of the array as
        # provided
        if member_val is not None:
            arg_len = len(member_val)
            if arg_len > n_values:
                raise ValueError("Argument {} too long. Max length: {}".format(m_name, n))

            val_padded[0:arg_len] = member_val

            # Force utf-8 encoding
            if type_spec == 'char':
                val_padded = [bytes(v.encode('utf-8')) for v in val_padded]

        return val_padded

    def get_fields(self, cstruct):
        """get a flat list of values for a given structure"""

        values = []

        # Iterate over the members of this struct specification
        # This populates the values aray
        for m_name, m_type, _ in cstruct.spec.members:

            # Get the member value if populated
            member_val = cstruct.members.get(m_name, None)

            # Get the number of values for this field
            n_values = (
                    m_type.declarators[0][0]
                    if (len(m_type.declarators) > 0)
                    else 1)

            # Handle primitives or other CStructs
            if m_type.type_spec in self.formatter.primitives:
                # Determine if this member is scalar or vector
                if n_values == 1:
                    # Zero or the provided value
                    values.append(member_val if (member_val is not None) else 0)
                else:
                    # Extend with a vector of values
                    values.extend(
                            self.get_vector(
                                m_type.type_spec,
                                n_values,
                                member_val))
            else:

                spec = self.formatter.specs._fw[m_type.type_spec]

                if n_values == 1:
                    if member_val is None:
                        member_val = CStruct(spec)

                    assert(type(member_val) == CStruct)
                    values.extend(self.get_fields(member_val))
                else:
                    if member_val is None:
                        member_val = []

                    assert(len(member_val) <= n_values)

                    for member_val_elem in member_val:
                        assert(type(member_val_elem) == CStruct)
                        values.extend(self.get_fields(member_val_elem))

                    # Pad missing elements with zeros
                    #print('Padding array member {} with {} structs'.format(m_name, n_values - len(member_val)))
                    for i in range(n_values - len(member_val)):
                        values.extend(self.get_fields(CStruct(spec)))

        return values

    def pack_struct(self, structure):
        """Pack a binary struct from a specification and a set of field values

        given a structure (pair of spec and member values), return a packed
        struct which includes the struct format and a list of values
        corresponding to each format value

        for composite types, this recursively packs and flattens the structure

        """

        # get the format for packing
        spec_format = self.formatter.get_format(structure.spec)
        # get the fields to pack
        field_values = self.get_fields(structure)

        return struct.pack(self.formatter.payload_endianness + spec_format, *field_values)


class TelemetryFactory(object):
    """
    telemetry factory is used to construct CStruct objects from telemetry
    message bytestrings
    """
    def __init__(self, type_specs, spacecraft_endianness='little'):
        self.formatter = Formatter(type_specs, spacecraft_endianness)

    def unpack_header(self, data):
        # Unpack the header
        pri_id, pri_seq, pri_data_len = struct.unpack(
                CCSDS.PRI.FORMAT,
                data[0:struct.calcsize(CCSDS.PRI.FORMAT)])

        # Check if it's a telemetry packet
        if (pri_id & CCSDS.PRI.BIT_PKT_TYPE) != CCSDS.PRI.PKT_TYPE_TLM:
            raise ValueError("Not a TLM packet.")

        # Check if it has a valid secondary header
        if not pri_id & CCSDS.PRI.HAS_SEC_HEADER:
            raise ValueError("No secondary header.")

        # Unpack the secondary header
        stamp = struct.unpack_from(
                cFS.TLM.SEC.FORMAT,
                data,
                CCSDS.PRI.SIZE)

        return pri_id, pri_seq, pri_data_len, stamp


    def unpack_payload(self, data, spec):

        # Unpack the packet based on the spec
        spec_format = self.formatter.get_format(spec, padding=True)

        try:
            offset = (CCSDS.PRI.SIZE + cFS.TLM.SEC.SIZE + cFS.TLM.SEC.PADDING)
            fields = struct.unpack_from(
                    spec_format,
                    data,
                    offset = offset)
        except Exception as ex:
            spec_size = struct.calcsize(spec_format)
            print('Error unpacking {} with format "{}" and size {} (calcsize: {}) from data "{}" of size {} with offset {}'.format(spec,
                spec_format, spec_size, struct.calcsize(spec_format),
                ''.join(' x%02x'%ord(i) for i in data),
                len(data), offset))
            print(ex)
            return


        # Populate a CStruct with the appropriate fields
        cstruct,fields = self.formatter.make_cstruct(fields, spec)

        assert(len(fields) == 0)

        return cstruct
