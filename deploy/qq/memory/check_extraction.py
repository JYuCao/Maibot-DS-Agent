"""用合成私聊验证实际提取模型；不写入事实、不发送 QQ，调用一次现有 Utils API。"""
from types import SimpleNamespace

import asyncio
import json

from src.config.config import global_config
from src.services.memory_flow_service import PersonFactWritebackService
from src.services.person_fact_policy import direct_person_statement


async def main() -> None:
    source = '我给你部署了MaiBot。'
    service = PersonFactWritebackService()
    user = SimpleNamespace(person_name='测试用户', nickname='测试用户', person_id='synthetic-no-write')
    items = await service._extract_facts(user, '本鲸收到啦。',
        '目标用户原始发言（事实值必须来自这里）：\n- [消息ID: synthetic-no-write] ' + source, private=True)
    verified = [direct_person_statement(item.get('evidence_quote',''), source,
                person_name='测试用户',bot_name=global_config.bot.nickname,private=True)
                for item in items if item.get('evidence_message_id')=='synthetic-no-write']
    assert verified and all(value and global_config.bot.nickname in value and '对方' not in value for value in verified)
    print('MEMORY_FIX_CHECK ' + json.dumps({'success':True,'canonical_synthetic_facts':verified,
          'facts_written':0,'qq_messages_sent':0},ensure_ascii=False))


if __name__ == '__main__':
    asyncio.run(main())
