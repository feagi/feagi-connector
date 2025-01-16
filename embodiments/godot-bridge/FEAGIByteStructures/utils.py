from typing import Type, TypeVar
from .AbstractByteStructure import AbstractByteStructure
from .ActivatedNeuronLocation import ActivatedNeuronLocation
from .JSONByteStructure import JSONByteStructure
from .MultiByteStructHolder import MultiByteStructHolder
from .SingleRawImage import SingleRawImage


def attempt_to_create_byte_structure_from_bytes(byte_array: bytes) -> AbstractByteStructure:
    """
    Given a sequence of bytes, attempts to create to correct Byte Structure from it
    """
    if len(byte_array) < 3:
        raise Exception("Byte structure is missing initial header!")
    structure_type: int = byte_array[0]
    match structure_type:
        case 1:
            return JSONByteStructure.create_from_bytes(byte_array)
        case 7:
            return ActivatedNeuronLocation.create_from_bytes(byte_array)
        case 8:
            return SingleRawImage.create_from_bytes(byte_array)
        case 9:
            return MultiByteStructHolder.create_from_bytes(byte_array)
    raise Exception(f"Unable to generate unsupported byte structure of type {structure_type}!")

