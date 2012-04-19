# Copyright 2012 Robert Schroll
#
# This file is part of prsannots and is distributed under the terms of
# the LGPL license.  See the file COPYING for full details.

import os
from xml.dom import minidom
import svglib
from StringIO import StringIO
import hashlib
import pyPdf
from pagetext import PageText, get_layouts, NoSubstringError, MultipleSubstringError
from pdfannotation import highlight_annotation, text_annotation, add_annotation

HIGHLIGHT, HIGHLIGHT_TEXT, HIGHLIGHT_DRAWING = 10, 11, 12

def intersection(a, b):
    return (max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3]))

class OneToOneMap(object):
    
    def __init__(self, npages):
        self.npages = npages
    
    def __len__(self):
        return self.npages
    
    def __getitem__(self, num):
        if num < 0 or num >= self.npages:
            raise IndexError
        return (num, None)

class Reader(object):
    
    def __init__(self, path):
        self.path = path
    
    @property
    def books(self):
        if not hasattr(self, '_books'):
            self._books = self._get_books()
        return self._books
    
    def _get_books(self):
        raise NotImplementedError, "Subclasses must implement a _get_books() method."
    
    def __getitem__(self, filepath):
        for b in self.books:
            if b.file == filepath:
                return b
        raise KeyError


class Book(object):
    """ Encapsulate a book stored on the ereader.
    """
    
    def __init__(self, reader, id_, title, filepath, thumbnail):
        self.reader = reader
        self.id = id_
        self.title = title
        self.file = filepath
        self.thumbnail = thumbnail
        self._layouts = None
        self._page_texts = {}
    
    @property
    def annotations(self):
        if not hasattr(self, '_annotations'):
            self._annotations = self._get_annotations()
            self._annotations.sort(lambda a,b: cmp(a.page, b.page))
        return self._annotations
    
    def _get_annotations(self):
        raise NotImplementedError, "Subclasses must implement a _get_annotations() method."
    
    @property
    def hash(self):
        if not hasattr(self, '_hash'):
            hashes = [ann.hash for ann in self.annotations]
            self._hash = hashlib.md5(''.join(hashes)).digest()
        return self._hash
    
    @property
    def pdf(self):
        return pyPdf.PdfFileReader(open(os.path.join(self.reader.path, self.file), 'r'))
    
    def pdf_layout(self, page):
        if self._layouts is None:
            self._layouts = get_layouts(open(os.path.join(self.reader.path, self.file), 'r'))
        return self._layouts[page]
    
    def page_text(self, page):
        if page not in self._page_texts:
            self._page_texts[page] = PageText(self.pdf_layout(page))
        return self._page_texts[page]
    
    def write_annotated_pdf(self, outfd, pdf=None, dice_map=None):
        if pdf is None:
            pdf = self.pdf
        if dice_map is None:
            dice_map = OneToOneMap(len(self.pdf.pages))
        
        outpdf = pyPdf.PdfFileWriter()
        j = k = 0
        for i, page in enumerate(pdf.pages):
            while j < len(dice_map) and dice_map[j][0] == i:
                while k < len(self.annotations) and self.annotations[k].page == j:
                    self.annotations[k].write_to_pdf(page, outpdf, dice_map[j][1])
                    k += 1
                j += 1
            outpdf.addPage(page)
        outpdf.write(outfd)


class Freehand(object):
    """ Encapsulate a freehand annotation to a Book.
    """
    
    def __init__(self, book, page, svg_file, crop_left, crop_top, crop_right, crop_bottom, orientation):
        self.book = book
        self.page = int(page)
        self.svg_file = svg_file
        self.crop = map(float, (crop_left, crop_top, crop_right, crop_bottom))
        self.orientation = int(orientation)
    
    @property
    def svg(self):
        if not hasattr(self, '_svg'):
            doc = minidom.parse(os.path.join(self.book.reader.path, self.svg_file))
            drawing = doc.getElementsByTagNameNS('http://www.sony.com/notepad', 'drawing')[0]
            self._svg = doc.getElementsByTagNameNS('http://www.w3.org/2000/svg','svg')[0]
            for attr in ('width', 'height'):
                self._svg.setAttribute(attr, drawing.getAttribute(attr))
        return self._svg
    
    @property
    def hash(self):
        return hashlib.md5(str(self.crop) + str(self.orientation) + self.svg.toxml('utf-8')).digest()
    
    @property
    def pdf(self):
        renderer = svglib.SvgRenderer()
        renderer.render(self.svg)
        drawing = renderer.finish()
        
        pdfstring = svglib.renderPDF.drawToString(drawing)
        pdfdoc = pyPdf.PdfFileReader(StringIO(pdfstring))
        return pdfdoc.getPage(0)
    
    def write_to_pdf(self, page, outpdf, crop=None):
        if crop is None:
            # The reader displays the intersection of the cropBox and the mediaBox.
            crop = intersection(page.cropBox[:], page.mediaBox[:])
        page.mergeScaledTranslatedPage(self.pdf, *self.scale_offset(crop))
    
    def scale_offset(self, pdfcrop):
        svgw, svgh = self.crop[2:]
        svgcw, svgch = [float(self.svg.getAttribute(x)) for x in ('width', 'height')]
        cropx0, cropy0, cropx1, cropy1 = map(float, pdfcrop)
        cropw = cropx1 - cropx0
        croph = cropy1 - cropy0
        if croph/cropw > svgh/svgw:  # Tall and skinny
            scale = croph/svgh
        else:
            scale = cropw/svgw
        scale *= 1.023  # Empirical factor to get size right.
        cropx0 += cropw/2 - svgw*scale/2
        cropy0 += croph/2 - svgh*scale/2
        
        return scale, cropx0, cropy0 + (svgh - svgch) * scale


class Highlight(object):
    """ Encapsulate a highlighted annotation to a Book.
    """
    
    def __init__(self, book, page, area, content_type, content=None, strict=False):
        self.book = book
        self.page = int(page)
        self.message = ''
        self.area = area
        self.strict = strict
        self.content_type = content_type
        self.content = content
    
    @property
    def bboxes(self):
        if not hasattr(self, '_bboxes'):
            if isinstance(self.area, basestring):
                try:
                    self._bboxes = self.book.page_text(self.page).box_substring(self.area, self.strict)
                except NoSubstringError:
                    self.message = '\n\nThis note was supposed to be attached to the following ' \
                                   'text, which was not found on this page.\n' + self.area
                    self._bboxes = None
                except MultipleSubstringError:
                    self.message = '\n\nThis note was supposed to be attached to the following ' \
                                   'text, which was found multiple times on this page.\n' + self.area
                    self._bboxes = None
            else:
                self._bboxes = self.area
        return self._bboxes
    
    @property
    def text_content(self):
        if self.content_type is HIGHLIGHT:
            if self.message:
                return self.message[2:]  # Remove initial newlines
            return None
        if self.content_type is HIGHLIGHT_TEXT:
            doc = minidom.parse(os.path.join(self.book.reader.path, self.content))
            text = doc.getElementsByTagName('text')[0]
            return text.childNodes[0].toxml() + self.message
        if self.content_type is HIGHLIGHT_DRAWING:
            return "Can't handle drawings yet.  (Sorry.)" + self.message
    
    @property
    def hash(self):
        return hashlib.md5((str(self.page) + unicode(self.area)
                            + unicode(self.text_content)).encode('utf-8')).digest()
    
    def write_to_pdf(self, page, outpdf, crop=None):
        if crop is None:
            # PDFMiner reports positions relative to the mediaBox.
            crop = map(float, page.mediaBox[:])
        if self.bboxes is not None:
            shifted_bboxes = [(bb[0] + crop[0], bb[1] + crop[1], bb[2] + crop[0], bb[3] + crop[1])
                              for bb in self.bboxes]
            annot = highlight_annotation(shifted_bboxes, self.text_content, 'Sony eReader')
        else:
            if not hasattr(page, 'prsannot_vskip'):
                page.prsannot_vskip = 0
            
            pcrop = intersection(page.cropBox[:], page.mediaBox[:])
            x,y = pcrop[0]+10, pcrop[3]-10-page.prsannot_vskip # Add a little margin
            page.prsannot_vskip += 25
            annot = text_annotation([x, y, x, y], self.text_content, 'Sony eReader')
        add_annotation(outpdf, page, annot)
