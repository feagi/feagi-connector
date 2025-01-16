from .AbstractByteStructure import AbstractByteStructure
import struct
import numpy as np
import numpy.typing as npt # PROPER TYPE SAFETY IS SUCH A GREAT EXPERIENCE IN PYTHON! /s

class SingleRawImage(AbstractByteStructure):
    """
    Encodes a raw image in BGR format with resolution information
    """

    structure_id = 8

    def __init__(self, resolution: tuple[int, int], raw_data_BGR: npt.NDArray[np.uint8]):
        self.resolution: tuple[int, int] = resolution
        self.raw_data_BGR: npt.NDArray[np.uint8] = raw_data_BGR

    @staticmethod
    def create_from_bytes(byte_array: bytes, flip_BR_color_channels: bool = False) -> 'SingleRawImage':
        SingleRawImage.confirm_header(byte_array) # throws an exception if something is wrong
        if len(byte_array) < 4:
            raise Exception("Missing sub-header for 'SingleRawImage'!")

        if (len(byte_array) - 4) % 3 != 0: # global header + sub header
            raise Exception("Invalid number of bytes for 'SingleRawImage'!")

        resolution: tuple[int, int] = struct.unpack('<hh', byte_array[2:4]) # TODO how can I define types for this properly?

        if len(byte_array) - 4 != resolution[0] * resolution[1] * 3:
            raise Exception(f"number of data bytes '{len(byte_array) - 4}' does not match expected given resolution '{resolution[0]}' and '{resolution[1]}' for 'SingleRawImage'!")
        array: npt.NDArray[np.uint8] = np.array(byte_array[4:], dtype=np.uint8)
        if flip_BR_color_channels:
            array[0::3], array[2::3] = array[2::3], array[0::3].copy() # TODO currently optimizing for speed here by keeping this entirely within numpy, but perhaps we can also reduce memory usage a bit if we find a method that doesn't need to copy a third of the array?
        return SingleRawImage(resolution, array)


    @staticmethod
    def create_from_FEAGI_list(resolution: tuple[int, int], feagi_RGB_list: list[int]) -> 'SingleRawImage':
        if len(feagi_RGB_list) != 3 * resolution[0] * resolution[1]:
            raise Exception(f"Invalid data length of '{len(feagi_RGB_list)}' from FEAGI for Raw Image at this given resolution!")
        array: npt.NDArray[np.uint8] = np.array(feagi_RGB_list, dtype=np.uint8)
        array[0::3], array[2::3] = array[2::3], array[0::3].copy() # swap B and R channels to go from RGB to BGR # TODO currently optimizing for speed here by keeping this entirely within numpy, but perhaps we can also reduce memory usage a bit if we find a method that doesn't need to copy a third of the array?
        return SingleRawImage(resolution, array)

    def to_bytes(self) -> bytes:
        return self._create_header() + struct.pack('<hh', self.resolution[0], self.resolution[1]) + bytes(self.raw_data_BGR)
