from SVONode import SVONode
import numpy as np
import struct

MAX_ALLOWED_SVO_DEPTH: int = 32 # You should never be approaching this ANYWAYS, 4b in any dimension!
DEFAULT_PERCENTAGE_AREA_EXPECTED_TO_BE_ACTIVATED: float = 0.30

class SVOTree:

    def __init__(self, depth: int, representing_dimensions: np.ndarray):
        if representing_dimensions.shape != (3,):
            raise ValueError("representing_dimensions must have exactly 3 elements.")

        self._max_depth: int = depth
        self._user_dimension_limit = representing_dimensions
        self._tree_dimension_limit: int = 2 ** depth
        self._root_node: SVONode = SVONode()
        self._number_nodes_per_nonleaf_layer: np.ndarray = np.array([0] * self._max_depth, dtype=np.int32)
        self._total_number_nonleaf_nodes: int = 1
        self._image_size: np.ndarray = np.array([1,1], dtype=np.int16)
        self._data: bytearray
        self.reset_tree()

    @staticmethod
    def create_SVOTree(target_minimum_dimensions: np.ndarray) -> 'SVOTree':
        if target_minimum_dimensions.shape != (3,):
            raise ValueError("target_minimum_dimensions must have exactly 3 elements.")
        max_dim_size: int = target_minimum_dimensions.max()
        if max_dim_size < 1:
            raise ValueError("Dimensions must be or exceed <1,1,1> for SVO!")
        calculated_depth: int = np.ceil(np.log2(max_dim_size)).astype(int)
        if calculated_depth > MAX_ALLOWED_SVO_DEPTH:
            raise ValueError("Dimensions size Exceeded for SVO!")
        return SVOTree(calculated_depth, target_minimum_dimensions)


    def reset_tree(self) -> None:
        """
        Clears all child nodes, to be used again
        """
        self._root_node = SVONode()
        self._number_nodes_per_nonleaf_layer: np.ndarray = np.array([0] * self._max_depth, dtype=np.int32)
        self._number_nodes_per_nonleaf_layer[0] = 1  # root node
        self._total_number_nonleaf_nodes = 1
        self._recompute_cache_memory(np.ceil(float(self._user_dimension_limit[0] * self._user_dimension_limit[1] * self._user_dimension_limit[2]) * DEFAULT_PERCENTAGE_AREA_EXPECTED_TO_BE_ACTIVATED / 8.0).astype(int))

    def add_node(self, position: np.ndarray) -> None:
        """
        Adds a node to a given coordinate (or does nothing if node already exists)
        """
        if position.shape != (3,):
            raise ValueError("position must have exactly 3 elements.")

        if position[0] >= self._user_dimension_limit[0] or position[1] >= self._user_dimension_limit[1] or position[2] >= self._user_dimension_limit[2]:
            raise ValueError("Requested position is out of bounds! Not adding node!")
        if position[0] < 0 or position[0] < 0 or position[0] < 0:
            raise ValueError("Requested position is negative! Not adding node!")
        self._add_node(position)

    def export_as_byte_array(self) -> bytes:
        """
        Exports the tree as is as a bytes array ready for ray marching visualization by Brain Visualizer

        2 parts. the first part is the x y size of what the texture should be (each as 2 byte unsigned shorts), the second part is the output array:
            We have to calculate the byte structure: structure is the following (where each node is 4 bytes)
            Node (inclusive byte ranges):
            Byte 0: Bitmask of active children (0-7),
            Byte 2-3: uint24 node count offset to first child node (if applicable), reverse byte order. If this node was a parent of a leaf (which is not exported, only represented by bitmask), then this value will be 0xFFFFFF
            NOTE: leaf nodes are skipped in the output array, as we only need the bitmask of their parent node to ensure their existance (leaf nodes cannot have child nodes)
            example structure, where the number represents the child index from the parent and the letter is a reference to the node
            ( Root ) a
               ├── [0]b
               │   └── [4]d ─ [0]g
               └── [7]c
                   ├── [3]e ─ [3]h
                   └── [7]f
                        ├─── [1]i
                        └─── [7]j
            The above represents 8x8x8 cube with voxels (top down) <0,0,2>, <7,7,4>, <7,6,6>, <7,7,7>
            Nodes are ordered by layer when outputted, skipping leaf nodes. So the output looking by node structure would be [a,b,c,d,e,f]
            As bytes, this would look like the following (bytes, but each node seperated by parentheses, and sections by | for easier reading):
            (0x81|0x010000)(0x10|0x020000)(0x88|0x020000)(0x01|0xFFFFFF)(0x08|0xFFFFFF)(0x82|0xFFFFFF)
        """
        return struct.pack('HH', self._image_size[0], self._image_size[1]) + self._export_as_bytes_for_shader_image()

    def shrink_memory_usage(self) -> None:
        """
        While the memory allocation can scale up automatically, this function must be called if you intend to scale down memory usage. Intensive so it shouldnt be called often
        """
        self._recompute_texture_memory(self._total_number_nonleaf_nodes)

    def get_tree_max_depth(self) -> int:
        return self._max_depth


    def _add_node(self, node_location: np.ndarray) -> None:
        current_node: SVONode = self._root_node
        size: int = self._tree_dimension_limit
        current_depth: int = 1  # skip root

        while size > 1:
            size /= 2
            octant: int = (int(node_location[0] >= size)) | (int(node_location[1] >= size) << 1) | (
                        int(node_location[2] >= size) << 2)  # bitmask octant

            if not (current_node.child_bitmask & (1 << octant)):  # check if the bit at the "octant" index is false (no child mentioned)
                current_node.child_bitmask |= (1 << octant)  # set the current node's bit at octant index to true as we are creating a child

                if not current_depth < self._max_depth:
                    # we have reached leaf node and labeled it, break out
                    break

                # we are still in internal nodes (not at leaf level yet)
                self._number_nodes_per_nonleaf_layer[current_depth] += 1
                self._total_number_nonleaf_nodes += 1
                new_node: SVONode = SVONode()
                current_node.children[octant] = new_node
                current_node = new_node
            else:
                # a child node exists in the correct location
                if not current_depth < self._max_depth:
                    # we have reached leaf node. it was already labeled, break out
                    break
                current_node = current_node.children[octant]

            node_location %= size
            current_depth += 1


    def _recompute_texture_memory(self, number_of_nodes_to_hold: int) -> None:
        """
        Resizes the bytes array to the number needed, also assuming limitations given texture
        """

        # This is so when using the RF image format, where each pixel is 4 bytes (for 1 float normally), each node only takes 1 pixel
        number_pixels_needed: int = number_of_nodes_to_hold

        # We need to (quickly) find the best rectangle that can hold this data.
        # This following algorithm likely isnt the most memory efficient but is fast
        smallest_square_side: int = np.ceil(np.sqrt(float(number_pixels_needed))).astype(int)
        smallest_rect_side: int = np.ceil(float(number_pixels_needed) / float(smallest_square_side)).astype(int)
        self._max_number_of_nonleaf_nodes_image_can_hold = smallest_square_side * smallest_rect_side

        # we calculated what we need to, now update this object
        self._data = bytearray(self._max_number_of_nonleaf_nodes_image_can_hold * 4) # 4 bytes per pixel
        self._image_size[0] = smallest_square_side
        self._image_size[1] = smallest_rect_side





    def _export_as_bytes_for_shader_image(self) -> bytearray:
        if self._total_number_nonleaf_nodes > self._max_number_of_nonleaf_nodes_image_can_hold:
            self._recompute_texture_memory(self._total_number_nonleaf_nodes)  # expand memory allocation if needed

        if self._max_depth == 0:
            # unique case for single voxel area
            # TODO we should decide how to handle this. Perhaps have the child reference already be 0xFF?
            return bytearray()

        if self._total_number_nonleaf_nodes == 1:
            # Unique case where no nodes were added
            self._data[0] = self._root_node.child_bitmask
            self._data[1] = 255
            self._data[2] = 255
            self._data[3] = 255

        else:
            # do all internal nodes
            current_parent_nodes: list[SVONode] = [self._root_node]
            current_node_array_index: int = 0
            for current_depth in range(self._max_depth - 1):  # loop for all nodes but leaf nodes
                next_parent_nodes: list[SVONode] = []
                child_count_offset: int = 0
                parent_node_index_of_current_depth = 0
                for current_parent_node in current_parent_nodes:
                    parent_nodes_remaining_at_this_depth: int = self._number_nodes_per_nonleaf_layer[current_depth] - parent_node_index_of_current_depth

                    byte_index: int = current_node_array_index * 4
                    self._data[byte_index] = current_parent_node.child_bitmask  # write bitmask for current parent node

                    child_node_offset_index: int = child_count_offset + parent_nodes_remaining_at_this_depth
                    child_offset_uint24: bytes = struct.pack('i', child_node_offset_index)
                    self._data[byte_index + 1] = child_offset_uint24[0]
                    self._data[byte_index + 2] = child_offset_uint24[1]
                    self._data[byte_index + 3] = child_offset_uint24[2]

                    for child_index in range(8):
                        if current_parent_node.child_bitmask & (1 << child_index):  # loop over only children that are existing
                            next_parent_nodes.append(current_parent_node.children[child_index])
                            child_count_offset += 1

                    parent_node_index_of_current_depth += 1

                    current_node_array_index += 1
                current_parent_nodes = next_parent_nodes

            # do not export leaf nodes, instead just add the current parent nodes with the bitmasks, but set their address to #FFFFFF
            for current_parent_node in current_parent_nodes:
                byte_index: int = current_node_array_index * 4
                self._data[byte_index] = current_parent_node.child_bitmask
                self._data[byte_index + 1] = 255
                self._data[byte_index + 2] = 255
                self._data[byte_index + 3] = 255
                current_node_array_index += 1

        return self._data