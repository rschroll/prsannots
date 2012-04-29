#!/usr/bin/env python

check_dependencies = False
try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup
    check_dependencies = True

setup(
    name = 'prsannots',
    version = '0.1.1',
    description = 'Get annotated PDFs from your Sony PRS-T1 ereader.',
    license = 'LGPL 3',
    author = 'Robert Schroll',
    author_email = 'rschroll@gmail.com',
    url = 'https://github.com/rschroll/prsannots',
    packages = ['prsannots'],
    scripts = ['prsam', 'prsam-tk', 'getannotations'],
    install_requires = ['pyPdf >= 1.13', 'pdfminer'],
    keywords = 'pdf, pdf annotation, ereader, PRS-T1',
    classifiers = [
        'Development Status :: 3 - Alpha',
        'Environment :: Console',
        'Environment :: X11 Applications',
        'Environment :: Win32 (MS Windows)',
        'Environment :: MacOS X',
        'Intended Audience :: End Users/Desktop',
        'License :: OSI Approved :: GNU Lesser General Public License v3 or later (LGPLv3+)',
        'Programming Language :: Python :: 2'
        ],
    long_description = open('README.rst', 'r').read()
    )

if check_dependencies:
    # Test to see if dependencies are installed or not.  We don't want to
    # check these if installing with pip, since the dependencies will be
    # installed afterwards.  But there doesn't seem to be a way to test
    # for pip, so we only test these when using distutils, and hope that
    # everything goes correctly with setuptools or distribute.
    try:
        import pyPdf
    except ImportError:
        print "Note: pyPdf is needed, but not installed. See http://pybrary.net/pyPdf/"

    try:
        import pdfminer
    except ImportError:
        print "Note: PDFMiner is needed, but not installed.  See http://www.unixuser.org/~euske/python/pdfminer/"
