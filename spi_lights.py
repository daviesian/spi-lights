#!/usr/bin/python

# To get SPI1 output working, make sure the following two lines are in /boot/config.txt:
#
# dtparam=spi=on
# dtoverlay=spi1-1cs

import spidev
import time
import colorsys
import anvil.server
import threading

NUM_LEDS = 288
SPI_SPEED_HZ = 8000000

REGIONS = list(range(0,31) + range(62,85) + range(110,178) + range(212,233) + range(255,288))

t = 0

spi = spidev.SpiDev()

_data_array  = [0x00] * 4  # Reset indicator
_data_array += [0xE0, 0x00, 0x00, 0x00] * NUM_LEDS  # [Brightness 0xE0 to 0xFF, Blue, Green, Red]
_data_array += [0x00] * ((NUM_LEDS / 16) + 1)  # Empty padding


def _index(led):
    # There are 4 reset bytes before the data bytes, and 4 bytes per LED:
    return 4 + (led * 4)


def _bounds_check_rgb(r, g, b, brightness):
    # Bounds check brightness, to within 0xE0 and 0xFF
    brightness = 0xE0 | (brightness & 0x1F)
    # Set the colours, with range checking:
    r = int(r * 255) & 0xFF
    g = int(g * 255) & 0xFF
    b = int(b * 255) & 0xFF
    return r, g, b, brightness


def init():
    # Open an SPI connection:        
    spi.close()
    spi.open(1, 0)
    spi.max_speed_hz = SPI_SPEED_HZ



def set_led(i, (r, g, b), brightness=1):
    global _data_array, NUM_LEDS
    # Bounds check LED access, print warning and wrap around:
    if i < 0:
        print "WARN: Attempted to assign to a negative index!"
        while i < 0:
            i += NUM_LEDS
    if i >= NUM_LEDS:
        print "WARN: Attempted to access LED beyond end of strip!"
        i = i % NUM_LEDS
    # Enforce limits on LED values:
    r, g, b, brightness = _bounds_check_rgb(r, g, b, brightness)
    # Update the LED in the array:
    index = _index(i)
    _data_array[index] = brightness
    _data_array[index + 1] = b
    _data_array[index + 2] = g
    _data_array[index + 3] = r


def set_all((r, g, b)=(0, 0, 0), brightness=1):
    global _data_array, NUM_LEDS
    # Enforce limits on LED values:
    r, g, b, brightness = _bounds_check_rgb(r, g, b, brightness)
    # Work out where in the data array to update:   
    i_0 = _index(0)
    i_max = _index(NUM_LEDS)
    # Loop through the right bit of the array, updating a 4 bytes per LED:
    for i in range(i_0, i_max, 4):
        _data_array[i] = brightness
        _data_array[i + 1] = b
        _data_array[i + 2] = g
        _data_array[i + 3] = r


def clear_all(rgb=(0, 0, 0), brightness=0):
    set_all(rgb, brightness)


def get_time():
    global t
    return t


def time_gen():
    while True:
        yield get_time()


def _write_out():
    spi.writebytes(_data_array)


def _set_NUM_LEDS(N):
    global NUM_LEDS
    NUM_LEDS = N

def run_loop(loop_func):
    global t
    try:
        init()
        # Initial conditions:
        t_0 = time.time()
        gen = loop_func()
        # Loop forever!
        while True:
            dt = time.time() - (t + t_0)
            t = t + dt
            next(gen)
            _write_out()
    except KeyboardInterrupt:
        pass
    finally:
        print
        print "Cleaning Up!"
        clear_all()
        _write_out()
        spi.close()

def _default_loop():
    for t in time_gen():
        colour = colorsys.hsv_to_rgb((t / 100) % 1, 1, 1)
        for i in REGIONS: #range(NUM_LEDS):
#            set_led(i, colour, 1)
            set_led(i, (0.1,0,0), 1)
        yield

_current_red = 0.5
_current_green = 0.5
_current_blue = 0.5
_current_brightness = 0.0

_target_red = _current_red
_target_green = _current_green
_target_blue = _current_blue
_target_brightness = _current_brightness

EPSILON = 0.001 

def _near(x, y):
    return abs(x-y) < EPSILON


def _write_regions():
    for i in REGIONS:
        set_led(i, (_current_red, _current_green, _current_blue), int(_current_brightness*31+0.5))
        _write_out()
        time.sleep(0.01)

class DecayThread(threading.Thread):
    def run(self):
        global _current_red, _current_green, _current_blue, _current_brightness

	ALPHA = 0.50
        DT = 0.1

	d_alpha = ALPHA * DT
        while True:
            new_red = d_alpha * _target_red + (1 - d_alpha) * _current_red
            new_green = d_alpha * _target_green + (1 - d_alpha) * _current_green
            new_blue = d_alpha * _target_blue + (1 - d_alpha) * _current_blue
            new_brightness = _target_brightness # d_alpha * _target_brightness + (1 - d_alpha) * _current_brightness
    
            _current_red = new_red
            _current_green = new_green
            _current_blue = new_blue
            _current_brightness = new_brightness

#            print(int(_current_red*255), int(_current_green*255), int(_current_blue*255))

            if _near(new_red, _target_red) and _near(new_green, _target_green) and _near(new_blue, _target_blue) and _near(new_brightness, _target_brightness):
                pass
            else:
                _write_regions()

            time.sleep(DT)

@anvil.server.callable
def set_color(r,g,b,brightness):
    global _current_red, _current_green, _current_blue, _current_brightness
#    print("Set!", r, g, b, brightness)
    _current_red  = r / 255.0
    _current_green = g / 255.0
    _current_blue = b / 255.0
    _current_brightness = brightness / 31.0

    _write_regions()

@anvil.server.callable
def get_color():
    return (int(_current_red*256+0.5), int(_current_green*255+0.5), int(_current_blue*255+0.5), int(_current_brightness*31+0.5))

def run_anvil_server():
    anvil.server.connect("35OXD7FUTW6BYQ52PTRFX6KP-QCENAL7FI4KXXHMU")

    init()

#    t = DecayThread()
#    t.daemon = True
#    t.start()

    try:
        anvil.server.wait_forever()
    except KeyboardInterrupt:
        pass
    finally:
        print
        print "Cleaning Up!"
        clear_all()
        _write_out()
        spi.close()


if __name__ == "__main__":
    
#    run_loop(_default_loop)
    run_anvil_server()
       
