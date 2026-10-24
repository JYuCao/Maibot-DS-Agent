"""以可定位的用户直接自述构造事实，不把模型改写当成证据。"""

from typing import Optional

import re
import unicodedata


_AMBIGUOUS = re.compile(r"对方|另一方|我们|你们|您们|[\"“”‘’「」『』？?]|(?:他|她|别人|朋友|你|您)说|如果|假如|比如|我觉得|我猜|我以为")
_TEMPORARY = re.compile(r"正在|暂时|今天|明天|刚才|现在|目前|打算|计划|准备|也许|可能|好像|之类")
_OTHER_SUBJECTS = ("我们", "我朋友", "我的朋友", "我同事", "我的同事", "我爸", "我妈", "我的家人")


def direct_person_statement(quote: str, source: str, *, person_name: str,
                            bot_name: str, private: bool) -> Optional[str]:
    """保守接受明确自述；引用、假设、临时活动和群聊不明受话者不晋升稳定事实。"""
    quote = quote.strip()
    if not quote or quote not in source or quote.startswith(_OTHER_SUBJECTS):
        return None
    # 同一原句的前后限定不可被一个短引用删掉，例如“我不喜欢...”、“如果我...”。
    start = source.index(quote)
    before = re.split(r"[。！？；\n]", source[:start])[-1].strip()
    after = re.split(r"[。！？；\n]", source[start + len(quote):])[0].strip()
    if source[start + len(quote):].lstrip().startswith(("?", "？")):
        return None
    if before or after.strip("，,、 ") or _AMBIGUOUS.search(quote) or _TEMPORARY.search(quote):
        return None
    prefix = next((word for word in ("本人", "自己", "我") if quote.startswith(word)), None)
    if prefix is None:
        return None
    text = quote[len(prefix):].strip().rstrip("。！；")
    if not text or (not private and re.search(r"你|您", text)):
        return None
    # 此处只处理已排除引述/转述的私聊直接自述，不能用于全局替换聊天中的“你”。
    if private:
        text = re.sub(r"你|您", lambda _: bot_name, text)
    return person_name + text


def statement_key(text: str) -> str:
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", text).casefold()).rstrip("。！；")
