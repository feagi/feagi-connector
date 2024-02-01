import RPi.GPIO as GPIO
import time

# Dictionary to keep track of GPIO modes
gpio_modes = {}


# Function to setup GPIO
def setup_gpio(pin, mode):
    global gpio_modes
    GPIO.setup(pin, mode)
    gpio_modes[pin] = mode


def depower_pin():
    global gpio_modes
    for pin in gpio_modes:
        if gpio_modes[pin] == 0:
            GPIO.output(pin, GPIO.LOW)


def power_pin(pin):
    global gpio_modes
    if pin in gpio_modes:
        if gpio_modes[pin] == 0:
            GPIO.output(pin, GPIO.HIGH)


def get_available_gpios():
    available_gpios = []
    for pin in range(2, 28):  # The latest Raspberry Pi, the Raspberry Pi 5, features 28 GPIO pins.
        try:
            # GPIO.setup(pin, GPIO.IN)
            setup_gpio(pin, GPIO.OUT)
            available_gpios.append(pin)
            # GPIO.cleanup(pin)
        except ValueError:
            pass
    return available_gpios


# Function to check GPIO mode
def check_gpio_mode(pin):
    global gpio_modes
    if pin in gpio_modes:
        return "Output" if gpio_modes[pin] == GPIO.OUT else "Input"
    else:
        return "Not configured"


def configured_board_by_config(capabilities):
    if 'GPIO' in capabilities:
        if 'port' in capabilities['GPIO']:
            for pin in capabilities['GPIO']['port']:
                GPIO.setup(int(pin), capabilities['GPIO']['port'][pin])
                gpio_modes[int(pin)] = capabilities['GPIO']['port'][pin]
    print(gpio_modes)


def clear_gpio():
    GPIO.cleanup()


GPIO.setmode(GPIO.BCM)  # Using Broadcom pin numbering
# gpios = get_available_gpios()
# print(gpio_modes)
# GPIO.cleanup()
