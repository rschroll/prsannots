# Copyright 2012 Robert Schroll
#
# This file is part of prsannots and is distributed under the terms of
# the LGPL license.  See the file COPYING for full details.

import os
import sys
import glob
import uuid
import shutil
try:
    import cPickle as pickle
except ImportError:
    import pickle
import pyPdf
from prst1 import Reader
from pdfdice import dice, write_pdf

if sys.platform == 'win32':
    CONFIG_DIR = os.path.join(os.getenv('APPDATA'), 'prsannots')
else:
    CONFIG_DIR = os.path.join(os.getenv('XDG_CONFIG_HOME', os.path.join(os.getenv('HOME'), '.config')),
                              'prsannots')
if not os.path.isdir(CONFIG_DIR):
    os.makedirs(CONFIG_DIR)
CONFIG_EXT = '.prc'

class NotMountedError(Exception):
    pass

class Manager(object):
    
    _base_settings = { 'infix': 'annots', 'reader_dir': 'download', 'gs': False}
    _id_file = '.prsannots'
    
    def __init__(self):
        self.settings = {}
        self.library = {}
        self.reader = None
    
    def _ensure_base_settings(self):
        for key in self._base_settings:
            if key not in self.settings:
                self.settings[key] = self._base_settings[key]
    
    def load(self, filename):
        fd = open(filename, 'rb')
        self.settings = pickle.load(fd)
        self.library = pickle.load(fd)
        fd.close()
        self._ensure_base_settings()
        try:
            self.reader = Reader(self.settings['mount'])
        except IOError:  # Check this
            pass
    
    def load_if_mounted(self, filename):
        fd = open(filename, 'rb')
        self.settings = pickle.load(fd)
        id_file = os.path.join(self.settings['mount'], self._id_file)
        if os.path.exists(id_file):
            if self.settings['id']+'\n' in open(id_file, 'r'):
                self.library = pickle.load(fd)
                fd.close()
                self._ensure_base_settings()
                self.reader = Reader(self.settings['mount'])
                return True
        fd.close()
        self.settings = {}
        return False
    
    def load_mounted_reader(self):
        for f in glob.glob(os.path.join(CONFIG_DIR, '*' + CONFIG_EXT)):
            if self.load_if_mounted(f):
                return True
        return False
    
    def save(self):
        fd = open(os.path.join(CONFIG_DIR, self.settings['id'] + CONFIG_EXT), 'wb')
        pickle.dump(self.settings, fd, -1)
        pickle.dump(self.library, fd, -1)
        fd.close()
    
    def update_settings(self, **kw):
        for k,v in kw.items():
            if k in self.settings:
                self.settings[k] = v
    
    def new(self, mount, **kw):
        mount = os.path.abspath(mount)
        if not os.path.ismount(mount):
            raise NotMountedError, "Reader does not appear to be mounted at %s." % mount
        self.settings['mount'] = mount
        self.settings['id'] = str(uuid.uuid4())
        
        fd = open(os.path.join(mount, self._id_file), 'a')
        fd.write(self.settings['id'] + '\n')
        fd.close()
        
        for k,v in self._base_settings.items():
            self.settings[k] = v
        self.update_settings(**kw)
    
    def add_pdf(self, filename, dice_pdf=None, dice_map=None, infix=None, reader_dir=None, gs=None):
        filename = os.path.abspath(filename)
        basename = os.path.basename(filename)
        if infix is None:
            infix = self.settings['infix']
        if reader_dir is None:
            reader_dir = self.settings['reader_dir']
        if gs is None:
            gs = self.settings['gs']
        
        readerfn = os.path.join(self.settings['mount'], reader_dir, basename)
        while os.path.exists(readerfn):
            parts = readerfn.split('.', 2)
            if len(parts) == 2:
                num = 0
            else:
                try:
                    num = int(parts[1]) + 1
                except ValueError:
                    parts = ['.'.join(parts[:-1]), parts[-1]]
                    num = 0
            readerfn = '.'.join((parts[0], str(num), parts[-1]))
        
        if dice_pdf is not None:
            write_pdf(dice_pdf, readerfn, gs)
        else:
            shutil.copy(filename, readerfn)
        
        relfn = readerfn[len(self.settings['mount']) + 1:]  # + 1 for separator
        self.library[relfn] = { 'filename': filename, 'infix': infix, 'annhash': 0, 'dice_map': dice_map }
    
    def add_diced_pdf(self, filename, diceargs, **kw):
        pdf = pyPdf.PdfFileReader(open(filename, 'rb'))
        outpdf, dice_map = dice(pdf, *diceargs)
        self.add_pdf(filename, outpdf, dice_map, **kw)
    
    def sync_pdf(self, filepath):
        libentry = self.library[filepath]
        try:
            book = self.reader[filepath]
        except KeyError:
            # Not annotated
            return False
        if book.hash == libentry['annhash']:
            # No change in annotations
            return False
        
        parts = libentry['filename'].rsplit('.', 1)
        try:
            suffix = parts[1]
        except IndexError:
            suffix = 'pdf'
        annfn = '.'.join((parts[0], libentry['infix'], suffix))
        book.write_annotated_pdf(open(annfn, 'wb'), pyPdf.PdfFileReader(open(libentry['filename'], 'rb')),
                                 libentry['dice_map'])
        libentry['annhash'] = book.hash
        return True
    
    def sync(self):
        count = 0
        for f in self.library:
            if self.sync_pdf(f):
                count += 1
        return count
    
    def delete(self, reader_file=None, orig_file=None, delete_from_reader=False):
        if orig_file is not None:
            if reader_file is not None:
                raise RuntimeError, "Specify only one of reader_file and orig_file."
            orig_file = os.path.abspath(orig_file)
            for k,v in self.library.items():
                if v['filename'] == orig_file:
                    reader_file = k
                    break
        
        if reader_file in self.library:
            if delete_from_reader:
                try:
                    os.unlink(os.path.join(self.settings['mount'], reader_file))
                except OSError:
                    pass
            del(self.library[reader_file])
    
    def clean(self):
        """ Remove files from library that are no longer on the Reader. """
        for filepath in self.library.keys():
            if not os.path.exists(os.path.join(self.settings['mount'], filepath)):
                self.delete(filepath)

## Todo
# Test if file we're adding is already there
# Set title/author when adding files
#  - Can we preserve them in PDFs?
