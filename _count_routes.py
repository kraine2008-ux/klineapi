# -*- coding: utf-8 -*-
import re
src = open('app.py', encoding='utf-8').read()
routes = re.findall(r"@app\.route\('(/v1/[^']+)'", src)
print(len(routes), 'v1 routes:')
for r in routes:
    print(' ', r)
