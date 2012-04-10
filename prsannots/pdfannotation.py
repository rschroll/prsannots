# Copyright 2012 Robert Schroll
#
# This file is part of prsannots and is distributed under the terms of
# the LGPL license.  See the file COPYING for full details.

from datetime import datetime
from pyPdf.generic import *

def float_array(lst):
    return ArrayObject([FloatObject(i) for i in lst])

def _markup_annotation(rect, contents=None, author=None, subject=None,
                       color=[1,0,0], alpha=1, flag=4):
    
    # Python timezone handling is a messs, so just use UTC
    now = datetime.utcnow().strftime("D:%Y%m%d%H%M%SZ00'00")
    
    retval = DictionaryObject({ NameObject('/C'): float_array(color),
                                NameObject('/CA'): FloatObject(alpha),
                                NameObject('/F'): NumberObject(flag),
                                NameObject('/Rect'): float_array(rect),
                                NameObject('/Type'): NameObject('/Annot'),
                                NameObject('/CreationDate'): TextStringObject(now),
                                NameObject('/M'): TextStringObject(now),
                             })
    if contents is not None:
        retval[NameObject('/Contents')] = TextStringObject(contents)
    if author is not None:
        retval[NameObject('/T')] = TextStringObject(author)
    if subject is not None:
        retval[NameObject('/Subj')] = TextStringObject(subject)
    return retval


def highlight_annotation(quadpoints, contents=None, author=None,
                         subject=None, color=[1,1,0], alpha=1, flag=4):
    """ Create a 'Highlight' annotation that covers the area given by quadpoints.
    
    Inputs: quadpoints  A list of rectangles to be highlighted as part of this
                        annotation.  Each is specified by a quadruple [x0,y0,x1,y1],
                        where (x0,y0) is the lower left corner of the rectangle and
                        (x1,y1) the upper right corner.
            
            contents    Strings giving the content, author, and subject of the
            author      annotation
            subject
            
            color       The color of the highlighted region, as an array of type
                        [g], [r,g,b], or [c,m,y,k].
            
            alpha       The alpha transparency of the highlight.
            
            flag        A bit flag of options.  4 means the annotation should be
                        printed.  See the PDF spec for more.
    
    Output: A DictionaryObject representing the annotation.
    """
    
    qpl = []
    for x0,y0,x1,y1 in quadpoints:
        qpl.extend([x0, y1, x1, y1, x0, y0, x1, y0])
    # Annotation goes at upper left corner of /Rect.  But this doesn't
    # seem to matter for text markup annotations.
    rect = qpl[:2] + qpl[:2]
    
    retval = _markup_annotation(rect, contents, author, subject, color, alpha, flag)
    retval[NameObject('/Subtype')] = NameObject('/Highlight')
    retval[NameObject('/QuadPoints')] = float_array(qpl)
    return retval

def add_annotation(outpdf, page, annot):
    """ Add the annotation 'annot' to the page 'page' that is/will be part of
    the PdfFileWriter 'outpdf'.
    """
    
    # We need to make an indirect reference, or Acrobat will get huffy.
    indir = outpdf._addObject(annot)
    if '/Annots' in page:
        page['/Annots'].append(indir)
    else:
        page[NameObject('/Annots')] = ArrayObject([indir])


if __name__ == '__main__':
    import sys
    import pyPdf
    try:
        inpdf = pyPdf.PdfFileReader(open(sys.argv[1], 'r'))
    except (IndexError, IOError):
        print "Needs PDF file as an argument."
        raise SystemExit
    annot = highlight_annotation([[100, 100, 400, 125]],
                'An argument is a connected series of statements intended to establish a proposition.', 
                'I came here for a good argument.', 'Graham Chapman')
    page = inpdf.getPage(0)
    outpdf = pyPdf.PdfFileWriter()
    add_annotation(outpdf, page, annot)
    outpdf.addPage(page)
    outpdf.write(open('pythonannotation.pdf', 'w'))
    print "Highlighted PDF output to pythonannotation.pdf"
