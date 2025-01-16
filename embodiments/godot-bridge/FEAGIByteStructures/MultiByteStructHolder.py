from .AbstractByteStructure import AbstractByteStructure
from .utils import attempt_to_create_byte_structure_from_bytes
import struct

class MultiByteStructHolder(AbstractByteStructure):
    """
    Essentially a list of other ByteStuctures
    """

    structure_id = 9


    def __init__(self, byte_structures: list[AbstractByteStructure]):
        self.byte_structures: list[AbstractByteStructure] = byte_structures


    @staticmethod
    def create_from_bytes(byte_array: bytes) -> 'MultiByteStructHolder':
        MultiByteStructHolder.confirm_header(byte_array)  # throws an exception if something is wrong
        if len(byte_array) < 3:
            raise Exception("Missing data fro initial sub-header for 'MultiByteStructHolder'!")
        number_sub_byte_structs: int = byte_array[3]
        if len(byte_array) < 3 + (2 * number_sub_byte_structs):
            raise Exception("Sub-header size for 'MultiByteStructHolder' is smaller than expected!")
        parsed_byte_structures: list[AbstractByteStructure] = []
        header_offset: int = 3
        for byte_structure_index in range(number_sub_byte_structs):
            sub_struct_start_index: int = byte_array[header_offset]
            sub_struct_length: int = byte_array[header_offset + 1]
            sub_struct_bytes: bytes = byte_array[sub_struct_start_index:sub_struct_start_index + sub_struct_length]
            try:
                parsed_byte_structures.append(attempt_to_create_byte_structure_from_bytes(sub_struct_bytes))
            except Exception as e:
                print(f"Unable to parse one of the byte structures as a AbstractByteStructure member: {e}")
        return MultiByteStructHolder(parsed_byte_structures)


    @staticmethod
    def create_from_list_of_bytestructs(byte_structures: list[AbstractByteStructure]) -> 'MultiByteStructHolder':
        return MultiByteStructHolder(byte_structures)

    def to_bytes(self) -> bytes:

        output: bytearray = bytearray(self._create_header() + bytes([len(self.byte_structures)]) + bytes([0] * 2 * len(self.byte_structures))) ## allocate space for header

        # process subheader indexes for contained byte structure locations, and append data
        sub_header_index_offset: int = 3  # skipping global header, and the initial sub_struct count
        for byte_structure in self.byte_structures:
            data_start_offset: int = len(output)  # where we start reading data for this byte tructure
            data: bytes = byte_structure.to_bytes()
            output[sub_header_index_offset] = data_start_offset
            output[sub_header_index_offset + 1] = len(data)
            output += bytearray(output)
            sub_header_index_offset += 2
        return bytes(output)
