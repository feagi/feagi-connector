
from feagi_connector_2 import FeagiAgent
import feagi_rust_py_libs as frpl
import numpy as np
import asyncio
import sys
import cv2
import os
from pathlib import Path
from datetime import datetime

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


async def main():
    input_image_resolution = (128, 128, 3)
    
    # Get video path (same directory as this script)
    video_path = Path(__file__).parent / "../../video_agent/driving.mp4"
    if not video_path.exists():
        print(f"ERROR: Video file not found: {video_path}")
        return

    input_image_properties = frpl.connector_core.data.descriptors.ImageFrameProperties(
        frpl.connector_core.data.descriptors.ImageXYResolution(input_image_resolution[0], input_image_resolution[1]),
        frpl.connector_core.data.descriptors.ColorSpace.Linear,
        frpl.connector_core.data.descriptors.ColorChannelLayout.RGB
    )

    feagi_agent = FeagiAgent() # create agent instance
    feagi_agent.brain_input.image_camera_center.register(0, 1, input_image_properties) # register camera
    
    # Register motor devices we want to receive
    feagi_agent.brain_output.miscellaneous_absolute.register(
        cortical_group=0,
        number_of_channels=10,
        misc_dimensions=frpl.connector_core.data.descriptors.MiscDataDimensions(10, 1, 1)
    )

    # connect to feagi with timeout (using same ports as video_agent)
    print(f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] Connecting to FEAGI...")
    try:
        registration_response = await asyncio.wait_for(
            feagi_agent.feagi.connect_via_zmq("tcp://localhost", input_image_resolution, registration_port=30001, sensory_port=5558),
            timeout=5.0
        )
        print(f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] Connected! Response: {registration_response}")
        
        # Set up motor data callback
        async def on_motor_data(data: bytes):
            timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
            print(f"[{timestamp}] 🎮 [CONNECTOR] Motor data received: {len(data)} bytes")
            
            # Decode using FeagiByteContainer (version 2 container format)
            try:
                # Load data into FeagiByteContainer
                feagi_byte_container = frpl.data_serialization.FeagiByteContainer()
                feagi_byte_container.load_bytes_and_verify(data)
                
                # Extract first structure (should be CorticalMappedXYZPNeuronVoxels)
                mapped_neurons = feagi_byte_container.try_create_new_struct_from_index(0)
                
                # Iterate through all cortical areas
                for cortical_id, (x_coords, y_coords, z_coords, potentials) in mapped_neurons.iter_full():
                    neuron_count = len(x_coords)
                    
                    # Print in requested format: omot00:{x,y,z,p}
                    print(f"[{timestamp}] 🎮 {cortical_id}: {neuron_count} neurons firing")
                    for i in range(min(neuron_count, 10)):  # Show first 10
                        print(f"      x={x_coords[i]}, y={y_coords[i]}, z={z_coords[i]}, p={potentials[i]:.3f}")
                    if neuron_count > 10:
                        print(f"      ... and {neuron_count - 10} more")
                    
            except Exception as e:
                print(f"[{timestamp}] 🎮 [CONNECTOR] Failed to decode motor data: {e}")
                import traceback
                traceback.print_exc()
        
        # Subscribe to motor data
        feagi_agent.feagi._transport.motor_signal.register(on_motor_data)
        feagi_agent.feagi._transport.start_motor_listener()
        print(f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] Motor listener started (waiting for motor commands from FEAGI)")
        
    except asyncio.TimeoutError:
        print(f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] ERROR: Connection timeout. Is FEAGI running on localhost:30001?")
        return

    try:
        # Open video file
        print(f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] Opening video: {video_path}")
        cap = cv2.VideoCapture(str(video_path))
        
        if not cap.isOpened():
            print(f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] ERROR: Could not open video file")
            return
        
        # Get video properties
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        frame_delay = 1.0 / fps if fps > 0 else 1.0 / 30.0  # Default to 30 FPS if unknown
        
        print(f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] Video info: {frame_count} frames at {fps:.2f} FPS")
        print(f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] Streaming frames to FEAGI (Ctrl+C to stop)...")
        
        frame_number = 0
        last_status_time = datetime.now()
        last_status_frame = 0
        
        while True:
            ret, frame = cap.read()
            
            # Loop video when it ends
            if not ret:
                print(f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] End of video reached. Looping...")
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                frame_number = 0
                continue
            
            # Resize frame to target resolution
            resized_frame = cv2.resize(frame, (input_image_resolution[0], input_image_resolution[1]))
            
            # Convert BGR (OpenCV) to RGB
            rgb_frame = cv2.cvtColor(resized_frame, cv2.COLOR_BGR2RGB)
            
            # Convert to numpy array with correct dtype
            image_arr: np.ndarray = rgb_frame.astype(np.uint8)
            
            # Create image frame
            image_frame = frpl.connector_core.data.ImageFrame.new_from_array(
                image_arr, 
                input_image_properties.color_space, 
                frpl.connector_core.data.descriptors.MemoryOrderLayout.WidthsHeightsChannels
            )
            
            # Write to cache
            frame_send_start = datetime.now()
            feagi_agent.brain_input.image_camera_center.write(0, 0, image_frame)
            
            # Send to FEAGI
            await feagi_agent.brain_input_cache.send_brain_input_to_feagi()
            frame_send_duration = (datetime.now() - frame_send_start).total_seconds() * 1000
            
            frame_number += 1
            if frame_number % 30 == 0:  # Print status every 30 frames
                now = datetime.now()
                elapsed = (now - last_status_time).total_seconds()
                frames_sent = frame_number - last_status_frame
                actual_fps = frames_sent / elapsed if elapsed > 0 else 0
                print(f"[{now.strftime('%H:%M:%S.%f')[:-3]}] Sent frame {frame_number}/{frame_count} (send took {frame_send_duration:.2f}ms, actual rate: {actual_fps:.2f} Hz)")
                last_status_time = now
                last_status_frame = frame_number
            
            # Wait to maintain frame rate
            await asyncio.sleep(frame_delay)
            
    except KeyboardInterrupt:
        print(f"\n[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] Stopping video stream...")
    finally:
        # Clean up video capture
        if 'cap' in locals():
            cap.release()
        
        # Clean up connection
        print(f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] Closing connection...")
        if feagi_agent.feagi._transport:
            await feagi_agent.feagi._transport.close()
        print(f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] Connection closed.")


if __name__ == "__main__":
    asyncio.run(main())