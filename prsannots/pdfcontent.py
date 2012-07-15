# Copyright 2012 Robert Schroll
#
# This file is part of prsannots and is distributed under the terms of
# the LGPL license.  See the file COPYING for full details.

from pyPdf.pdf import ContentStream
from pyPdf.generic import ArrayObject, NameObject

class StupidSVGInterpreterError(Exception):
    pass

# Help on adding contents to PDF pages from
# https://github.com/Averell7/pyPdf/commit/a7934266c2cb53a778e89beec2ab7d8111a17530
def pdf_add_content(content_string, page, scale=1, offsetx=0, offsety=0):
    """Add content to the end of the content stream of the PDF page.
    
    Inputs: content_string  The PDF drawing commands to add, as a single string.
            
            page            The pyPdf.pdf.PageObject to add the content to.
            
            scale           Before adding the content, adjust the the coordinate
            offsetx         system with a (uniform) scale factor and a
            offsety         translation of offsetx and offsety.
    
    """
    coord_trans = '%.2f 0 0 %.2f %.2f %.2f cm' % (scale, scale, offsetx, offsety)
    commands = '\n'.join(('q', coord_trans, content_string, 'Q'))
    
    try:
        orig_content = page['/Contents'].getObject()
    except KeyError:
        orig_content = ArrayObject([])
    stream = ContentStream(orig_content, page.pdf)
    stream.operations.append([[], commands])
    page[NameObject('/Contents')] = stream

def svg_to_pdf_content(svg):
    """The world's worst SVG-to-PDF converter.
    
    Convert the SVG document svg (a minidom.Node for the svg element) into
    a string of PDF commands, suitable for use with pdf_add_content().
    Currently, only supports stroked polyline elements, and only a few of
    their attributes.  Suitable for the SVG files produced by a Sony Reader,
    and not much else.
    
    """
    commands = []
    
    # Flip coordinate system to SVG top-left origin
    commands.append('1 0 0 -1 0 %s cm' % svg.getAttribute('height'))
    # Switch to black strokes
    commands.append('0 0 0 RG')
    
    for node in svg.childNodes:
        if node.nodeType != node.ELEMENT_NODE:
            continue
        name = node.localName
        try:
            commands.extend(ELEMENT_FUNCS[name](node))
        except KeyError:
            raise StupidSVGInterpreterError, 'Cannot handle %s elements' % name
    
    commands.insert(0, 'q')  # Save graphics state
    commands.append('Q')     # ... and restore it
    return '\n'.join(commands)

def polyline(node):
    attr_func_map = {'stroke-width': lambda w: '%s w' % w,
                     'stroke-linecap': lambda lc: '%i J' % ('butt', 'round', 'square').index(lc),
                     'stroke-linejoin': lambda lj: '%i j' % ('miter', 'round', 'bevel').index(lj),
                    }
    
    commands = []
    for attr in attr_func_map:
        attrval = node.getAttribute(attr)
        if attrval:
            commands.append(attr_func_map[attr](attrval))
    
    pts = node.getAttribute('points').replace(',', ' ').split()
    xs, ys = pts[2::2], pts[3::2]
    segs = ['%s %s l' % (x, y) for x, y in zip(xs, ys)]
    commands.append('%s %s m %s S' % (pts[0], pts[1], ' '.join(segs)))
    
    commands.insert(0, 'q')
    commands.append('Q')
    return commands

ELEMENT_FUNCS = {'polyline': polyline}


if __name__ == '__main__':
    import sys
    from xml.dom import minidom
    import pyPdf
    
    if len(sys.argv) != 3:
        print "Usage: %s file.pdf file.svg" % sys.argv[0]
        sys.exit(1)
    
    inpdf = pyPdf.PdfFileReader(open(sys.argv[1], 'rb'))
    page = inpdf.pages[0]
    
    doc = minidom.parse(sys.argv[2])
    drawing = doc.getElementsByTagNameNS('http://www.sony.com/notepad', 'drawing')[0]
    svg = doc.getElementsByTagNameNS('http://www.w3.org/2000/svg','svg')[0]
    for attr in ('width', 'height'):
        svg.setAttribute(attr, drawing.getAttribute(attr))
    
    pdf_add_content(svg_to_pdf_content(svg), page)
    
    outpdf = pyPdf.PdfFileWriter()
    outpdf.addPage(page)
    outpdf.write(open('pdfcontent.pdf', 'wb'))
    print "Combined file output to pdfcontent.pdf"
