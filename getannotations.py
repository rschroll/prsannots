#!/usr/bin/env python

import os
import sys
import tempfile
import sqlite3
from xml.dom import minidom
import rsvg
import cairo
import pyPdf

def get_database(path):
    return sqlite3.connect(os.path.join(path, *('Sony_Reader', 'database', 'books.db')))

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
    c.execute('''select page, svg_file, crop_left, crop_top, crop_right, crop_bottom
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
    drawing = doc.getElementsByTagNameNS("http://www.sony.com/notepad", "drawing")[0]
    svg = doc.getElementsByTagNameNS('http://www.w3.org/2000/svg','svg')[0]
    for attr in ('width', 'height'):
        svg.setAttribute(attr, drawing.getAttribute(attr))
    return svg

def svg2pdf(svg, svgcrop, pdfcrop):
    fh, tempfn = tempfile.mkstemp()
    os.close(fh)
    svg.writexml(open(tempfn, 'w'))
    
    svgw, svgh = map(float, svgcrop[2:])
    (cropx0, cropy0), (cropx1, cropy1) = map(float, pdfcrop.lowerLeft), map(float, pdfcrop.upperRight)
    cropw = cropx1 - cropx0
    croph = cropy1 - cropy0
    if croph/cropw > svgh/svgw:  # Tall and skinny
        midx = cropx0 + cropw/2
        cropw = svgw/svgh * croph
        cropx0 = midx - cropw/2
        cropx1 = midx + cropw/2
    else:
        midy = cropy0 + croph/2
        croph = svgh/svgw * cropw
        cropy0 = midy - croph/2
        cropy1 = midy + croph/2
    
    rs = rsvg.Handle(tempfn)
    surf = cairo.PDFSurface(tempfn, cropx1, cropy1)
    cr = cairo.Context(surf)
    # The cairo coordinate system is from the top left, not the bottom left of PDFs.
    # We created the surface to be just as big as we need it, so we don't have to
    # to any vertical translations; we're already lined up at the top of the box.
    cr.translate(cropx0, 0)
    cr.scale(cropw/svgw, croph/svgh)
    rs.render_cairo(cr)
    surf.finish()
    
    pdf = pyPdf.PdfFileReader(open(tempfn, 'r'))
    os.unlink(tempfn)
    return pdf.getPage(0)

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
            apage = svg2pdf(clean_svg(path, annots[0][1]), annots[0][2:], crop)
            page.mergePage(apage)
            annots.pop(0)
        outpdf.addPage(page)
    title = title or book_file.split('/')[-1]
    title = title.replace(os.path.sep, '_') + '.annot.pdf'
    outpdf.write(open(title, 'w'))
    print "Annotated file saved as", title

if __name__ == '__main__':
    main(*sys.argv[1:])
