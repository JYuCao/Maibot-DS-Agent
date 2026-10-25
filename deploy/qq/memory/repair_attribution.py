"""预览/补齐已确认的管理员私聊摘要归属；不修改正文、向量、群聊或删除状态。"""
from pathlib import Path
from typing import Any, Dict

import argparse
import hashlib
import json
import os
import sqlite3
import subprocess
import time
import tomllib

ROOT = Path(__file__).resolve().parents[3]
MEMORY = ROOT / 'data/MaiMBot/a-memorix/metadata/metadata.db'
MAIN = ROOT / 'data/MaiMBot/MaiBot.db'


def private_json(path: Path, value: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as output:
        json.dump(value, output, ensure_ascii=False, indent=2)
        output.write('\n')


def preview() -> Dict[str, Any]:
    config = tomllib.loads((ROOT / 'plugins/social_life_plugin/config.toml').read_text())
    owner = config['access']['administrator']
    changes, skipped = [], []
    with sqlite3.connect(MEMORY.as_uri() + '?mode=ro', uri=True) as memory, sqlite3.connect(MAIN.as_uri() + '?mode=ro', uri=True) as main:
        memory.row_factory = main.row_factory = sqlite3.Row
        for paragraph in memory.execute('SELECT * FROM paragraphs WHERE COALESCE(is_deleted,0)=0'):
            meta = json.loads(paragraph['metadata'] or '{}')
            if meta.get('source_type') != 'chat_summary' or meta.get('person_ids'):
                continue
            sid = meta.get('chat_id', '')
            sessions = main.execute('SELECT * FROM chat_sessions WHERE session_id=?', (sid,)).fetchall()
            if len(sessions) != 1 or sessions[0]['group_id'] or sessions[0]['platform'] != 'qq' or sessions[0]['user_id'] != owner:
                skipped.append({'paragraph': paragraph['hash'], 'reason': 'not_verified_owner_private_session'})
                continue
            persons = main.execute('SELECT * FROM person_info WHERE platform=? AND user_id=? AND is_known=1', ('qq', owner)).fetchall()
            if len(persons) != 1:
                skipped.append({'paragraph': paragraph['hash'], 'reason': 'person_identity_not_unique'})
                continue
            person = persons[0]
            name = person['person_name'] or person['user_nickname']
            if not name or name.casefold() not in paragraph['content'].casefold():
                skipped.append({'paragraph': paragraph['hash'], 'reason': 'no_explicit_person_reference_in_summary'})
                continue
            after = {**meta, 'person_ids': [person['person_id']], 'participants': [name],
                     'identity_binding_repair': {'method': 'verified_private_session_and_named_summary', 'version': 1}}
            changes.append({'paragraph': paragraph['hash'], 'content_sha256': hashlib.sha256(paragraph['content'].encode()).hexdigest(),
                            'content_preview': paragraph['content'][:500], 'before_metadata': paragraph['metadata'], 'after_metadata': after})
    return {'version': 1, 'created': time.time(), 'changes': changes, 'skipped': skipped}


def apply(path: Path) -> None:
    state = subprocess.run(['docker', 'inspect', 'maibot-qq-core-1', '--format', '{{.State.Status}}'], capture_output=True, text=True, check=True).stdout.strip()
    if state != 'exited':
        raise RuntimeError('须先停止 core，避免与运行时缓存和写入并发；不需要停止 NapCat')
    plan = json.loads(path.read_text())
    with sqlite3.connect(MEMORY.as_uri() + '?mode=rw', uri=True) as db:
        db.row_factory = sqlite3.Row
        db.execute('BEGIN IMMEDIATE')
        for change in plan['changes']:
            current = db.execute('SELECT * FROM paragraphs WHERE hash=?', (change['paragraph'],)).fetchone()
            if not current or current['is_deleted'] or current['metadata'] != change['before_metadata'] or hashlib.sha256(current['content'].encode()).hexdigest() != change['content_sha256']:
                raise RuntimeError('数据在预览后发生变化；已取消整笔修复，请重新生成预览')
            db.execute('UPDATE paragraphs SET metadata=?,updated_at=? WHERE hash=?',
                       (json.dumps(change['after_metadata'], ensure_ascii=False), time.time(), change['paragraph']))
            pid = change['after_metadata']['person_ids'][0]
            db.execute("""INSERT INTO person_profile_refresh_queue(person_id,status,reason,source_query_tool_id,retry_count,last_error,requested_at,updated_at)
                          VALUES(?,'pending','verified_summary_identity_repair','',0,'',?,?)
                          ON CONFLICT(person_id) DO UPDATE SET status='pending',reason=excluded.reason,retry_count=0,last_error='',requested_at=excluded.requested_at,updated_at=excluded.updated_at""", (pid, time.time(), time.time()))
    private_json(path.with_name(path.stem + '-applied.json'), {'applied_at': time.time(), 'count': len(plan['changes']), 'changes': plan['changes']})
    print('Applied verified private-summary attribution:', len(plan['changes']), '; original content and deleted records preserved.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preview', type=Path)
    parser.add_argument('--apply', type=Path)
    args = parser.parse_args()
    if bool(args.preview) == bool(args.apply):
        parser.error('指定 --preview 或 --apply 二者之一')
    if args.preview:
        plan = preview()
        private_json(args.preview, plan)
        print('Preview candidates:', len(plan['changes']), '; skipped:', len(plan['skipped']), '; full preview saved privately:', args.preview)
    else:
        apply(args.apply)
