from .AbstractByteStructure import AbstractByteStructure

# TODO: We really should be using np arrays... however for now to ensure interoperability, use lists of tuples instead

class ActivatedNeuronLocation(AbstractByteStructure):

    structure_id = 7


    def __init__(self, coordinates: list[tuple[int, int, int]]):
        self.activated_neuron_coordinates: list[tuple[int, int, int]] = coordinates


    @staticmethod
    def create_from_list_of_tuples(coordinates: list[tuple[int, int, int]]):
        return ActivatedNeuronLocation(coordinates)
