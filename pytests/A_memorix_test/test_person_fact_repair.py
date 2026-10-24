from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import AsyncMock

import json
import sqlite3

import pytest

from src.A_memorix.core.utils.person_profile_service import PersonProfileService
from src.config.config import global_config
from src.services import memory_flow_service as flow
from src.services.person_fact_journal import PersonFactJournal
from src.services.person_fact_policy import direct_person_statement, statement_key


def test_journal_survives_restart_and_does_not_retry_failed_evidence(tmp_path):
    path = tmp_path / 'journal.sqlite3'
    first = PersonFactJournal(path)
    assert first.claim('real-stream', 'person', ['message']) == ['message']
    first.finish('real-stream', 'person', ['message'], succeeded=False)
    assert PersonFactJournal(path).claim('real-stream', 'person', ['message']) == []
    assert first.claim('real-stream', 'person', ['new-message']) == ['new-message']
    first.finish('real-stream', 'person', ['new-message'], succeeded=True)
    assert PersonFactJournal(path).claim('real-stream', 'person', ['new-message']) == []
    assert path.stat().st_mode & 0o777 == 0o600


def test_journal_seeds_deleted_sources_without_restoring_them(tmp_path):
    metadata = tmp_path / 'metadata'
    metadata.mkdir()
    with sqlite3.connect(metadata / 'metadata.db') as db:
        db.execute('CREATE TABLE paragraphs(metadata TEXT,is_deleted INTEGER)')
        db.execute('INSERT INTO paragraphs VALUES(?,1)', (json.dumps({
            'source_type': 'person_fact', 'person_id': 'person', 'chat_id': 'real-stream',
            'evidence_message_ids': ['deleted-source']}),))
    journal = PersonFactJournal(tmp_path / 'journal.sqlite3')
    assert journal.claim('real-stream', 'person', ['deleted-source']) == []
    with sqlite3.connect(metadata / 'metadata.db') as db:
        assert db.execute('SELECT is_deleted FROM paragraphs').fetchone()[0] == 1


def test_parallel_claim_has_one_winner(tmp_path):
    path = tmp_path / 'journal.sqlite3'
    PersonFactJournal(path).claim('s', 'p', ['initialize'])
    with ThreadPoolExecutor(max_workers=6) as pool:
        values = list(pool.map(lambda _: PersonFactJournal(path).claim('s', 'p', ['same']), range(12)))
    assert sum(bool(item) for item in values) == 1


@pytest.mark.parametrize('source', [
    '我正在帮你改记忆模块', '我今天打算去画画', '如果我喜欢拼图', '我朋友喜欢拼图',
    '我觉得你喜欢拼图', '我说“你喜欢拼图”', '我喜欢拼图？', '我们喜欢拼图',
])
def test_unstable_or_ambiguous_statements_are_not_stable_facts(source):
    assert direct_person_statement(source, source, person_name='用户', bot_name='DeepSeek', private=True) is None


def test_private_addressee_is_named_and_group_addressee_is_not_guessed():
    quote = '我给你部署了MaiBot'
    assert direct_person_statement(quote, quote, person_name='用户', bot_name='DeepSeek', private=True) == '用户给DeepSeek部署了MaiBot'
    assert direct_person_statement(quote, quote, person_name='用户', bot_name='DeepSeek', private=False) is None
    assert direct_person_statement('我喜欢拼图', '如果我喜欢拼图', person_name='用户', bot_name='DeepSeek', private=True) is None
    assert direct_person_statement('我喜欢拼图', '我喜欢拼图，但是这句是玩笑', person_name='用户', bot_name='DeepSeek', private=True) is None
    assert direct_person_statement('我喜欢拼图', '我喜欢拼图？', person_name='用户', bot_name='DeepSeek', private=True) is None


@pytest.mark.asyncio
async def test_split_reply_extracts_once_and_uses_source_not_model_paraphrase(tmp_path, monkeypatch):
    monkeypatch.setattr(global_config.bot, 'nickname', 'DeepSeek')
    person = SimpleNamespace(person_id='person', person_name='用户', nickname='用户', is_known=True)
    source = SimpleNamespace(message_id='user-message', processed_plain_text='我给你部署了MaiBot',
                             message_info=SimpleNamespace(user_info=SimpleNamespace(user_nickname='用户', user_cardname='', user_id='22222')))
    service = flow.PersonFactWritebackService()
    service._fact_journal = PersonFactJournal(tmp_path / 'journal.sqlite3')
    monkeypatch.setattr(service, '_resolve_target_person', lambda _: person)
    monkeypatch.setattr(service, '_collect_user_evidence', lambda *_: flow.PersonFactEvidence([source], [source]))
    service._extractor = SimpleNamespace(generate_response=AsyncMock(return_value=SimpleNamespace(response=json.dumps([
        {'fact': '用户给对方部署了MaiBot', 'evidence_message_id': 'user-message', 'evidence_quote': source.processed_plain_text}
    ], ensure_ascii=False))))
    store = AsyncMock(return_value=True)
    monkeypatch.setattr(flow, 'store_person_memory_from_answer', store)
    message = SimpleNamespace(session_id='real-stream', processed_plain_text='本鲸有话想接着说。', session=SimpleNamespace(group_id=''))
    await service._handle_message(message)
    await service._handle_message(message)
    assert service._extractor.generate_response.await_count == 1
    assert store.await_count == 1
    assert store.call_args.args[1] == '用户给DeepSeek部署了MaiBot'
    assert store.call_args.kwargs['evidence_message_ids'] == ['user-message']
    assert 'DeepSeek' in service._extractor.generate_response.call_args.args[0]
    restarted = flow.PersonFactWritebackService()
    restarted._fact_journal = PersonFactJournal(tmp_path / 'journal.sqlite3')
    monkeypatch.setattr(restarted, '_resolve_target_person', lambda _: person)
    monkeypatch.setattr(restarted, '_collect_user_evidence', lambda *_: flow.PersonFactEvidence([source], [source]))
    restarted._extractor = SimpleNamespace(generate_response=AsyncMock(side_effect=AssertionError('must not extract twice')))
    await restarted._handle_message(message)


@pytest.mark.asyncio
async def test_private_summary_passes_real_person_binding(monkeypatch):
    service = flow.ChatSummaryWritebackService()
    monkeypatch.setattr(service, '_count_messages_until_trigger', lambda **_: 60)
    monkeypatch.setattr(service, '_load_last_trigger_message_count', AsyncMock(return_value=0))
    monkeypatch.setattr(flow.PersonFactWritebackService, '_resolve_private_person', staticmethod(lambda *_: SimpleNamespace(person_id='person', person_name='用户', nickname='用户', is_known=True)))
    ingest = AsyncMock(return_value=SimpleNamespace(success=True, detail='test'))
    monkeypatch.setattr(flow.memory_service, 'ingest_summary', ingest)
    message = SimpleNamespace(session_id='real-stream', timestamp=1_700_000_000, platform='qq',
                              session=SimpleNamespace(user_id='22222', group_id='', platform='qq'))
    await service._handle_message(message)
    assert ingest.call_args.kwargs['metadata']['person_ids'] == ['person']
    assert ingest.call_args.kwargs['participants'] == ['用户']


def test_profile_duplicate_does_not_reappear_in_another_section():
    buckets = {'stable_facts': ['用户给 DeepSeek 部署了 MaiBot。'], 'recent_interactions': []}
    PersonProfileService._append_profile_bucket(buckets, 'recent_interactions', '用户给DeepSeek部署了MaiBot')
    assert buckets['recent_interactions'] == []


@pytest.mark.asyncio
async def test_summary_importer_preserves_attribution_in_common_ingest(monkeypatch):
    from src.A_memorix.core.utils.summary_importer import SummaryImporter
    importer = object.__new__(SummaryImporter)
    importer.metadata_store = SimpleNamespace(get_external_memory_ref=lambda _: None)
    ingest = AsyncMock(return_value={"stored_ids": ["paragraph"]})
    monkeypatch.setattr(importer, "_plugin_instance", lambda: SimpleNamespace(ingest_text=ingest))
    result = await importer._execute_import("用户喜欢拼图", [], [], "real-stream",
                                            metadata={"external_id": "real-summary", "person_ids": ["person"], "participants": ["用户"]})
    assert result == "paragraph"
    assert ingest.call_args.kwargs["person_ids"] == ["person"]
    assert ingest.call_args.kwargs["participants"] == ["用户"]


def test_statement_identity_preserves_technical_symbols():
    assert statement_key("用户喜欢 C++") != statement_key("用户喜欢 C#")
    assert statement_key("用户喜欢 Visual Studio") == statement_key("用户喜欢Visual Studio。")


@pytest.mark.parametrize("locale", ["zh-CN", "en-US", "ja-JP"])
def test_person_fact_prompt_preserves_roles_and_has_metadata(locale):
    from src.common.prompt_i18n import list_prompt_templates, load_prompt
    text = load_prompt("person_fact_extract", locale=locale, person_name="TestUser", bot_name="DeepSeek",
                       chat_kind="private", user_evidence_text="evidence-canary", reply_text="reply-canary")
    assert all(value in text for value in ["TestUser", "DeepSeek", "private", "evidence-canary", "reply-canary"])
    meta = list_prompt_templates(locale=locale)["person_fact_extract"].metadata
    assert meta.display_name and meta.description
