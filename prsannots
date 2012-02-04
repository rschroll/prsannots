#!/usr/bin/env python

USAGE = """
%s mount-point

Find all annotated PDFs on the Sony PRS-T1 mounted at the specified
mount point, and present a menu to let the user chose to export one
of them with annotations.  Currently, only the freehand annotations
directly on the page are supported.
"""

import os
import sys
import sqlite3
from xml.dom import minidom
import svglib
from StringIO import StringIO
import pyPdf

def get_database(path):
    return sqlite3.connect(os.path.join(path, 'Sony_Reader', 'database', 'books.db'))

def get_annotated_pdfs(db):
    c = db.cursor()
    c.execute('''select books._id, books.title, books.file_path, books.thumbnail
                    from books inner join freehand
                    on books._id = freehand.content_id
                    where mime_type = "application/pdf"
                    group by books._id''')
    return c.fetchall()

def get_annotations(db, book_id):
    c = db.cursor()
    c.execute('''select page, svg_file, crop_left, crop_top, crop_right, crop_bottom, orientation
                    from freehand
                    where content_id = ?
                    order by page''', (book_id,))
    return c.fetchall()

def select_book(books):
    print "Please select which book to get:"
    for i, row in enumerate(books):
        title = row[1] or row[2].split('/')[-1]
        print "  %i. %s" % (i+1, title)
    which = raw_input("> ")
    try:
        return books[int(which) - 1]
    except (ValueError, IndexError):
        print "Could not understand your response.  Aborting."
    sys.exit(1)

def clean_svg(path, fn):
    doc = minidom.parse(os.path.join(path, fn))
    drawing = doc.getElementsByTagNameNS('http://www.sony.com/notepad', 'drawing')[0]
    svg = doc.getElementsByTagNameNS('http://www.w3.org/2000/svg','svg')[0]
    for attr in ('width', 'height'):
        svg.setAttribute(attr, drawing.getAttribute(attr))
    return svg

def svg2pdf(svg):
    renderer = svglib.SvgRenderer()
    renderer.render(svg)
    drawing = renderer.finish()
    
    pdfstring = svglib.renderPDF.drawToString(drawing)
    pdf = pyPdf.PdfFileReader(StringIO(pdfstring))
    return pdf.getPage(0)

def scale_offset(svgcrop, svgcanvas, orientation, pdfcrop):
    svgw, svgh = map(float, svgcrop[2:])
    if orientation in (u'90', u'270'):
        svgw, svgh = svgh, svgw
    svgcw, svgch = map(float, svgcanvas)
    (cropx0, cropy0), (cropx1, cropy1) = map(float, pdfcrop.lowerLeft), map(float, pdfcrop.upperRight)
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

def main(path):
    db = get_database(path)
    books = get_annotated_pdfs(db)
    book_id, title, book_file, thumbnail = select_book(books)
    annots = get_annotations(db, book_id)
    
    pdf = pyPdf.PdfFileReader(open(os.path.join(path, book_file), 'r'))
    outpdf = pyPdf.PdfFileWriter()
    for i, page in enumerate(pdf.pages):
        crop = page.cropBox
        while annots and int(annots[0][0]) == i:
            svg = clean_svg(path, annots[0][1])
            apage = svg2pdf(svg)
            scale, offsetx, offsety = scale_offset(annots[0][2:6],
                                        map(svg.getAttribute, ('width', 'height')), 
                                        annots[0][6], crop)
            page.mergeScaledTranslatedPage(apage, scale, offsetx, offsety)
            annots.pop(0)
        outpdf.addPage(page)
    outfn = os.path.splitext(os.path.basename(book_file))[0] + '.annot.pdf'
    userfn = raw_input("Enter output file name [%s]: " % outfn)
    if userfn:
        outfn = userfn
    outpdf.write(open(outfn, 'w'))

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print USAGE % sys.argv[0]
        sys.exit(0)
    if not os.path.ismount(sys.argv[1]):
        print "First argument must be mount point of Sony Reader."
        print "(%s does not appear to be a mount point.)" % sys.argv[1]
        sys.exit(1)
    main(sys.argv[1])
