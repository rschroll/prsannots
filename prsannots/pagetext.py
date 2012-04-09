# Copyright 2012 Robert Schroll
#
# This file is part of prsannots and is distributed under the terms of
# the LGPL license.  See the file COPYING for full details.

from pdfminer.pdfparser import PDFParser, PDFDocument
from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
from pdfminer.layout import LAParams, LTAnon, LTTextBox
from pdfminer.converter import PDFPageAggregator


LIGATURES = {u"\ufb00": "ff",
             u"\ufb01": "fi",
             u"\ufb02": "fl",
             u"\ufb03": "ffi",
             u"\ufb04": "ffl",
            }


class NoSubstringError(Exception):
    pass
class MultipleSubstringError(Exception):
    pass


def get_layouts(fd):
    """ From an open PDF file, get the page layouts (of type
    pdfminer.layout.LTPage).
    """
    
    parser = PDFParser(fd)
    doc = PDFDocument()
    parser.set_document(doc)
    doc.set_parser(parser)
    doc.initialize()
    
    laparams = LAParams()
    rsrcmgr = PDFResourceManager()
    device = PDFPageAggregator(rsrcmgr, laparams=laparams)
    interpreter = PDFPageInterpreter(rsrcmgr, device)
    
    layouts = []
    for page in doc.get_pages():
        interpreter.process_page(page)
        layouts.append(device.get_result())
    return layouts


class PageText(object):
    """ Tracks the characters that make up a page's text, as well as the
    location of each of them.  The characters may be read out by calling
    string or unicode on this object.
    """
    
    def __init__(self, page=None):
        """ Input:  page    A pdfminer.layout.LTPage to load the text from.
        """
        
        self._chars = []
        self._pos = []
        if page is not None:
            self.load(page)
    
    def __str__(self):
        return "".join(self._chars)
    
    def _get_chars(self, char):
        t = char.get_text()
        if isinstance(char, LTAnon):
            if t == ' ':
                return ''
            if t == '\n':
                if self._chars[-1] == '-':
                    del(self._chars[-1])
                    del(self._pos[-1])
                    return ''
                else:
                    return ' '
        return LIGATURES.get(t, t)
    
    def add(self, char, lnum):
        """ Add a character to the page.
        
        Input:  char    The pdfminer.layout.LTChar (or LTAnon) character.
                
                lnum    The line on which the character is.  The only
                        important thing about it is that it changes
                        between lines and is constant within a line.
        """
        
        for c in self._get_chars(char):
            self._chars.append(c)
            self._pos.append((lnum, getattr(char, 'bbox', None)))
    
    def load(self, page):
        """ Add the text from the page (a pdfminer.layout.LTPage).
        """
        
        for box in page._objs:
            if isinstance(box, LTTextBox):
                for l, line in enumerate(box._objs):
                    for char in line._objs:
                        self.add(char, l)
    
    def bboxes(self, start, length):
        """ Get some bounding boxes that contain the specified characters.
        
        Input:  start   The first character to contain.
                
                length  The number of characters to contain.
        
        Returns a list bounding boxes, each one a list of length 4:
        [left, bottom, right, top].
        """
        
        bbox = []
        currline = None
        for l, box in self._pos[start:start+length]:
            if box is None:
                continue
            if l == currline:
                b = bbox[-1]
                b[0] = min(b[0], box[0])
                b[1] = min(b[1], box[1])
                b[2] = max(b[2], box[2])
                b[3] = max(b[3], box[3])
            else:
                bbox.append(list(box))
                currline = l
        return bbox
    
    def box_substring(self, substr, strict=False):
        """ Get some bounding boxes that contain the specified string.
        
        If the specified string does not appear on the page, a
        NoSubstringError is raised.  The behavior when the substring
        appears multiple times depends on strict.
        
        Input:  substr  The string to be contained.
                
                strict  Whether to raise an exception if the string
                        occurs more than once.  If False, the first
                        occurance of substr is used.  If True, a
                        MultipleSubstringError is raised.
        
        Returns a list bounding boxes, each one a list of length 4:
        [left, bottom, right, top].
        """

        s = unicode(self)
        lf = s.find(substr)
        if lf == -1:
            raise NoSubstringError
        if strict:
            rf = s.rfind(substr)
            if rf != lf:
                raise MultipleSubstringError
        return self.bboxes(lf, len(substr))
