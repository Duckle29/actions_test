#!/usr/bin/env python3

import os
import fileinput
import tempfile
from pathlib import Path

import re
import hashlib
import json

QMK_VID = 0x03A8

VID_regex = re.compile(r"""^#define\s+VENDOR_ID\s+(0x[0-9a-f]{4})$""", flags=re.IGNORECASE)
PID_regex = re.compile(r"""^#define\s+PRODUCT_ID\s+(0x[0-9a-f]{4})$""", flags=re.IGNORECASE)


def get_vid_pid(config_file):
    vid = None
    pid = None
    with open(config_file) as cf:
        for line in cf:
            if vid is None:
                vid = re.match(VID_regex, line)
            if pid is None:
                pid = re.match(PID_regex, line)
            if vid is not None and pid is not None:
                break
    return vid, pid


def check_collision(pid, data):
    """Return true of the PID collides with an already assigned PID"""

    if pid in data['pids']:
        return True
    else:
        return False


def calculate_pid(config_path, data, offset=0, max_tries=3):
    if offset >= max_tries:
        raise RecursionError(offset)
    m = hashlib.sha1()
    m.update(config_path.encode('utf-8'))
    pid = m.hexdigest()[offset:offset+4].upper()

    if check_collision(pid, data):
        return calculate_pid(config_path, data, offset+1, max_tries)
    else:
        return pid


def init():
    # Check if json file exists
    if not Path(os.environ['PIDS_JSON_PATH']).is_file():
        with open(os.environ['PIDS_JSON_PATH'], 'w') as jfile:
            json.dump({"pids": {}}, jfile)


init()


def atomic_dump(data, json_file):
    with tempfile.NamedTemporaryFile(
            'w', dir=Path(json_file).parents[0], delete=False) as tf:
        json.dump(data, tf)
    os.replace(tf.name, json_file)


VID, PID = get_vid_pid(os.environ['KEYBOARD_CONFIG_PATH'])
if int(VID.group(1), 16) != QMK_VID:

    print("Keyboard does not use QMK VID (0x{:04X} != 0x{:04X})".format(int(VID.group(1), 16), QMK_VID))
    exit(0)
else:
    with open(os.environ['PIDS_JSON_PATH'], 'r') as json_file:
        data = json.load(json_file)
        path = str(Path(os.environ['KEYBOARD_CONFIG_PATH']).parents[0])

        if path in data['pids'].values():
            print("Keyboard already assigned a PID")
            exit(0)
        else:
            try:
                pid = calculate_pid(path, data)
            except RecursionError as e:
                print("Too many PID collisions ({}). Aborting".format(e))
                exit(1)
                
            print("Assigned PID 0x{}".format(pid))
            for line in fileinput.input(os.environ['KEYBOARD_CONFIG_PATH'], inplace=True):
                print(line.replace(PID.group(0), "{}{}".format(PID.group(0)[:-4], pid)), end='')

        data["pids"][pid] = path
    atomic_dump(data, os.environ['PIDS_JSON_PATH'])


