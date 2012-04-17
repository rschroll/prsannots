# Copyright 2012 Robert Schroll
#
# This file is part of prsannots and is distributed under the terms of
# the LGPL license.  See the file COPYING for full details.

import os
import sys
import glob
import uuid
import shutil
import subprocess
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

def test_gs():
    """ Test if Ghostscript is installed with the pdfwrite device. """
    try:
        output = subprocess.check_output(['gs', '-h'])
    except (OSError, subprocess.CallProcessError):
        return False
    if output.find('pdfwrite') == -1:
        return False
    return True

class NotMountedError(Exception):
    pass

class Manager(object):
    """ Tracks a set of files on the eReader, so that annotated files can
    be retrieved.
    """
    
    _base_settings = { 'infix': 'annot', 'reader_dir': 'download', 'gs': None}
    _id_file = '.prsannots'
    
    def __init__(self):
        self.settings = {}
        self.library = {}
        self.reader = None
        self._mount = None
    
    def _ensure_base_settings(self):
        for key in self._base_settings:
            if key not in self.settings:
                self.settings[key] = self._base_settings[key]
    
    @property
    def mount(self):
        """ The mount point is usually stored in self.settings, but we
        want to be able to mount somewhere else if needed.
        """
        
        if self._mount is not None:
            return self._mount
        return self.settings.get('mount', None)
    
    @mount.setter
    def mount(self, value):
        """ Set to None to use self.settings['mount']. """
        self._mount = value
    
    def update_mount_setting(self):
        """ Update the mount point in the settings to the current mount
        point.  Be sure to call save() sometime after this method.
        """
        
        if self.mount is not None:  # Before loading
            self.settings['mount'] = self.mount
            self.mount = None
    
    def load(self, filename):
        """ Load the configuration file specified by filename.  Note that
        this method does not require the reader to be mounted.  The only
        indication that it isn't will be that self.reader = None.
        """
        
        fd = open(filename, 'rb')
        self.settings = pickle.load(fd)
        self.library = pickle.load(fd)
        fd.close()
        self._ensure_base_settings()
        try:
            self.reader = Reader(self.mount)
        except IOError:  # Check this
            pass
    
    def load_if_mounted(self, filename):
        """ Load the configuration file specified by filename if the
        corresponding reader is mounted.  Return True if successful,
        False otherwise.
        """
        
        fd = open(filename, 'rb')
        self.settings = pickle.load(fd)
        id_file = os.path.join(self.mount, self._id_file)
        if os.path.exists(id_file):
            if self.settings['id']+'\n' in open(id_file, 'r'):
                self.library = pickle.load(fd)
                fd.close()
                self._ensure_base_settings()
                self.reader = Reader(self.mount)
                return True
        fd.close()
        self.settings = {}
        return False
    
    def load_mounted_reader(self):
        """ Load the reader that is mounted, if a configuration file is
        found for it.  Returns True if a reader was found, False otherwise.
        
        Note that if multiple readers are mounted, only the "first" one
        will be loaded.  Which one this is is deterministic, but will
        seem random to the user.
        """
        
        for f in glob.glob(os.path.join(CONFIG_DIR, '*' + CONFIG_EXT)):
            if self.load_if_mounted(f):
                return True
        return False
    
    def load_mount(self, mount):
        """ Load the reader at mount, if there is a configuration file for
        it, even if that file suggests a different mount point.  Returns
        True if successful, False otherwise.
        """
        
        mount = os.path.abspath(mount)
        self.mount = mount
        try:
            for line in open(os.path.join(mount, self._id_file), 'r').read().splitlines():
                fn = os.path.join(CONFIG_DIR, line + CONFIG_EXT)
                if os.path.exists(fn):
                    fd = open(fn, 'rb')
                    self.settings = pickle.load(fd)
                    self.library = pickle.load(fd)
                    fd.close()
                    self._ensure_base_settings()
                    self.reader = Reader(self.mount)
                    if self.settings['mount'] == self.mount:
                        self.mount = None  # Use self.settings
                    return True
        except IOError:
            pass
        self.mount = None
        return False
    
    def save(self):
        """ Save the configuration. """
        
        fd = open(os.path.join(CONFIG_DIR, self.settings['id'] + CONFIG_EXT), 'wb')
        pickle.dump(self.settings, fd, -1)
        pickle.dump(self.library, fd, -1)
        fd.close()
    
    def update_settings(self, **kw):
        """ Update the global settings for the manager.
        
        Be sure to call save() sometime after this method.
        """
        
        for k,v in kw.items():
            if k in self.settings:
                self.settings[k] = v
    
    def new(self, mount, **kw):
        """ Create a new configuration.  mount is where the reader is
        mounted.  Other keyword arguments specify global settings.
        
        Be sure to call save() sometime after this method.
        """
        
        mount = os.path.abspath(mount)
        if not os.path.ismount(mount):
            raise NotMountedError, "Reader does not appear to be mounted at %s." % mount
        self.settings['mount'] = mount
        self.settings['id'] = str(uuid.uuid4())
        
        fd = open(os.path.join(mount, self._id_file), 'a')
        fd.write(self.settings['id'] + '\n')
        fd.close()
        
        if self._base_settings['gs'] is None:
            self._base_settings['gs'] = test_gs()
        for k,v in self._base_settings.items():
            self.settings[k] = v
        self.update_settings(**kw)
    
    def add_pdf(self, filename, dice_pdf=None, dice_map=None, title=None,
                author=None, infix=None, reader_dir=None, gs=None):
        """ Add a PDF file to the reader, to be managed by this manager.
        
        Inputs: filename    The location on the computer of the PDF file.
                
                dice_pdf    A pyPdf.PdfFileWriter with the diced PDF file
                            to be put on the reader.  If None, then
                            filename is copied to the reader.
                
                dice_map    The dice map describing how the original PDF
                            was cut up for the reader.  None indicates
                            no dicing occured.
                
                title       The to be given to the PDF file put on the
                            reader.  If None, use the original file's
                            title, if it exists.
                
                author      The author of the PDF file put on the reader.
                            If None, use the original file's author,
                            if it exists.
                
                infix       The annotated PDF will be written back to the
                            filesystem with the name filename.infix.pdf.
                            If None, use the global settings.
                
                reader_dir  The directory on the reader to place the PDF
                            file.  If None, use the global settings.
                
                gs          A Boolean flag on whether to run the diced
                            PDF through Ghostscript.  If None, use the
                            global settings.
        
        Be sure to call save() sometime after this method.
        """
        
        filename = os.path.abspath(filename)
        if not os.path.exists(filename):
            raise IOError, "File %s does not exist." % filename
        basename = os.path.basename(filename)
        if infix is None:
            infix = self.settings['infix']
        if reader_dir is None:
            reader_dir = self.settings['reader_dir']
        if gs is None:
            gs = self.settings['gs']
        
        readerfn = os.path.join(self.mount, reader_dir, basename)
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
        
        orig_pdf = pyPdf.PdfFileReader(open(filename, 'rb'))
        # If we're changing the title or author, we need to rewrite the
        # whole PDF file.
        if dice_pdf is None and (title is not None or author is not None):
            dice_pdf = pyPdf.PdfFileWriter()
            for page in orig_pdf.pages:
                dice_pdf.addPage(page)
        
        if dice_pdf is not None:
            info_dict = {}
            if title is not None:
                info_dict[pyPdf.generic.NameObject('/Title')] = pyPdf.generic.TextStringObject(title)
            else:
                try:
                    info_dict[pyPdf.generic.NameObject('/Title')] = orig_pdf.documentInfo['/Title']
                except KeyError:
                    pass
            if author is not None:
                info_dict[pyPdf.generic.NameObject('/Author')] = pyPdf.generic.TextStringObject(author)
            else:
                try:
                    info_dict[pyPdf.generic.NameObject('/Author')] = orig_pdf.documentInfo['/Author']
                except KeyError:
                    pass
            
            info = dice_pdf._info.getObject()
            info.update(info_dict)
            write_pdf(dice_pdf, readerfn, gs)
        else:
            shutil.copy(filename, readerfn)
        
        relfn = readerfn[len(self.mount) + 1:]  # + 1 for separator
        self.library[relfn] = { 'filename': filename, 'infix': infix, 'annhash': 0, 'dice_map': dice_map }
    
    def add_diced_pdf(self, filename, diceargs, **kw):
        """ Add a PDF file to the reader, diced as specified.
        
        Inputs: filename    The location on the computer of the PDF file.
                
                diceargs    The arguments to be passed to pdfdice.dice().
                            As of this writing, a tuple of the form
                            (ncols, nrows, [overlap]).  See pdfdice
                            documentation for more details.
                
                Additional keyword arguments are the same as for add_pdf().
        
        Be sure to call save() sometime after this method.
        """
        
        pdf = pyPdf.PdfFileReader(open(filename, 'rb'))
        outpdf, dice_map = dice(pdf, *diceargs)
        self.add_pdf(filename, outpdf, dice_map, **kw)
    
    def sync_pdf(self, filepath):
        """ Create an up-to-date annotated PDf for the specified file.
        
        This method short-circuits if the current anotated PDF is up-to-date.
        
        Input:  filepath    The location of the specified PDF file on the
                            reader, relative to the mount point.
        
        Output: A Boolean indicating whether the annotated PDF was
                updated or not.  If True, be sure to call save()
                sometime in the future.
        """
        
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
        """ Sync all PDF files tracked my this manager.
        
        Returns the number of updated annotated PDF files.  Be sure to
        call save() in the future if this number is > 0.
        """
        
        count = 0
        for f in self.library:
            if self.sync_pdf(f):
                count += 1
        return count
    
    def delete(self, reader_file=None, orig_file=None, delete_from_reader=False):
        """ Remove a file from the manager, and optionally delete it from the reader.
        
        Inputs: reader_file         The path to the file on the reader,
                                    relative to the mount point.
                
                orig_file           The path to the file on the computer.
                                    Note that only one of reader_file
                                    and orig_file should be specified.
                
                delete_from_reader  Whether to delete the PDF file from
                                    the reader.
        
        Output: A Boolean indicating whether the file was removed from the manager.
        
        Be sure to call save() sometime after this method.
        """
        
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
                    os.unlink(os.path.join(self.mount, reader_file))
                except OSError:
                    pass
            del(self.library[reader_file])
            return True
        
        return False
    
    def clean(self):
        """ Remove files from the manager that are no longer on the Reader. """
        for filepath in self.library.keys():
            if not os.path.exists(os.path.join(self.mount, filepath)):
                self.delete(filepath)

## Todo
# Test if file we're adding is already there
