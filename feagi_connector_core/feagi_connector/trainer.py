import os
import re
import cv2
from feagi_connector import pns_gateway as pns


def scan_the_folder(path_direction):
  """
  Generator to yield image files with specific pattern in filename.
  Useful for filtering training images provided by the user.
  Will ignore the file if it doesn't have #-#-# in the filename or isn't an image.
  """
  folder_path = path_direction
  files = os.listdir(folder_path)
  pattern = re.compile(r'\d+-\d+-\d+\..+')
  image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp']
  video_extensions = ['.mov', '.mpg', '.mp4']
  for filename in files:
    if pattern.match(filename) and os.path.splitext(filename)[1].lower() in video_extensions:
      id_message = dict()
      name_only = os.path.splitext(filename)[0]
      extension = os.path.splitext(filename)[1]
      cap = cv2.VideoCapture(filename)
      frame = []
      id_message[name_only] = 100
      ret, frame = cap.read()
      yield cap, id_message, extension
      #
      # while (cap.isOpened()):
      #     # Capture frame-by-frame
      #     ret, frame = cap.read()
      #     if ret == True:
      #         id_message[name_only] = 100
      #         yield frame, id_message, extension
      #     # Break the loop
      #     else:
      #         break
      #
      # print("exited")

    elif pattern.match(filename) and os.path.splitext(filename)[1].lower() in image_extensions:
      id_message = dict()
      name_only = os.path.splitext(filename)[0]
      id_message[name_only] = 100
      extension = os.path.splitext(filename)[1]
      yield cv2.imread(path_direction + filename), id_message, extension


def id_training_with_image(message_to_feagi, name_id):
    # Process for ID training
    message_to_feagi = pns.append_sensory_data_for_feagi('training', name_id, message_to_feagi)
    # Process ends for the ID training
    return message_to_feagi
