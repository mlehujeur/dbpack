#!/usr/bin/env python
import sys
from dbpack import Database


"""
find the column names of a selection 
like "select * from this"
"""

with Database(sys.argv[1]) as db:

    print('please type/paste your sqlite script below, end with ; ')
    
    lines = []
    while True:
        line = input()
        if line.endswith(';'):
            break            
        lines.append(line)
    text = '\n'.join(lines)

    db.cursor.execute(text)
    column_names = [_[0] for _ in db.cursor.description]

print(',\n'.join(column_names))


