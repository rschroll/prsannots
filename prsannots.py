#!/usr/bin/env python

"""
%s mount-point

Find all annotated PDFs on the Sony PRS-T1 mounted at the specified
mount point, and present a menu to let the user chose to export one
of them with annotations.  Currently, only the freehand annotations
drawn directly on the page are supported.
"""

# Copyright 2012 Robert Schroll
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this program.  If not, see
# <http://www.gnu.org/licenses/>.

import os
import sys
import pyPdf
from prsannots.prst1 import Reader

__version__ = "0.1"
__license__ = "LGPL 3"
__author__ = "Robert Schroll"
__date__ = "2012-02-04"


def select_book(books):
    print "Please select which book to get:"
    for i, book in enumerate(books):
        title = book.title or book.file.split('/')[-1]
        print "  %i. %s" % (i+1, title)
    which = raw_input("> ")
    try:
        return books[int(which) - 1]
    except (ValueError, IndexError):
        print "Could not understand your response.  Aborting."
    sys.exit(1)

def main(path):
    reader = Reader(path)
    book = select_book(reader.books)
    annots = book.annotations
    
    outpdf = pyPdf.PdfFileWriter()
    for i, page in enumerate(book.pdf.pages):
        crop = page.cropBox
        while annots and annots[0].page == i:
            annots[0].write_to_pdf(page)
            annots.pop(0)
        outpdf.addPage(page)
    outfn = os.path.splitext(os.path.basename(book.file))[0] + '.annot.pdf'
    userfn = raw_input("Enter output file name [%s]: " % outfn)
    if userfn:
        outfn = userfn
    outpdf.write(open(outfn, 'w'))

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print __doc__ % sys.argv[0]
        sys.exit(0)
    if not os.path.ismount(sys.argv[1]):
        print "First argument must be mount point of Sony Reader."
        print "(%s does not appear to be a mount point.)" % sys.argv[1]
        sys.exit(1)
    main(sys.argv[1])
