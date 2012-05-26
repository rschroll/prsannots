# Copyright 2008-2012 Hartmut Goebel <h.goebel@goebel-consult.de>
# Copyright 2012 Robert Schroll
#
# This file is part of prsannots and is distributed under the terms of
# the LGPL license.  See the file COPYING for full details.

import os
from subprocess import call
from tempfile import mkstemp
from pyPdf.pdf import PdfFileWriter, PdfFileReader, PageObject, \
                      NameObject, RectangleObject
from generic import intersection

PAGE_BOXES = ("/MediaBox", "/CropBox", "/BleedBox", "/TrimBox", "/ArtBox")

_mm = 72 / 25.4
UNITS = {'pt': 1, 'in': 72, 'mm': _mm, 'cm': 10*_mm}

def dice(inpdf, ncols, nrows, crop=0, overlap=0.05):
    """Dice each page in the PDF file into a number of sub-pages.
    
    Inputs: inpdf       The pyPdf.PdfFileReader to be diced.
            
            ncols       Each page will be diced into ncols columns and
            nrows       nrows rows.
            
            crop        The amount to crop from the edges of page in
                        Postscript points (1/72 in).  Either a number or
                        as list of 1, 2 (horizontal, vertical), or 4
                        (left, bottom, right, top) numbers.
            
            overlap     The amount of overlap for the sub-pages, as a
                        percentage of the cropped page size.  Either a
                        float or a list of two floats for the horizontal
                        and vertical overlaps.
    
    Output: outpdf      A pyPdf.PdfFileWriter for the diced PDF.
            
            dice_map    A list of tuples, one for each page in outpdf.
                        Each tuple is of the form (page, bbox), where
                        page is the page in inpdf and bbox a tuple of
                        length 4 giving the bounding box that specifies
                        the diced page on the original page.
    
    """
    if isinstance(crop, (float, int)):
        crop = (crop,)
    if len(crop) == 1:
        crop = (crop[0], crop[0], crop[0], crop[0])
    elif len(crop) == 2:
        crop = (crop[0], crop[1], crop[0], crop[1])
    elif len(crop) != 4:
        raise ValueError, "crop must be length 1, 2, or 4."
    
    if isinstance(overlap, (float, int)):
        overlap = (overlap, overlap)
    if len(overlap) == 1:
        overlap = (overlap[0], overlap[0])
    
    outpdf = PdfFileWriter()
    dice_map = []
    for i, page in enumerate(inpdf.pages):
        bboxes = dice_page(outpdf, page, ncols, nrows, crop, overlap)
        for bbox in bboxes:
            dice_map.append((i, bbox))
    return outpdf, dice_map

def write_pdf(outpdf, filename, gs=False):
    """Write the PDF file, possibly sending running it through Ghostscript.
    
    Inputs: outpdf      The pyPdf.PdfFileWriter to be output.
            
            filename    The file where the PDF is to be saved.
            
            gs          If True, the file will be sent through Ghostscript's
                        pdfwrite device.  Sometimes this can reduce the
                        file size and improve the Reader's rendering time.
    
    """
    if gs:
        info = outpdf._info.getObject()
        title = info.get('/Title', None)
        author = info.get('/Author', None)
        
        tmpfd, tmpfn = mkstemp()
        tmp = os.fdopen(tmpfd, 'wb')
        outpdf.write(tmp)
        tmp.close()
        callarr = ['gs', '-sDEVICE=pdfwrite', '-dCompatibility=1.4', '-dNOPAUSE',
                   '-dQUIET', '-dBATCH', '-sOutputFile=%s' % filename, tmpfn]
        
        if title or author:
            # See http://milan.kupcevic.net/ghostscript-ps-pdf/#marks
            # Note that the marks have to come in a different file; we can't
            # just send them both in through stdin.  This is why we have to
            # fuss around with mkstemp.
            markfd, markfn = mkstemp()
            mark = os.fdopen(markfd, 'w')
            mark.write('[')
            title and mark.write(' /Title (%s)\n' % title.encode('utf-8'))
            author and mark.write(' /Author (%s)\n' % author.encode('utf-8'))
            mark.write(' /DOCINFO pdfmark\n')
            mark.close()
            callarr.append(markfn)
        else:
            markfn = None
        
        retcode = call(callarr)
        os.unlink(tmpfn)
        if markfn is not None:
            os.unlink(markfn)
        if retcode == 0:
            return
        print "Error code %i returned by Ghostscript.  Trying direct output." % retcode
    
    outpdf.write(open(filename, 'wb'))

# Helper functions
def copy_page(page):
    newpage = PageObject(page.pdf)
    newpage.update(page)
    # Copy Rectangles to be manipulatable
    for attr in PAGE_BOXES:
        if page.has_key(attr):
            newpage[NameObject(attr)] = RectangleObject(list(page[attr]))
    return newpage

def dice_page(outpdf, page, ncols, nrows, crop, overlap):
    obox = map(float, intersection(page.cropBox[:], page.mediaBox[:]))
    box = (obox[0] + crop[0], obox[1] + crop[1], obox[2] - crop[2], obox[3] - crop[3])
    width = (box[2] - box[0]) * ((1. - overlap[0])/ncols + overlap[0])
    xspace = (box[2] - box[0]) * (1. - overlap[0])/ncols
    height = (box[3] - box[1]) * ((1. - overlap[1])/nrows + overlap[1])
    yspace = (box[3] - box[1]) * (1. - overlap[1])/nrows
    x0, y0 = box[0], box[1]
    
    bboxes = []
    for col in range(ncols):
        for row in range(nrows-1, -1, -1):
            newpage = copy_page(page)
            bbox = (col * xspace + x0, row * yspace + y0,
                    col * xspace + x0 + width, row * yspace + y0 + height)
            newpage.cropBox = newpage.artBox = newpage.trimBox = newpage.mediaBox = RectangleObject(bbox)
            outpdf.addPage(newpage)
            bboxes.append(bbox)
    return bboxes


if __name__ == '__main__':
    import sys
    try:
        inpdf = PdfFileReader(open(sys.argv[1], 'rb'))
        ncols = int(sys.argv[2])
        nrows = int(sys.argv[3])
    except (IndexError, IOError):
        print "Usage: %s file.pdf ncols nrows [overlap [crop]]" % sys.argv[0]
        raise SystemExit
    
    overlap = map(float, sys.argv[4:6])
    if not overlap:
        overlap = 0.05
    crop = map(float, sys.argv[6:10])
    if not crop:
        crop = 0
    
    outpdf, _ = dice(inpdf, ncols, nrows, crop, overlap)
    write_pdf(outpdf, 'pdfdice.pdf')
    print "Diced PDF file output to pdfdice.pdf"
