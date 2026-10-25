"""在临时实例和无外部 API 的配置下运行记忆回归测试。"""
from pathlib import Path
from tempfile import TemporaryDirectory

import os
import sys
import tomllib

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
os.environ['MAIBOT_INITIALIZE_ONLY'] = '1'
os.environ['PYTEST_DISABLE_PLUGIN_AUTOLOAD'] = '1'

with TemporaryDirectory(prefix='maibot-memory-tests-') as directory:
    os.environ['MAIBOT_INSTANCE_DIR'] = directory
    from src.config.config import Config, ModelConfig, config_manager
    model = tomllib.loads((ROOT / 'deploy/qq/model.template.toml').read_text())
    for provider in model['api_providers']:
        provider['base_url'] = 'http://127.0.0.1:9/v1'
        provider['api_key'] = 'offline-test'
    config_manager.global_config = Config()
    config_manager.model_config = ModelConfig.model_validate(model)
    from src.common.database.database import initialize_database
    initialize_database()
    import pytest
    targets = sys.argv[1:] or [
        'pytests/A_memorix_test/test_person_memory_writeback.py',
        'pytests/A_memorix_test/test_person_profile_service.py',
        'pytests/A_memorix_test/test_person_fact_repair.py',
        'pytests/A_memorix_test/test_chat_summary_writeback_integration.py',
    ]
    raise SystemExit(pytest.main(['-p', 'pytest_asyncio.plugin', '-q', '--disable-warnings', *targets]))
