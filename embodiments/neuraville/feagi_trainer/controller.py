#!/usr/bin/env python
# -*- coding: utf-8 -*-
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

from time import sleep
from datetime import datetime
from feagi_agent import pns_gateway as pns
from feagi_agent import retina as retina
from feagi_agent.version import __version__
from feagi_agent import feagi_interface as feagi
from feagi_agent import testing_mode
from feagi_agent import trainer as feagi_trainer
from configuration import *
import requests
import threading
import os
import cv2

if __name__ == "__main__":
    # Generate runtime dictionary
    runtime_data = {"vision": {}, "current_burst_id": None, "stimulation_period": None,
                    "feagi_state": None,
                    "feagi_network": None}
    print("retrying...")
    FEAGI_FLAG = False
    print("Waiting on FEAGI...")
    while not FEAGI_FLAG:
        FEAGI_FLAG = feagi.is_FEAGI_reachable(
            os.environ.get('FEAGI_HOST_INTERNAL', feagi_settings["feagi_host"]),
            int(os.environ.get('FEAGI_OPU_PORT', "3000")))
        sleep(2)
    # # # FEAGI registration # # # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    # - - - - - - - - - - - - - - - - - - #
    feagi_settings, runtime_data, api_address, feagi_ipu_channel, feagi_opu_channel = \
        feagi.connect_to_feagi(feagi_settings, runtime_data, agent_settings, capabilities,
                               __version__)
    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    msg_counter = runtime_data["feagi_state"]['burst_counter']
    if not pns.full_list_dimension:
        pns.full_list_dimension = pns.fetch_full_dimensions()
    rgb = dict()
    rgb['camera'] = dict()
    previous_frame_data = {}
    response = requests.get(api_address + '/v1/feagi/genome/cortical_area/geometry')
    size_list = retina.obtain_cortical_vision_size("00", response)  # Temporarily
    start_timer = 0
    raw_frame = []
    continue_loop = True
    total = 0
    success = 0
    success_rate = 0
    # overwrite manual
    camera_data = dict()
    camera_data['vision'] = dict()
    threading.Thread(target=pns.feagi_listener, args=(feagi_opu_channel,), daemon=True).start()
    threading.Thread(target=retina.vision_progress, args=(capabilities, feagi_opu_channel,
                                                          api_address, feagi_settings,
                                       camera_data['vision'],), daemon=True).start()
    while continue_loop:
        image_obj = feagi_trainer.scan_the_folder(capabilities['image_reader']['path'])
        for image in image_obj:
            raw_frame = image[0]
            camera_data['vision'] = raw_frame
            name_id = image[1]
            message_to_feagi = feagi_trainer.id_training_with_image(message_to_feagi, name_id)
            # Post image into vision
            # CUSTOM MADE ONLY #############################
            if size_list:
                region_coordinates = retina.vision_region_coordinates(frame_width=raw_frame.shape[1],
                                                                      frame_height=raw_frame.shape[0],
                                                                      x1=abs(capabilities['camera']['gaze_control'][0]),
                                                                      x2=abs(capabilities['camera']['pupil_control'][0]),
                                                                      y1=abs(capabilities['camera']['gaze_control'][1]),
                                                                      y2=abs(capabilities['camera']['pupil_control'][1]),
                                                                      camera_index="00",
                                                                      size_list=size_list)
                segmented_frame_data = retina.split_vision_regions(
                    coordinates=region_coordinates, raw_frame_data=raw_frame)
                compressed_data = dict()
                for cortical in segmented_frame_data:
                    compressed_data[cortical] = retina.downsize_regions(segmented_frame_data[
                                                                            cortical],
                                                                        size_list[cortical])
                for segment in compressed_data:
                    cv2.imshow(segment, compressed_data[segment])
                if cv2.waitKey(30) & 0xFF == ord('q'):
                    pass
                vision_dict = dict()
                for get_region in compressed_data:
                    if size_list[get_region][2] == 3:
                        if previous_frame_data != {}:
                            thresholded = cv2.threshold(compressed_data[get_region],
                                                        capabilities['camera']['threshold_default'][
                                                            0],
                                                        capabilities['camera']['threshold_default'][
                                                            1],
                                                        cv2.THRESH_TOZERO)[1]
                            vision_dict[get_region] = \
                                retina.create_feagi_data(thresholded,
                                                         compressed_data[get_region],
                                                         previous_frame_data[get_region].shape)
                    else:
                        if previous_frame_data != {}:
                            thresholded = cv2.threshold(compressed_data[get_region],
                                                        capabilities['camera']['threshold_default'][
                                                            0],
                                                        capabilities['camera']['threshold_default'][
                                                            1],
                                                        cv2.THRESH_TOZERO)[1]
                            vision_dict[get_region] = \
                                retina.create_feagi_data_grayscale(thresholded,
                                                                   compressed_data[get_region],
                                                                   previous_frame_data[get_region].shape)
                print(capabilities['camera']['gaze_control'])
                previous_frame_data = compressed_data
                rgb['camera'] = vision_dict
            # capabilities, feagi_settings['feagi_burst_speed'] = retina.vision_progress(
            #     capabilities, feagi_opu_channel, api_address, feagi_settings, raw_frame)
            message_to_feagi = pns.generate_feagi_data(rgb, msg_counter, datetime.now(),
                                                       message_to_feagi)
            # Vision process ends of custom
            if start_timer == 0:
                start_timer = datetime.now()
            while capabilities['image_reader']['pause'] >= int(
                (datetime.now() - start_timer).total_seconds()):
                # Testing mode section
                if capabilities['image_reader']['test_mode']:
                    success_rate, success, total = testing_mode.mode_testing(name_id,
                                                                             feagi_opu_channel,
                                                                             total, success,
                                                                             success_rate)
                else:
                    success_rate, success, total = 0, 0, 0
                pns.signals_to_feagi(message_to_feagi, feagi_ipu_channel, agent_settings)
            start_timer = 0
            message_to_feagi.clear()

        continue_loop = capabilities['image_reader']['loop']
