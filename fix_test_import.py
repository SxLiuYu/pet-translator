from pathlib import Path
path = Path('tests/test_app_api.py')
text = path.read_text(encoding='utf-8')
if 'from datetime import datetime' not in text:
    text = text.replace('import os\nimport sys\n', 'import os\nimport sys\nfrom datetime import datetime\n')
    path.write_text(text, encoding='utf-8')
    print('added datetime import')
else:
    print('datetime import already exists')
