from .AbstractByteStructure import AbstractByteStructure
from .SVO.SVOTree import SVOTree
import numpy as np

class SVORaymarchingByteStructure(AbstractByteStructure):

    structure_id: int = 10

    def __init__(self, dimensions: np.ndarray):
        self.svo: SVOTree = SVOTree.create_SVOTree(dimensions)
        self.dimensions = dimensions

    @staticmethod
    def create_from_bytes(byte_array: bytes) -> 'SVORaymarchingByteStructure':
        SVORaymarchingByteStructure.confirm_header(byte_array) # throws an exception if something is wrong
        raise NotImplemented("Not implemented!")


    @staticmethod
    def create_from_summary_data(dimensions: np.ndarray, activated_voxels: np.ndarray) -> 'SVORaymarchingByteStructure':
        structure: SVORaymarchingByteStructure  = SVORaymarchingByteStructure(dimensions)
        structure.add_activated_voxels(activated_voxels)
        return structure

    def add_activated_voxels(self, activated_voxels: np.ndarray):
        """
        Allows adding multiple activated voxels, given a 2d array where each row is the integer xyz coordinate of the activated voxel. Assumes Cortical Area size is unchanged
        """
        for row in activated_voxels:
            self.svo.add_node(row)

    def reset_tree(self):
        """
        Clears added nodes to tree, but still keeps the tree at its given size
        """
        self.svo.reset_tree()

    def change_dimensions(self, new_dimensions: np.ndarray):
        """
        Should be called when cortical area changes dimensions, to reallocate SVO tree
        """
        # TODO this can be optimized since not all dimension changes require recomputation of SVO hierarchy
        self.svo: SVOTree = SVOTree.create_SVOTree(new_dimensions)
        self.dimensions = new_dimensions

    def is_dimension_matching(self, checking_dimensions: np.ndarray):
        return self.dimensions == checking_dimensions

    def to_bytes(self) -> bytes:
        return bytes(self._create_header() + self.svo.export_as_byte_array())
