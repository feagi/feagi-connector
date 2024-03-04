import threading
import serial

# Global variable for received data
received_data = ""


# Function to handle receiving data
def read_from_port(ser):
    global received_data
    while True:
        reading = ser.readline().decode('utf-8').rstrip()
        received_data = reading
        print(reading)  # Or handle received data as needed


# Function to handle sending data
def write_to_port(ser):
    while True:
        # Replace 'your_data_to_send' with the actual data you want to send
        data_to_send = input("Enter data to send: ")  # Or any other method to get data
        ser.write(data_to_send.encode())


# Main function to setup serial connection and threads
def main():
    ser = serial.Serial('/dev/ttyACM0', 115200)
    thread_read = threading.Thread(target=read_from_port, args=(ser,))
    thread_write = threading.Thread(target=write_to_port, args=(ser,))

    thread_read.start()
    thread_write.start()

    thread_read.join()
    thread_write.join()


if __name__ == "__main__":
    main()
