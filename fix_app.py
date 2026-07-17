from pathlib import Path
restore = """
\"\"\"
app.py
...
\"\"\"
...
"""
Path('server/app.py').write_text(restore, encoding='utf-8')
print('restored')
