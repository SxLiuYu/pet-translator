from pathlib import Path
import re

path = Path('server/app.py')
text = path.read_text(encoding='utf-8')
text = text.replace('from __future__ import annotations\n\n', '')
text = re.sub(r': (str|int|float|bool|dict|list) \| None', lambda m: ': Optional[' + m.group(1) + ']', text)
text = re.sub(r': (str|int|float|bool|dict|list) \| None', lambda m: ': Optional[' + m.group(1) + ']', text)
path.write_text(text, encoding='utf-8')
print('fixed annotations globally')
