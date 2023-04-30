import json
from PyInstaller.utils.hooks import collect_data_files
datas = collect_data_files('luau')
print(f"data files: {json.dumps(datas, indent=5)}")