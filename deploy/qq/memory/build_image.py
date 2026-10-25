"""仅把补丁源码送入 Docker 构建，不发送部署配置、密钥或聊天数据。"""
from pathlib import Path
from tempfile import TemporaryDirectory

import hashlib
import json
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[3]
FILES = [
    'src/services/memory_flow_service.py', 'src/services/person_fact_journal.py',
    'src/services/person_fact_policy.py', 'src/person_info/person_info.py',
    'src/A_memorix/core/utils/person_profile_service.py', 'src/A_memorix/core/utils/summary_importer.py',
    *['prompts/' + locale + '/person_fact_extract' + suffix for locale in ['zh-CN', 'en-US', 'ja-JP'] for suffix in ['.prompt', '.meta.json']],
]
manifest = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in FILES}
digest = hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()[:12]
image = 'maibot-qq-core:1.3.15-memory-fix-' + digest
with TemporaryDirectory(prefix='maibot-memory-build-') as directory:
    context = Path(directory)
    for name in FILES:
        target = context / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, target)
    shutil.copyfile(ROOT / 'deploy/qq/memory/Dockerfile', context / 'Dockerfile')
    subprocess.run(['docker', 'build', '--pull=false', '--network=none', '-t', image, str(context)], check=True)
(ROOT / 'deploy/qq/memory/patch_manifest.json').write_text(json.dumps({'image': image, 'base_image': 'maibot-qq-core:1.3.15-062d45cf8', 'files': manifest}, indent=2) + '\n')
print('Built verified local memory-fix image:', image)
