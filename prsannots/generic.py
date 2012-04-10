# Copyright 2012 Robert Schroll
#
# This file is part of prsannots and is distributed under the terms of
# the LGPL license.  See the file COPYING for full details.

import os
from xml.dom import minidom
import svglib
from StringIO import StringIO
import pyPdf
from pagetext import PageText, get_layouts
from pdfannotation import highlight_annotation, add_annotation

HIGHLIGHT, HIGHLIGHT_TEXT, HIGHLIGHT_DRAWING = 10, 11, 12

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
        return self._annotations
    
    def _get_annotations(self):
        raise NotImplementedError, "Subclasses must implement a _get_annotations() method."
    
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
    def pdf(self):
        renderer = svglib.SvgRenderer()
        renderer.render(self.svg)
        drawing = renderer.finish()
        
        pdfstring = svglib.renderPDF.drawToString(drawing)
        pdfdoc = pyPdf.PdfFileReader(StringIO(pdfstring))
        return pdfdoc.getPage(0)
    
    def write_to_pdf(self, page, outpdf, crop=None):
        if crop is None:
            cb = page.cropBox
            crop = map(float, cb.lowerLeft) + map(float, cb.upperRight)
        page.mergeScaledTranslatedPage(self.pdf, *self.scale_offset(crop))
    
    def scale_offset(self, pdfcrop):
        svgw, svgh = self.crop[2:]
        svgcw, svgch = [float(self.svg.getAttribute(x)) for x in ('width', 'height')]
        cropx0, cropy0, cropx1, cropy1 = pdfcrop
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
    
    def __init__(self, book, page, area, content_type, content=None):
        self.book = book
        self.page = int(page)
        if isinstance(area, basestring):
            self.bboxes = self.book.page_text(self.page).box_substring(area)
        else:
            self.bboxes = area
        self.content_type = content_type
        self.content = content
    
    @property
    def text_content(self):
        if self.content_type is HIGHLIGHT:
            return None
        if self.content_type is HIGHLIGHT_TEXT:
            doc = minidom.parse(os.path.join(self.book.reader.path, self.content))
            text = doc.getElementsByTagName('text')[0]
            return text.childNodes[0].toxml()
        if self.content_type is HIGHLIGHT_DRAWING:
            return "Can't handle drawings yet.  (Sorry.)"
    
    def write_to_pdf(self, page, outpdf):
        annot = highlight_annotation(self.bboxes, self.text_content, 'Sony eReader')
        add_annotation(outpdf, page, annot)
