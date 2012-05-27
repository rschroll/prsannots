# Copyright 2012 Robert Schroll
#
# This file is part of prsannots and is distributed under the terms of
# the LGPL license.  See the file COPYING for full details.

import os
import sys
import subprocess

def open_file(fn):
    """Open file with default handler.  Return True on success."""
    
    try:
        os.startfile(fn)
    except AttributeError:
        command = 'xdg-open'
        if sys.platform.startswith('darwin'):
            command = 'open'
        try:
            subprocess.call((command, fn))
        except OSError:
            return False
    return True
