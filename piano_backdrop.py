#!/usr/bin/python

import spi_lights as lights
import time
import socket
import colorsys
from threading import Thread

UDP_IP = "0.0.0.0"
UDP_PORT = 5005

MIN_KEY = 28
MAX_KEY = 100

MIN_LED = 173
MAX_LED = 30

NUM_KEYS = 128
_piano_keys = [0] * NUM_KEYS
_piano_keys_fast = [0] * NUM_KEYS

_t_last_key_release = 0

_current_colour = [0, 0, 0]
_target_colour = [0, 0, 0]

# Mixing factor from current to target colours:
ALPHA = 0.97
# Brightness decay factor:
BETA = 0.996
# Fast decay to smooth out changes:
GAMMA_INC = 0.8
GAMMA_DEC = 0.92

# Interval between notes, in seconds, after which colour jumps not fades:
NOTE_INTERVAL = 0.1


#####
# Listening Thread:
#####

sock = socket.socket(socket.AF_INET, # Internet
                     socket.SOCK_DGRAM) # UDP
sock.bind((UDP_IP, UDP_PORT))


def listen_udp():
    global _target_colour, _t_last_key_release, _current_colour  # _target_hue
    while True:
        # Listen for a new key update:
        data, addr = sock.recvfrom(1024) # buffer size is 1024 bytes
        print "received message:", data
        data = data.split(",")
        if len(data) == 3:
            # Note, Note Velocity, Hue
            note, velocity, hsv_h = data
            note = int(note)
            velocity = int(velocity)
            hsv_h = float(hsv_h) % 1
            _target_colour = list(colorsys.hsv_to_rgb(hsv_h, 1, 1))
            if velocity == 0:
                _t_last_key_release = lights.get_time()
            elif lights.get_time() - _t_last_key_release > NOTE_INTERVAL and sum(_piano_keys) == 0:
                _current_colour = _target_colour
        elif len(data) == 2:
            # Note, Note Velocity
            note, velocity = map(int, data)
            if velocity == 0:
                _t_last_key_release = lights.get_time()
        else:
            # Unknown; ignore!
            continue
        _piano_keys[note] = velocity
        

udp_thread = Thread(target=listen_udp)
udp_thread.daemon = True
udp_thread.start()


#####
# Light controller code:
#####

def _lerp(x, i_min, i_max, o_min, o_max):
    """Linear interpolation between input, i, and output, o."""
    f = float(x - i_min) / (i_max - i_min)
    if f < 0:
        f = 0
    elif f > 1:
        f = 1
    y = o_min + (f * (o_max - o_min))
    return y


def piano_to_led(p):
    """Convert piano key to correct LED number."""
    return int(_lerp(p, MIN_KEY, MAX_KEY, MIN_LED, MAX_LED))


def velocity_to_brightness(vel):
    """Convert MIDI key velocity to HSV value 'brightness'."""
    return _lerp(vel, 20, 110, 0, 1)


def update_lights():
    """Generator to contol light colours."""
    global _current_colour
    t_prev = lights.get_time()
    for t in lights.time_gen():
        time.sleep(0.001)
        dt = t - t_prev
        t_prev = t
        _current_colour[0] = ALPHA * _current_colour[0] + (1 - ALPHA) * _target_colour[0]
        _current_colour[1] = ALPHA * _current_colour[1] + (1 - ALPHA) * _target_colour[1]
        _current_colour[2] = ALPHA * _current_colour[2] + (1 - ALPHA) * _target_colour[2]
        # Update all the lights:
        for i in range(NUM_KEYS):
            j = piano_to_led(i)

            _piano_keys[i] *= BETA
            if _piano_keys_fast[i] >= _piano_keys[i]:
                _piano_keys_fast[i] = GAMMA_DEC * _piano_keys_fast[i] + (1 - GAMMA_DEC) * _piano_keys[i]
            else:
                _piano_keys_fast[i] = GAMMA_INC * _piano_keys_fast[i] + (1 - GAMMA_INC) * _piano_keys[i]

            hsv_v = velocity_to_brightness(_piano_keys_fast[i])
            # colour = colorsys.hsv_to_rgb((2.0*j/lights.NUM_LEDS - 0.19) % 1, 1, hsv_v)
            colour = map(lambda x: x*hsv_v, _current_colour)
            if _piano_keys_fast[i] > 0:
                # Set the LED to the colour:
                lights.set_led(j, colour, 31)	
                lights.set_led(j+1, colour, 31)	
            else:
                # Turn off the LED:
                lights.set_led(j, (0,0,0), 0)
                lights.set_led(j+1, (0,0,0), 0)
        yield


if __name__ == "__main__":
    lights.run_loop(update_lights)
