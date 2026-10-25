"""本人在官方 QQ 空间网页登录后，本地隐藏输入 Cookie；不会发送或打印凭据。"""
from getpass import getpass
from http.cookies import CookieError, SimpleCookie
from pathlib import Path

import argparse
import json
import os
import re
import tempfile
import tomllib

import tomlkit

ROOT = Path(__file__).resolve().parents[3]


def validate_cookie(raw: str, account: str) -> str:
    """只报告字段状态；不输出输入、账号值或凭据值。"""
    raw = raw.strip()
    if raw.lower().startswith('set-cookie:'):
        raise ValueError('复制的是响应 Set-Cookie；请复制 Request Headers 中完整的 Cookie 值。未保存。')
    if raw.lower().startswith('cookie:'):
        raw = raw.split(':', 1)[1].strip()
    if not raw or len(raw) > 16384 or '\n' in raw or '\r' in raw or '\t' in raw:
        raise ValueError('输入为空、过长或含多行/表格。请只复制同一个请求的 Cookie 值，不复制整份请求头。未保存。')
    if raw.startswith(('{', '[', '"', "'")):
        raise ValueError('输入看起来是 JSON、Cookie 表格或带外层引号的文本；请复制 Request Headers → Cookie 的值。未保存。')
    jar = SimpleCookie()
    try:
        jar.load(raw)
    except CookieError:
        raise ValueError('Cookie 格式无法解析；请复制 Request Headers 的完整 Cookie 值。未保存。') from None
    states = []
    for name in ['uin', 'p_uin', 'skey', 'p_skey']:
        states.append(name + ('=存在' if name in jar and jar[name].value else '=空' if name in jar else '=缺少'))
    print('本地字段检查（不显示值）：' + '；'.join(states))
    if not jar:
        raise ValueError('没有解析出 Cookie 字段。请复制完整的 name=value; name=value 格式，不是单个字段值或表格。未保存。')
    identities = {name: jar[name].value.lstrip('o0') for name in ['uin', 'p_uin'] if name in jar and jar[name].value}
    if not identities:
        raise ValueError('缺少用于核对账号的 uin/p_uin。可能复制了登录页或单个字段；请从 user.qzone.qq.com 的已登录空间请求复制完整 Cookie。未保存。')
    if len(set(identities.values())) > 1:
        raise ValueError('uin 与 p_uin 对应不同账号，可能混有另一 QQ 的浏览器会话。请用无痕窗口仅扫码登录机器人小号后重新复制；不要手动改 Cookie 中的 QQ 号。未保存。')
    wrong = [name for name, value in identities.items() if value != account]
    if wrong:
        raise ValueError('账号校验未通过：' + '/'.join(wrong) + ' 不属于配置中的机器人小号（尾号 ' + account[-4:] + '）。请确认网页登录的是小号，不是主人账号。未保存。')
    if 'p_skey' not in jar or not jar['p_skey'].value:
        named = bool(re.search(r'(?:^|;)\s*p_skey\s*=', raw))
        detail = '输入中出现 p_skey，但没有解析到非空值。' if named else '完整请求中没有 p_skey。'
        raise ValueError('账号身份匹配，但缺少有效空间票据 p_skey。' + detail + '请在登录成功的 user.qzone.qq.com 页面刷新，复制该域名请求的 Cookie；仅有 skey 不够。未保存。')
    return '; '.join(name + '=' + jar[name].value for name in ['uin', 'p_uin', 'skey', 'p_skey'] if name in jar)


def private_write(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix='.qzone-auth-')
    try:
        with os.fdopen(fd, 'w') as output:
            output.write(value)
        os.replace(temporary, path)
        path.chmod(0o600)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main(check_only: bool = False) -> None:
    config_path = ROOT / 'plugins/social_life_plugin/config.toml'
    config = tomllib.loads(config_path.read_text())
    account = config['access']['bot_account']
    print('请在官方 qzone.qq.com 使用机器人小号扫码登录浏览器；不要另开电脑版 QQ 登录。')
    print('登录成功后打开自己的空间；F12 → Network → 刷新，选 user.qzone.qq.com 请求的 Request Headers → Cookie。')
    print('不要复制登录页、Response Headers 的 Set-Cookie、表格或单个值。只在下方本地隐藏输入，不要发到聊天。')
    raw = getpass('QQ 空间 Cookie（隐藏输入）：').strip()
    selected = validate_cookie(raw, account)
    if check_only:
        print('本地格式和账号校验通过；未保存、未连接空间、未改动配置。')
        return
    # 只保留空间请求使用的四个字段，不保存其它站点的凭据。
    path = ROOT / 'data/MaiMBot-plugin-data/jycao.social-life/qzone-credentials.json'
    private_write(path, json.dumps({'account': account, 'cookies': selected}, ensure_ascii=False) + '\n')
    doc = tomlkit.parse(config_path.read_text())
    doc['qzone_auto']['credential_source'] = 'local_file'
    private_write(config_path, tomlkit.dumps(doc))
    print('已保存本机私有凭据（600），并明确选择 local_file 来源。没有解除暂停、连接空间或执行写入。')
    print('回到本地空间管理页做“只读检查连接”，通过后再“核实后恢复排期”。')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check-only', action='store_true', help='只检查格式和账号，不保存、不连接空间')
    args = parser.parse_args()
    try:
        main(check_only=args.check_only)
    except (CookieError, ValueError) as error:
        print(str(error))
        raise SystemExit(1) from None
