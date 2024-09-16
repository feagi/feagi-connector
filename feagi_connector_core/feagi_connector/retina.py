#!/usr/bin/env python3
"""
Copyright 2016-2022 The FEAGI Authors. All Rights Reserved.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
==============================================================================
"""

import cv2
import numpy
import asyncio
import traceback
import numpy as np
import zmq.asyncio
from time import sleep
from datetime import datetime
from feagi_connector import router
from feagi_connector import pns_gateway as pns

genome_tracker = 0
previous_genome_timestamp = 0
current_dimension_list = {}


def get_device_of_vision(device):
    """
    Obtain the camera source and bind it using the provided address.

    Args:
    - device: The path to the file, video, or webcam. Webcam should be an integer number.

    Returns:
    - An address corresponding to the webcam source, enabling its use across different files.
    """
    return cv2.VideoCapture(device)


def vision_frame_capture(device=0, RGB_flag=True):
    """
    Capture frames from the specified `device`, which represents the camera source.

    Args:
    - device: The camera device obtained using the `get_device_of_vision()` function.
    - RGB_flag: A boolean indicating whether to retrieve data in RGB format (default: True).
      If set to False, the function returns grayscale data.

    Returns:
    - An nd.array representing the captured frame data. For RGB, it contains three dimensions;
      for grayscale, it displays a single dimension.
      Example format: [[x, y, z], [x, y, z]].
    """
    start_time = datetime.now()
    check, frame = device.read()  # 0 is the default
    # print("vision_frame_capture time total: ", (datetime.now() - start_time).total_seconds())
    if RGB_flag:
        return frame, datetime.now(), check
    else:
        return cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), datetime.now(), check


def vision_region_coordinates(frame_width=None, frame_height=None, x1=None, x2=None, y1=None,
                              y2=None, camera_index=0, size_list=None):
    """
    Calculate coordinates for nine different regions within a frame based on given percentages.

    This function computes the coordinates for nine regions within a frame, defined by x1, x2,
    y1, and y2 percentages. These percentages indicate the position of a point within the frame's
    width and height.

    Inputs:
    - frame_width: Integer, width of the frame.
    - frame_height: Integer, height of the frame.
    - x1, x2, y1, y2: integers representing percentages (0 to 100) along x-axis
    and y-axis.
                      For example, x1=50, y1=40 corresponds to 50% and 40%.

    Output:
    - region_coordinates: Dictionary containing coordinates for nine different regions:
                          'TL', 'TM', 'TR', 'ML', '_C', 'MR', 'BL', 'BM', 'BR'.
                          Each region has its respective coordinates within the frame.

    Note: Make sure that x1, x2, y1, and y2 are valid percentage values within the range of 0 to
    100.
    """
    # start_time = datetime.now()
    # Gaze controls
    x1_prime = int(frame_width * (x1 / 100))
    y1_prime = int(frame_height * (y1 / 100))
    # Pupil controls
    x2_prime = min(x1_prime + int(frame_width * x2 / 100), frame_width)
    y2_prime = min(y1_prime + int(frame_height * y2 / 100), frame_height)

    region_coordinates = dict()
    if (camera_index + 'TL') in size_list:
        region_coordinates[camera_index + 'TL'] = [0, 0, x1_prime, y1_prime]
    if (camera_index + 'TM') in size_list:
        region_coordinates[camera_index + 'TM'] = [x1_prime, 0, x2_prime, y1_prime]
    if (camera_index + 'TR') in size_list:
        region_coordinates[camera_index + 'TR'] = [x2_prime, 0, frame_width, y1_prime]
    if (camera_index + 'ML') in size_list:
        region_coordinates[camera_index + 'ML'] = [0, y1_prime, x1_prime, y2_prime]
    if (camera_index + '_C') in size_list:
        region_coordinates[camera_index + '_C'] = [x1_prime, y1_prime, x2_prime, y2_prime]
    if (camera_index + 'MR') in size_list:
        region_coordinates[camera_index + 'MR'] = [x2_prime, y1_prime, frame_width, y2_prime]
    if (camera_index + 'BL') in size_list:
        region_coordinates[camera_index + 'BL'] = [0, y2_prime, x1_prime, frame_height]
    if (camera_index + 'BM') in size_list:
        region_coordinates[camera_index + 'BM'] = [x1_prime, y2_prime, x2_prime, frame_height]
    if (camera_index + 'BR') in size_list:
        region_coordinates[camera_index + 'BR'] = [x2_prime, y2_prime, frame_width, frame_height]
    # print("vision_region_coordinates time total: ", (datetime.now() - start_time).total_seconds())
    return region_coordinates


def split_vision_regions(coordinates={}, raw_frame_data=[]):
    """
    Split a frame into separate regions based on provided coordinates.

    This function takes the output coordinates from the 'vision_region_coordinates()' function
    and the raw frame data, then splits the frame into nine distinct regions according to those
    coordinates.

    Inputs:
    - coordinates: Dictionary containing the coordinates for nine regions, usually obtained
                   from the 'vision_region_coordinates()' function.
    - raw_frame_data: The original frame data or image used for splitting into regions.

    Output:
    - Display: Visual representation or display of all nine regions independently within the frame.
    """

    # start_time = datetime.now()
    frame_segments = dict()
    for region in coordinates:
        frame_segments[region] = raw_frame_data[coordinates[region][1]:coordinates[region][3],
                                 coordinates[region][0]:coordinates[region][2]]
    # print("split_vision_regions time total: ", (datetime.now() - start_time).total_seconds())
    return frame_segments


def downsize_regions(frame=[], resize=[]):
    """
    Downsize regions within a frame using specified width and height for compression.

    This function utilizes the resize parameter to compress regions within a frame obtained from
     FEAGI's API.
    The frame should be represented as a NumPy ndarray.

    Inputs:
    - frame: NumPy ndarray representing the image/frame data.
    - resize: Tuple containing width and height values for compression.
              Example: (8, 8), (64, 64), (64, 32)

    Output:
    - compressed_dict: Dictionary containing compressed data for nine regions.
                       Each region will be represented within the compressed_dict.

    Make sure that the 'frame' input is a valid NumPy ndarray and the 'resize' parameter contains
    appropriate width and height values for compression.
    """
    # start_time = datetime.now()
    if resize[2] == 3:
        try:
            compressed_dict = cv2.resize(frame, [int(resize[0]), int(resize[1])],
                                         interpolation=cv2.INTER_AREA)
        except Exception as e:
            # print("error inside downsize_regions on retina.py: ", e)
            compressed_dict = np.zeros(resize, dtype=np.uint8)
            compressed_dict = update_astype(compressed_dict)
    if resize[2] == 1:
        try:
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            compressed_dict = cv2.resize(frame, [resize[0], resize[1]],
                                         interpolation=cv2.INTER_AREA)
        except Exception as e:
            # print(e)
            compressed_dict = np.zeros(resize, dtype=np.uint8)
            compressed_dict = update_astype(compressed_dict)
    # print("downsize_regions time total: ", (datetime.now() - start_time).total_seconds())
    return compressed_dict


def create_feagi_data(significant_changes=[], current=[], shape=[], index=[], cortical_name="", grayscale=False):
    """
        :param significant_changes: An array of modified data derived from the raw data.
        :param current: The current raw data.
        :param shape: The shape of the array (e.g., '(64, 64, 3)').
        :param index: An index within [input][camera].
        :param cortical_name: An ID for the cortical area.
        :param grayscale: A boolean indicating if the data is grayscale. True for 3 dimensions, false for 1 dimension.
        :return: A dictionary of difference locations in the FEAGI format.
    """
    # start_time = datetime.now()
    feagi_data = {}
    size_of_frame = shape
    name = 'iv' + cortical_name
    offset_x = (pns.full_list_dimension[name]['cortical_dimensions_per_device'][0] * index)
    if len(significant_changes) > 0:
        if grayscale:
            for x in range(size_of_frame[0]):
                for y in range(size_of_frame[1]):
                    if significant_changes[x, y]:
                        key = f'{offset_x + y}-{((int(size_of_frame[0]) - 1) - x)}-{0}'
                        # key = f'{y}-{(int(size_of_frame[0]) - 1) - x}-{0}'
                        feagi_data[key] = int(current[x, y])
        else:
            for x in range(size_of_frame[0]):
                for y in range(size_of_frame[1]):
                    for z in range(size_of_frame[2]):
                        if significant_changes[x, y, z]:
                            key = f'{offset_x + y}-{((int(size_of_frame[0]) - 1) - x)}-{z}'
                            # key = f'{y}-{((int(size_of_frame[0]) - 1) - x)}-{z}'
                            feagi_data[key] = int(current[x, y, z])
    return feagi_data


def get_difference_from_two_images(previous=[], current=[]):
    """
    Compare two images and detect which pixel changed using cv2 functions.
    """
    return cv2.absdiff(previous, current)


def vision_blink(image=[], blink=[]):
    """
    Blink to turn the whole screen briight until next burst
    """
    if len(blink) != 0:
        difference = blink
        image = cv2.threshold(difference, 0, 255,cv2.THRESH_TOZERO_INV)
    return image[1]


def apply_threshold(difference=[], src=50):
    return cv2.threshold(difference, src, 255,cv2.THRESH_TOZERO)


def change_detector(previous=[], current=[], src=50, compare_image=True, cortical_name=""):
    """
    Detects changes between previous and current frames and checks against a threshold.

    Compares the previous and current frames to identify differences. If the difference
    exceeds a predefined threshold (iso), it records the change in a dictionary for Feagi.

    Inputs:
    - previous: Dictionary with 'cortical' keys containing NumPy ndarray frames.
    - current: Dictionary with 'cortical' keys containing NumPy ndarray frames.

    Output:
    - Dictionary containing changes in the ndarray frames.
    """
    if current.shape == previous.shape:
        if compare_image:
            difference = get_difference_from_two_images(previous, current)
        else:
            difference = current
        _, thresholded = apply_threshold(difference,src=src)
        return thresholded
    else:
        return {}


def generating_rgb_data(percentage=1.0, cortical_name="", thresholded=[], current=[], previous=[], feagi_index=0, grayscale=False):
    if drop_high_frequency_events(thresholded) <= (get_full_dimension_of_cortical_area(cortical_name) * percentage):
        feagi_data = create_feagi_data(thresholded, current, previous.shape, feagi_index,
                                       cortical_name, grayscale=grayscale)
        return dict(feagi_data)
    else:
        return {}


def flip_the_camera(data=[]):
    return cv2.flip(data, 1)


def grab_cortical_resolution(name="", cortical=""):
    return [pns.full_list_dimension[name]['cortical_dimensions_per_device'][0],
            pns.full_list_dimension[name]['cortical_dimensions_per_device'][1],
            current_dimension_list[cortical][2]]


def grab_XY_cortical_resolution(name=""):
    return pns.full_list_dimension[name]['cortical_dimensions_per_device'][0],\
           pns.full_list_dimension[name]['cortical_dimensions_per_device'][1]


def get_full_dimension_of_cortical_area(cortical_name=""):
    global current_dimension_list
    return current_dimension_list[cortical_name][0] * current_dimension_list[cortical_name][1] * \
           current_dimension_list[cortical_name][2]


def process_visual_stimuli(raw_frame=[], capabilities={}, previous_frame_data={}, rgb={}, actual_capabilities={}, compare_image=True):
    global current_dimension_list

    if isinstance(raw_frame, numpy.ndarray):
        temp_dict = {0: raw_frame}
        raw_frame = temp_dict.copy()

    capabilities = pns.create_runtime_default_list(capabilities, actual_capabilities)
    if pns.resize_list:
        current_dimension_list = pns.resize_list
        one_data_vision = {}
        for obtain_raw_data in raw_frame:
            if not capabilities['input']['camera'][str(obtain_raw_data)]['disabled']:
                if obtain_raw_data in capabilities['input']['camera'][str(obtain_raw_data)]['blink']:
                    raw_frame[obtain_raw_data] = vision_blink(raw_frame, capabilities['input']['camera'][str(obtain_raw_data)]['blink'])
                if capabilities['input']['camera'][str(obtain_raw_data)]["mirror"]:
                    raw_frame[obtain_raw_data] = cv2.flip(raw_frame[obtain_raw_data], 1)
                region_coordinates = vision_region_coordinates(
                    frame_width=raw_frame[obtain_raw_data].shape[1],
                    frame_height=raw_frame[obtain_raw_data].shape[0],
                    x1=abs(capabilities['input']['camera'][str(obtain_raw_data)]['eccentricity_control']['X offset percentage']),
                    x2=abs(capabilities['input']['camera'][str(obtain_raw_data)]['modulation_control']['X offset percentage']),
                    y1=abs(capabilities['input']['camera'][str(obtain_raw_data)]['eccentricity_control']['Y offset percentage']),
                    y2=abs(capabilities['input']['camera'][str(obtain_raw_data)]['modulation_control']['Y offset percentage']),
                    camera_index=capabilities['input']['camera'][str(obtain_raw_data)]['index'],
                    size_list=current_dimension_list)

                if not region_coordinates:
                    if not (capabilities['input']['camera'][str(obtain_raw_data)]['index'] + '_C') in current_dimension_list:
                        pns.resize_list.update(obtain_cortical_vision_size(capabilities['input']['camera'][str(obtain_raw_data)]['index'], pns.full_list_dimension))
                segmented_frame_data = split_vision_regions(coordinates=region_coordinates, raw_frame_data=raw_frame[obtain_raw_data])

                if len(one_data_vision) == 0:
                    for region in segmented_frame_data:
                        one_data_vision[region] = []
                compressed_data = dict()

                for cortical in segmented_frame_data:
                    name = 'iv' + cortical
                    updated_size = grab_cortical_resolution(name, cortical)
                    compressed_data[cortical] = downsize_regions(frame=segmented_frame_data[cortical], resize=updated_size)
                    if 0 in capabilities['input']['camera'][str(obtain_raw_data)]['enhancement']:
                        compressed_data[cortical] = adjust_brightness(image=compressed_data[cortical], bright=capabilities['input']['camera'][str(obtain_raw_data)]['enhancement'][0])
                    if 1 in capabilities['input']['camera'][str(obtain_raw_data)]['enhancement']:
                        compressed_data[cortical] = adjust_contrast(image=compressed_data[cortical], contrast=capabilities['input']['camera'][str(obtain_raw_data)]['enhancement'][1])
                    if 2 in capabilities['input']['camera'][str(obtain_raw_data)]['enhancement']:
                        compressed_data[cortical] = adjust_shadow(image=compressed_data[cortical], shadow=capabilities['input']['camera'][str(obtain_raw_data)]['enhancement'][2])
                    if len(one_data_vision[cortical]) == 0:  # update the newest data into empty one_data_vision
                        one_data_vision[cortical] = compressed_data[cortical]
                    else:
                        one_data_vision[cortical] = numpy.concatenate((one_data_vision[cortical], compressed_data[cortical]), axis=1)
                        if (len(raw_frame) - 1) == obtain_raw_data:  # Reach to end of the list for camera
                            one_data_vision[cortical] = cv2.resize(one_data_vision[cortical],
                                                                   grab_XY_cortical_resolution(name),
                                                                   interpolation=cv2.INTER_AREA)

        vision_dict = dict()
        # for segment in compressed_data:
        #     if "_C" in segment:
        #         cv2.imshow(segment, compressed_data[segment])
        # if cv2.waitKey(30) & 0xFF == ord('q'):
        #     pass
        for get_region in one_data_vision:
            if current_dimension_list[get_region][2] == 3:
                if previous_frame_data != {}:
                    if get_region in previous_frame_data:
                        modified_data = change_detector(
                            previous_frame_data[get_region],
                            one_data_vision[get_region],
                            capabilities['input']['camera'][str(obtain_raw_data)]['threshold_default'], compare_image, get_region)
                        vision_dict[get_region] = generating_rgb_data(
                            capabilities['input']['camera'][str(obtain_raw_data)]['percentage_to_allow_data'],
                        get_region, modified_data, one_data_vision[get_region],
                            previous_frame_data[get_region], capabilities['input']['camera'][str(obtain_raw_data)]['feagi_index'])
                    else:
                        vision_dict[get_region] = change_detector(
                            np.zeros((3, 3, 3)),
                            one_data_vision[get_region],
                            capabilities['input']['camera'][str(obtain_raw_data)]['threshold_default'], compare_image, get_region)
            else:
                if previous_frame_data != {}:
                    if get_region in previous_frame_data:
                        modified_data = change_detector(
                            previous_frame_data[get_region],
                            one_data_vision[get_region],
                            capabilities['input']['camera'][str(obtain_raw_data)]['threshold_default'], compare_image, get_region)

                        vision_dict[get_region] = generating_rgb_data(
                            capabilities['input']['camera'][str(obtain_raw_data)]['percentage_to_allow_data'],
                            get_region, modified_data, one_data_vision[get_region],
                            previous_frame_data[get_region],
                            capabilities['input']['camera'][str(obtain_raw_data)]['feagi_index'],
                            grayscale=True)
                    else:
                        vision_dict[get_region] = change_detector(
                            np.zeros((3, 3, 3)),
                            one_data_vision[get_region],
                            capabilities, compare_image, get_region)
        if previous_frame_data:
            previous_frame_data.update(one_data_vision)
        else:
            previous_frame_data = one_data_vision
        if 'camera' in rgb:
            rgb['camera'].update(vision_dict)
        else:
            rgb['camera'] = vision_dict

        for index in capabilities['input']['camera']:
            if len(capabilities['input']['camera'][index]['blink']) > 0:
                capabilities['input']['camera'][index]['blink'] = []
        return previous_frame_data, rgb, capabilities
    return pns.resize_list, pns.resize_list, capabilities  # sending empty dict


def obtain_cortical_vision_size(camera_index="00", response=""):
    size_list = {}
    data = response
    items = [camera_index + "_C", camera_index + "BL", camera_index + "BM", camera_index + "BR",
             camera_index + "MR", camera_index + "ML", camera_index + "TR", camera_index + "TL",
             camera_index + "TM"]
    if data is not None:
        for name_from_data in data:
            for fetch_name in items:
                if fetch_name in name_from_data:
                    name = name_from_data.replace("iv", "")
                    dimension_array = data[name_from_data]["cortical_dimensions"][0], \
                                      data[name_from_data]["cortical_dimensions"][1], \
                                      data[name_from_data]["cortical_dimensions"][2]
                    size_list[name] = dimension_array
    return size_list


def drop_high_frequency_events(data=[]):
    return np.count_nonzero(data)


def process_visual_stimuli_trainer(raw_frame={}, capabilities={}, previous_frame_data={}, rgb={},
                                   actual_capabilities={}, compare_image=False):
    global current_dimension_list

    if isinstance(raw_frame, numpy.ndarray):
        temp_dict = {0: raw_frame}
        raw_frame = temp_dict.copy()

    capabilities = pns.create_runtime_default_list(capabilities, actual_capabilities)
    if pns.resize_list:
        current_dimension_list = pns.resize_list
        one_data_vision = {}
        for obtain_raw_data in raw_frame:
            if not capabilities['input']['camera'][str(obtain_raw_data)]['disabled']:
                if 0 in capabilities['input']['camera'][str(obtain_raw_data)]['blink']:
                    raw_frame[obtain_raw_data] = vision_blink(raw_frame, capabilities['input']['camera'][str(obtain_raw_data)]['blink'][0])
                if capabilities['input']['camera'][str(obtain_raw_data)]["mirror"]:
                    raw_frame[obtain_raw_data] = cv2.flip(raw_frame[obtain_raw_data], 1)
                region_coordinates = vision_region_coordinates(
                    frame_width=raw_frame[obtain_raw_data].shape[1],
                    frame_height=raw_frame[obtain_raw_data].shape[0],
                    x1=abs(capabilities['input']['camera'][str(obtain_raw_data)]['eccentricity_control']['X offset percentage']),
                    x2=abs(capabilities['input']['camera'][str(obtain_raw_data)]['modulation_control']['X offset percentage']),
                    y1=abs(capabilities['input']['camera'][str(obtain_raw_data)]['eccentricity_control']['Y offset percentage']),
                    y2=abs(capabilities['input']['camera'][str(obtain_raw_data)]['modulation_control']['Y offset percentage']),
                    camera_index=capabilities['input']['camera'][str(obtain_raw_data)]['index'],
                    size_list=current_dimension_list)

                if not region_coordinates:
                    if not (capabilities['input']['camera'][str(obtain_raw_data)]['index'] + '_C') in current_dimension_list:
                        pns.resize_list.update(obtain_cortical_vision_size(capabilities['input']['camera'][str(obtain_raw_data)]['index'], pns.full_list_dimension))
                segmented_frame_data = split_vision_regions(coordinates=region_coordinates,
                                                            raw_frame_data=raw_frame[
                                                                obtain_raw_data])

                if len(one_data_vision) == 0:
                    for region in segmented_frame_data:
                        one_data_vision[region] = []
                compressed_data = dict()

                for cortical in segmented_frame_data:
                    name = 'iv' + cortical
                    updated_size = grab_cortical_resolution(name=name, cortical=cortical)
                    compressed_data[cortical] = downsize_regions(frame=segmented_frame_data[cortical], resize=updated_size)
                    if 0 in capabilities['input']['camera'][str(obtain_raw_data)]['enhancement']:
                        compressed_data[cortical] = adjust_brightness(image=compressed_data[cortical], bright=capabilities['input']['camera'][str(obtain_raw_data)]['enhancement'][0])
                    if 1 in capabilities['input']['camera'][str(obtain_raw_data)]['enhancement']:
                        compressed_data[cortical] = adjust_contrast(image=compressed_data[cortical], contrast=capabilities['input']['camera'][str(obtain_raw_data)]['enhancement'][1])
                    if 2 in capabilities['input']['camera'][str(obtain_raw_data)]['enhancement']:
                        compressed_data[cortical] = adjust_shadow(image=compressed_data[cortical], shadow=capabilities['input']['camera'][str(obtain_raw_data)]['enhancement'][2])
                    if len(one_data_vision[
                               cortical]) == 0:  # update the newest data into empty one_data_vision
                        one_data_vision[cortical] = compressed_data[cortical]
                    else:
                        one_data_vision[cortical] = numpy.concatenate(
                            (one_data_vision[cortical], compressed_data[cortical]), axis=1)
                        if (
                                len(raw_frame) - 1) == obtain_raw_data:  # Reach to end of the list for camera
                            one_data_vision[cortical] = cv2.resize(one_data_vision[cortical], grab_XY_cortical_resolution(name), interpolation=cv2.INTER_AREA)

        vision_dict = dict()
        # for segment in compressed_data:
        #     if "_C" in segment:
        #         cv2.imshow(segment, compressed_data[segment])
        # if cv2.waitKey(30) & 0xFF == ord('q'):
        #     pass
        modified_data_dict = {}
        for get_region in one_data_vision:
            if current_dimension_list[get_region][2] == 3:
                if previous_frame_data != {}:
                    if get_region in previous_frame_data:
                        modified_data = change_detector(
                            previous=previous_frame_data[get_region],
                            current=one_data_vision[get_region],
                            src=capabilities['input']['camera'][str(obtain_raw_data)]['threshold_default'], compare_image=compare_image, cortical_name=get_region)

                        vision_dict[get_region] = generating_rgb_data(percentage=capabilities['input']['camera'][str(obtain_raw_data)]['percentage_to_allow_data'],
                                                                      cortical_name=get_region,
                                                                      thresholded=modified_data,
                                                                      current=one_data_vision[get_region],
                                                                      previous=previous_frame_data[get_region],
                                                                      feagi_index=capabilities['input']['camera'][str(obtain_raw_data)]['feagi_index'])

                        modified_data_dict[get_region] = modified_data
                    else:
                        vision_dict[get_region] = change_detector(
                            previous=np.zeros((3, 3, 3)),
                            current=one_data_vision[get_region],
                            src=capabilities['input']['camera'][str(obtain_raw_data)]['threshold_default'],
                            compare_image=compare_image,
                            cortical_name=get_region)
            else:
                if previous_frame_data != {}:
                    if get_region in previous_frame_data:
                        modified_data = change_detector(
                            previous=previous_frame_data[get_region],
                            current=one_data_vision[get_region],
                            src=capabilities['input']['camera'][str(obtain_raw_data)]['threshold_default'],
                            compare_image=compare_image,
                            cortical_name=get_region)

                        vision_dict[get_region] = generating_rgb_data(
                            percentage=capabilities['input']['camera'][str(obtain_raw_data)]['percentage_to_allow_data'],
                            cortical_name=get_region,
                            thresholded=modified_data,
                            current=one_data_vision[get_region],
                            previous=previous_frame_data[get_region],
                            feagi_index=capabilities['input']['camera'][str(obtain_raw_data)]['feagi_index'],
                            grayscale=True)
                        modified_data_dict[get_region] = modified_data
                    else:
                        vision_dict[get_region] = change_detector(
                            previous=np.zeros((3, 3, 3)),
                            current=one_data_vision[get_region],
                            src=capabilities['input']['camera'][str(obtain_raw_data)]['threshold_default'],
                            compare_image=compare_image,
                            cortical_name=get_region)
        if previous_frame_data:
            previous_frame_data.update(one_data_vision)
        else:
            previous_frame_data = one_data_vision
        if 'camera' in rgb:
            rgb['camera'].update(vision_dict)
        else:
            rgb['camera'] = vision_dict
        return previous_frame_data, rgb, capabilities, modified_data_dict
    return pns.resize_list, pns.resize_list, capabilities, {}  # sending empty dict


def vision_progress(capabilities={}, feagi_settings={}, raw_frame={}):
    global genome_tracker, previous_genome_timestamp
    while True:
        message_from_feagi = pns.message_from_feagi
        if message_from_feagi is not None and message_from_feagi:
            capabilities = pns.fetch_vision_turner(message_from_feagi, capabilities)
            capabilities = pns.fetch_enhancement_data(message_from_feagi, capabilities)
            capabilities = pns.fetch_threshold_type(message_from_feagi, capabilities)
            capabilities = pns.fetch_mirror_opu(message_from_feagi, capabilities)
            # Update resize if genome has been changed:
            pns.check_genome_status(message_from_feagi, capabilities)
            if isinstance(raw_frame, dict):
                if 'vision' in raw_frame:
                    capabilities = pns.obtain_blink_data(raw_frame['vision'], message_from_feagi, capabilities)  # for javascript webcam
                else:
                    capabilities = pns.obtain_blink_data(raw_frame, message_from_feagi, capabilities)  # for multiple support cameras
            else:
                capabilities = pns.obtain_blink_data(raw_frame, message_from_feagi, capabilities)  # regular cameras
            capabilities = pns.monitor_switch(message_from_feagi, capabilities)
            capabilities = pns.eccentricity_control_update(message_from_feagi, capabilities)
            capabilities = pns.modulation_control_update(message_from_feagi, capabilities)
            feagi_settings['feagi_burst_speed'] = pns.check_refresh_rate(message_from_feagi, feagi_settings['feagi_burst_speed'])
        sleep(feagi_settings['feagi_burst_speed'])

    # return capabilities, feagi_settings['feagi_burst_speed']


def update_astype(data=[]):
    return data.astype(np.uint8)


def RGB_list_to_ndarray(data=[], size=[]):
    new_rgb = np.array(data)
    new_rgb = new_rgb.reshape(size[1], size[0], 3)
    return new_rgb


def flip_video(data=[]):
    return cv2.flip(data, 1)


def check_brightness(frame=[]):
    # Calculate the average pixel intensity (brightness)
    average_intensity = cv2.mean(frame)[0]

    # Define thresholds for brightness
    brightness_threshold = 127  # Adjust this threshold as needed

    # Check if the average intensity is above or below the threshold
    if average_intensity > brightness_threshold:
        return "Image is too bright"
    elif average_intensity < brightness_threshold:
        return "Image is too dark"
    else:
        return "Image is neither too bright nor too dark"


def threshold_detect(capabilities={}):
    threshold_type = [cv2.THRESH_BINARY, cv2.THRESH_BINARY_INV, cv2.THRESH_TRUNC, cv2.THRESH_TOZERO, cv2.THRESH_TOZERO_INV, cv2.THRESH_OTSU]
    threshold_total = cv2.THRESH_BINARY
    if capabilities['input']['camera'][str(obtain_raw_data)]['threshold_type']:
        for threshold_selected in range(len(capabilities['input']['camera'][str(obtain_raw_data)]['threshold_type'])):
            threshold_total = threshold_type[threshold_selected]
    capabilities['input']['camera'][str(obtain_raw_data)]['threshold_type'].clear()
    return threshold_total

def adjust_brightness(image=[], bright=None):
    if bright:
        highlight = 255
        alpha_b = (highlight - bright) / 255
        gamma_b = bright
        image = cv2.addWeighted(image, alpha_b, image, 0, gamma_b)
    return image

def adjust_contrast(image=[], contrast=None):
    if contrast:
        image = cv2.convertScaleAbs(image, alpha=contrast, beta=0)
    return image

def adjust_shadow(image=[], shadow=None):
    if shadow:
        maxIntensity = 255.0
        phi = 1
        theta = 1
        adjusted = (maxIntensity / phi) * (image / (maxIntensity / theta)) ** shadow
        image = np.array(adjusted, dtype=np.uint8)
    return image


def convert_new_json_to_old_json(capabilities, index='0'):
    """
    deprecated: Converts the new JSON format to the old JSON format.

    Does nothing
    """

    print("This function, `convert_new_json_to_old_json`, is deprecated. Please remove this "
          "function, as it currently does nothing. It will be removed in the next version.")
    return capabilities