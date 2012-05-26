# Copyright 2012 Robert Schroll
#
# This file is part of prsannots and is distributed under the terms of
# the LGPL license.  See the file COPYING for full details.

import os
from xml.dom import minidom
from StringIO import StringIO
import hashlib
import pyPdf
from pagetext import PageText, get_layouts, NoSubstringError, MultipleSubstringError
from pdfannotation import highlight_annotation, text_annotation, add_annotation
from pdfcontent import pdf_add_content, svg_to_pdf_content

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
    """Represents an ereader, with its annotated books.
    
    The books may be indexed by their file name on the reader.
    
    """
    def __init__(self, path):
        self.path = path
    
    @property
    def books(self):
        """A list of books that are annotated PDF files on the reader."""
        if not hasattr(self, '_books'):
            self._books = self._get_books()
        return self._books
    
    def _get_books(self):
        raise NotImplementedError, "Subclasses must implement a _get_books() method."
    
    def __getitem__(self, filepath):
        # The path as saved in the database uses '/' for the path separator.
        filepath = filepath.replace(os.path.sep, '/')
        for b in self.books:
            if b.file == filepath:
                return b
        raise KeyError


class Book(object):
    """Represents a PDF file stored on the ereader."""
    
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
        """A list of annotations to the book, sorted by page number."""
        if not hasattr(self, '_annotations'):
            self._annotations = self._get_annotations()
            self._annotations.sort(lambda a,b: cmp(a.page, b.page))
        return self._annotations
    
    def _get_annotations(self):
        raise NotImplementedError, "Subclasses must implement a _get_annotations() method."
    
    @property
    def hash(self):
        """A number unique to the current annotation state."""
        if not hasattr(self, '_hash'):
            hashes = [ann.hash for ann in self.annotations]
            self._hash = hashlib.md5(''.join(hashes)).digest()
        return self._hash
    
    @property
    def pdf(self):
        """A pyPdf.PdfFileReader instance of the PDF file."""
        return pyPdf.PdfFileReader(open(os.path.join(self.reader.path, self.file), 'rb'))
    
    def pdf_layout(self, page):
        """Get a pdfminer.LTPage object for page."""
        if self._layouts is None:
            self._layouts = get_layouts(open(os.path.join(self.reader.path, self.file), 'rb'))
        return self._layouts[page]
    
    def page_text(self, page):
        """Get the pagetext.PageText object for page."""
        if page not in self._page_texts:
            self._page_texts[page] = PageText(self.pdf_layout(page))
        return self._page_texts[page]
    
    def write_annotated_pdf(self, outfd, pdf=None, dice_map=None):
        """Write an annotated version of the PDF file.
        
        Inputs: outfd       A file object, to which the PDF is output.
                
                pdf         The original PDF file.  If None, use self.pdf.
                
                dice_map    The dice map describing how the PDF on the
                            reader was made from the original PDF file.
        
        """
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
    """Represents a freehand annotation to a Book."""
    
    def __init__(self, book, page, svg_file, crop_left, crop_top, crop_right, crop_bottom, orientation):
        self.book = book
        self.page = int(page)
        self.svg_file = svg_file
        self.crop = map(float, (crop_left, crop_top, crop_right, crop_bottom))
        self.orientation = int(orientation)
    
    @property
    def svg(self):
        """The SVG associated with the annotation, as a minidom object."""
        if not hasattr(self, '_svg'):
            doc = minidom.parse(os.path.join(self.book.reader.path, self.svg_file))
            drawing = doc.getElementsByTagNameNS('http://www.sony.com/notepad', 'drawing')[0]
            self._svg = doc.getElementsByTagNameNS('http://www.w3.org/2000/svg','svg')[0]
            for attr in ('width', 'height'):
                self._svg.setAttribute(attr, drawing.getAttribute(attr))
        return self._svg
    
    @property
    def hash(self):
        """Uniquely identifies the current annotation."""
        return hashlib.md5(str(self.crop) + str(self.orientation) + self.svg.toxml('utf-8')).digest()
    
    def write_to_pdf(self, page, outpdf, crop=None):
        """Write the annotation to the page which will be in outpdf.
        
        Note that outpdf is not used in this function; it is included only
        to have the same signature as Highlight.write_to_pdf().
        
        """
        if crop is None:
            # The reader displays the intersection of the cropBox and the mediaBox.
            crop = intersection(page.cropBox[:], page.mediaBox[:])
        pdf_add_content(svg_to_pdf_content(self.svg), page, *self.scale_offset(crop))
    
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
    """Represents a highlighted annotation to a Book."""
    
    def __init__(self, book, page, area, content_type, content=None, strict=False):
        """Initialize the Highlight object.
        
        Inputs: book            The Book in which this annotation is.
                
                page            The page number in the PDF of the annotation.
                
                area            The highlighted area associated with the
                                annotation.  Either the highlighted text
                                or a list of bounding boxes.
                
                content_type    One of HIGHLIGHT, HIGHLIGHT_TEXT, HIGHLIGHT_DRAWING
                
                content         Notes added to the highlighted region.
                
                strict          If False, we select the first region with
                                text that matches area.  If True, we won't
                                match any text if it appears more than once
                                on the page.  Instead, we add a text
                                annotation in the top-left corner of the
                                page, saying what happend.
        
        """
        self.book = book
        self.page = int(page)
        self.message = ''
        self.area = area
        self.strict = strict
        self.content_type = content_type
        self.content = content
    
    @property
    def bboxes(self):
        """A list of bounding boxes that cover the annotated region."""
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
        """The text to put into the annotation."""
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
        """Uniquely identify the annotation."""
        return hashlib.md5((str(self.page) + unicode(self.area)
                            + unicode(self.text_content)).encode('utf-8')).digest()
    
    def write_to_pdf(self, page, outpdf, crop=None):
        """Write the annotation to page in outpdf."""
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
            annot = text_annotation([x, y-20, x+20, y], self.text_content, 'Sony eReader')
        add_annotation(outpdf, page, annot)
