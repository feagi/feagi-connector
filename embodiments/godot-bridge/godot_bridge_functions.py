import requests
import ast


# def generate_max_second(config_max, second):
#     return config_max / round(second, 3)
#

def simulation_testing():
    """
    This is to stress the CPU using Godot. You should be able to see the red cube filled with
    small red cubes inside. You can simply uncomment this function in main() to test the
    stress and increase the iteration numbers to stress more..
    """
    array = [[random.randint(0, 64), random.randint(0, 64), random.randint(0, 64)] for _ in
             range(1000)]
    return array


def godot_data(data_input):
    """
    Simply clean the list and remove all unnecessary special characters and deliver with name, xyz
    only
    """
    return ast.literal_eval(data_input)
    # data = ast.literal_eval(data_input)
    # dict_with_updated_name = {"data": {}}
    # dict_with_updated_name["data"]["direct_stimulation"] = dict({})
    # for key in data["data"]["direct_stimulation"]:
    #     updated_name = key
    #     if dict_with_updated_name["data"]["direct_stimulation"].get(updated_name) is not None:
    #         pass
    #     else:
    #         dict_with_updated_name["data"]["direct_stimulation"][updated_name] = []
    #     for key_01 in data["data"]["direct_stimulation"][key]:
    #         dict_with_updated_name["data"]["direct_stimulation"][updated_name].append(key_01)

    # print("godot_data: ", dict_with_updated_name)
    # return dict_with_updated_name


# def name_to_id(name):
#     """
#     Convert from name to id of the cortical area name
#     """
#     for cortical_area in runtime_data["cortical_data"]:
#         if cortical_area == name:
#             return runtime_data["cortical_data"][cortical_area][7]
#
#     print("*** Failed to find cortical name ***")
#     return None


def feagi_breakdown(data, feagi_host_input, api_port_input, dimensions_endpoint_input,
                    runtime_data):
    """
    Designed for genome 2.0 only. Data is the input from feagi's raw data.
    This function will detect if cortical area list is different than the first, it will generate
    genome list for godot automatically.
    """
    try:
        new_list = []
        new_genome_num = data['genome_num']
        if new_genome_num > runtime_data["genome_number"]:
            runtime_data["old_cortical_data"] = runtime_data["cortical_data"]
            runtime_data["cortical_data"] = \
                requests.get('http://' + feagi_host_input + ':' + api_port_input +
                             dimensions_endpoint_input, timeout=10).json()
            if 'genome_reset' not in data and data == "{}":
                runtime_data["cortical_data"] = \
                    requests.get(
                        'http://' + feagi_host_input + ':' + api_port_input +
                        dimensions_endpoint_input, timeout=10).json()
            if data != "{}":
                if runtime_data["old_cortical_data"] != runtime_data["cortical_data"]:
                    pass
            runtime_data["genome_number"] = new_genome_num
        for i in data['godot']:
            new_list.append([i[1], i[2], i[3]])
        return new_list
    except requests.exceptions.RequestException as error:
        logging.exception(error)
        print("Exception during feagi_breakdown", error)
        return None


def convert_absolute_to_relative_coordinate(stimulation_from_godot, cortical_data):
    """
    Convert absolute coordinate from godot to relative coordinate for FEAGI. Dna_information is
    from the genome["blueprint"].
    """
    relative_coordinate = {"data": {"direct_stimulation": {}}}

    if stimulation_from_godot:
        for godot_key, xyz_list in stimulation_from_godot["data"]["direct_stimulation"].items():
            for cortical_info in cortical_data.values():
                cortical_name = cortical_info[7]
                if cortical_name == godot_key:
                    if cortical_name not in relative_coordinate["data"]["direct_stimulation"]:
                        relative_coordinate["data"]["direct_stimulation"][cortical_name] = []

                    for xyz in xyz_list:
                        new_xyz = [xyz[0] - cortical_info[0],
                                   xyz[1] - cortical_info[1],
                                   xyz[2] - cortical_info[2]]
                        relative_coordinate["data"]["direct_stimulation"][cortical_name]. \
                            append(new_xyz)
                    break

    return relative_coordinate

# def download_genome(feagi_host_input, api_port_input, endpoint):
#     """
#     Fetch and download the genome from FEAGI API
#     """
#     try:
#         data_from_genome = requests.get('http://' + feagi_host_input + ':' + api_port_input +
#                                         '/v1/genome/download',
#                                         timeout=10).json()
#         cortical_area_name = requests.get(
#             'http://' + feagi_host_input + ':' + api_port_input + endpoint, timeout=10).json()
#         return data_from_genome, cortical_area_name
#     except requests.exceptions.RequestException as error:
#         print("Error while fetching genome from FEAGI: ", error)
#         logging.exception(error)
#         return None, None


# def process_genome_data(runtime_data_list, cortical_data):
#     """
#     Check if the name matches
#     """
#     cortical_name = [cortical_data[x_cortical][7] for x_cortical in cortical_data]
#     cortical_genome_dictionary = {"genome": {}}
#
#     for i in runtime_data_list["cortical_data"]["blueprint"]:
#         for x_cortical in cortical_name:
#             if x_cortical in i:
#                 if x_cortical not in cortical_genome_dictionary['genome']:
#                     cortical_genome_dictionary['genome'][x_cortical] = []
#                 cortical_genome_dictionary['genome'][x_cortical].append(
#                     runtime_data_list["cortical_data"]["blueprint"][i])
#
#     return cortical_genome_dictionary


# def reload_genome(feagi_host_input, api_port_host, endpoint):
#     """
#     Every genome reloads or updated, this will be called.
#     """
#     while True:
#         cortical_genome_dictionary = {"genome": {}}
#         print("+++ 0 +++")
#
#         data_from_genome, cortical_area_name = download_genome(feagi_host_input, api_port_host,
#                                                                endpoint)
#         if data_from_genome and cortical_area_name:
#             runtime_data["cortical_data"] = data_from_genome
#             print("cortical_area_name: ", cortical_area_name)
#
#             cortical_genome_dictionary = process_genome_data(runtime_data, cortical_area_name)
#
#             json_object = json.dumps(cortical_genome_dictionary)
#             zmq_queue.append(json_object)
#
#         time.sleep(2)
#
#         print("Genome reloaded.")
#         if len(ws_queue[0]) > 2:
#             ws_queue.clear()
#         runtime_data["cortical_data"] = cortical_area_name
#         return cortical_genome_dictionary.copy()
