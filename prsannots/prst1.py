# Copyright 2012 Robert Schroll
#
# This file is part of prsannots and is distributed under the terms of
# the LGPL license.  See the file COPYING for full details.

import os
import sqlite3
import generic

class Reader(generic.Reader):
    
    def __init__(self, path):
        generic.Reader.__init__(self, path)
        self.db = sqlite3.connect(os.path.join(path, 'Sony_Reader', 'database', 'books.db'))
    
    def _get_books(self):
        c = self.db.cursor()
        # markup_types:  0 bookmark
        #               10 highlight
        #               11 text
        #               12 drawing
        #               20 freehand
        c.execute('''select books._id, books.title, books.file_path, books.thumbnail
                        from books inner join markups
                        on books._id = markups.content_id
                        where mime_type = "application/pdf" and markup_type != 0
                        group by books._id''')
        return [Book(self, *line) for line in c]

class Book(generic.Book):
    
    def _get_annotations(self):
        c = self.reader.db.cursor()
        c.execute('''select page, svg_file, crop_left, crop_top, crop_right, crop_bottom, orientation
                        from freehand
                        where content_id = ?
                        order by page''', (self.id,))
        freehand = [generic.Freehand(self, *line) for line in c]
        
        c.execute('''select page, marked_text, markup_type, file_path
                        from annotation
                        where content_id = ?
                        order by page''', (self.id,))
        highlight = [generic.Highlight(self, *line) for line in c]
        
        return freehand + highlight

