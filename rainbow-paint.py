#!/usr/bin/env python3
# Name: Rainbow Paint
# Author: toejough
#
# Description: Paints a color based on angle, with a larger slice by closeness to the center, surrounded by a rainbow starting and stopping at the opposite hue.

try:
    from neopixel import *
except ImportError:
    from rpi_ws281x import *

from colorFunctions import colorBlend, isDiff
from timeit import default_timer as timer
from sisyphusState import SisyphusState

def clamp(t):
    if t > 1.0:
        return 1.0
    elif t < 0:
        return 0
    else:
        return t

def wheel(pos):
    """Generate rainbow colors across 0-1.0 positions."""
    pos = clamp(pos)
    pos = int(pos * (256*3 - 1))
    if pos < 256: # green -> red
        r = pos
        g = 255 - pos
        b = 0
    elif pos < 256*2: # red -> blue 
        pos -= 256
        r = 255 - pos
        g = 0
        b = pos
    else: # blue -> green
        pos -= 256 * 2
        r = 0 
        g = pos 
        b = 255 - pos
    g = int(g / 2) # green is perceived to be 2x as bright with these LED's
    return Color(r, g, b)

last_update_s = 0
time_hue = 0
angle_hue = 0
was_moving = True

def init(strip, table_values):
    global last_update_s
    last_update_s = timer()

def perc_of_target(pos, target, led_count):
    max_distance = 90
    led_degrees = pos * 360 / led_count 
    distance_from_target = abs(led_degrees - target)
    # correct for circle. 340 is actually only 20 off. 
    distance_from_target = min(360 - distance_from_target, distance_from_target)
    # adjust for all the math maybe screwing something up slightly - we can only be up to the max distance away.
    distance_from_target = min(max_distance, distance_from_target)
    perc_of_max = distance_from_target / max_distance
    return 1 - perc_of_max


def update(strip, table_values):
    global last_update_s, time_hue, angle_hue, was_moving
    try:

        color1 = table_values["primary_color"]
        w1 = (color1 >> 24) & 0xFF;
        # r1 = (color1 >> 16) & 0xFF;
        # g1 = (color1 >> 8) & 0xFF;
        # b1 = color1 & 0xFF;

        # cycle_time = int(r1)
        cycle_time = 45

        degrees = (table_values["theta"] * 57.2958) %360

        led_count = strip.numPixels()

        if table_values["state"] in [SisyphusState.SLEEPING]:
            faded = Color(0, 0, 0, 128)
            for x in range(0, led_count):
                current = strip.getPixelColor(x)
                new_color = colorBlend(current, faded, 0.05)
                strip.setPixelColor(x, new_color)
                if isDiff(current, new_color):
                    table_values["do_update"] = True
            return

        if table_values["state"] in [SisyphusState.HOMING, SisyphusState.PLAYING]:
            angle_hue = clamp(degrees/360)
            was_moving = True
        else:
            # optimization to avoid calling timer repeatedly during movement
            now = timer()
            if was_moving:
                was_moving = False
                duration_s = 0
            else:
                duration_s = now - last_update_s
            duration_s %= cycle_time
            time_hue += duration_s / cycle_time 
            time_hue %= 1
            last_update_s = now # update start to be when we last were moving
        hue = (angle_hue + time_hue) % 1

        ball_color = wheel(hue) 
        # second color is 180 degrees from the main color
        second_color = wheel((hue + 0.5) % 1) 

        # spread out the pixel color based on rho
        rho = table_values["rho"]

        # always at least 1/8, up to 1/2
        min_percent_LED = 0.125
        max_percent_LED = 0.5
        percent_LED = min_percent_LED + (1 - rho) * (max_percent_LED - min_percent_LED)
        spread_degrees = percent_LED * 360
        spread_l = degrees - spread_degrees / 2
        spread_r = degrees + spread_degrees / 2
        secondary_spread_degrees = min_percent_LED * 360
        secondary_led_offset = int(secondary_spread_degrees * led_count / 360)

        start = int( (spread_l * led_count) / 360 )
        end = int( (spread_r * led_count) / 360 ) + 1
        if (end < start):
            end += led_count
        
        # before the main color, use the secondary color on either side
        for x in range(start + led_count - secondary_led_offset, start + led_count):
            pos = x % led_count
            strip.setPixelColor(pos, second_color)

        for x in range(end, end+secondary_led_offset):
            pos = x % led_count
            strip.setPixelColor(pos, second_color)

        # use the main color in the spread range
        for x in range(start, end):
            pos = x % led_count
            strip.setPixelColor(pos, ball_color)

        # rainbow the rest of the range with the wheel from secondary -> secondary 
        rainbow_start = end + secondary_led_offset
        rainbow_end = start - secondary_led_offset

        if rainbow_start > rainbow_end:
            rainbow_end += led_count
        starting_hue = hue + 0.5
        for x in range(rainbow_start, rainbow_end):
            rainbow_length = rainbow_end - rainbow_start
            rainbow_pos = x - rainbow_start
            pos = x % led_count
            rainbow_hue = starting_hue + float(rainbow_pos) / rainbow_length
            rainbow_color = wheel(rainbow_hue % 1)
            strip.setPixelColor(pos, rainbow_color)

        # tell the system to do a color update
        table_values["do_update"] = True
    except Exception as e:
        print(e)
