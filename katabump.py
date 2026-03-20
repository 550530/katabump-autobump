#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import re
import requests
from datetime import datetime, timezone, timedelta

# --- 核心配置 ---
DASHBOARD_URL = 'https://dashboard.katabump.com'
SERVER_ID = '08549d19' 

# 从环境变量读取配置
KATA_EMAIL = os.environ.get('KATA_EMAIL', '')
KATA_PASSWORD = os.environ.get('KATA_PASSWORD', '')
TG_BOT_TOKEN = os.environ.get('TG_BOT_TOKEN', '')
TG_CHAT_ID = os.environ.get('TG_USER_ID', '')
S5_PROXY = os.environ.get('S5_PROXY', '') # 格式: socks5://user:pass@host:port

def log(msg):
    tz = timezone(timedelta(hours=8))
    t = datetime.now(tz).strftime('%Y-%m-%d %H:%M:%S')
    print(f'[{t}] {msg}')

def send_telegram(message):
    if not TG_BOT_TOKEN or not TG_CHAT_ID: return
    try:
        requests.post(f'https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage',
                     json={'chat_id': TG_CHAT_ID, 'text': message, 'parse_mode': 'HTML'}, timeout=30)
        log('✅ Telegram 通知已发送')
    except Exception as e: log(f'❌ TG 发送失败: {e}')

def run():
    log('🚀 开始 KataBump 自动续订 (代理模式)')
    session = requests.Session()
    
    # 启用 SOCKS5 代理
    if S5_PROXY:
        session.proxies = {'http': S5_PROXY, 'https': S5_PROXY}
        log(f'🌐 已启用代理: {S5_PROXY[:10]}***')

    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    })
    
    try:
        log('🔐 正在登录...')
        session.get(f'{DASHBOARD_URL}/auth/login', timeout=45)
        
        login_resp = session.post(
            f'{DASHBOARD_URL}/auth/login',
            data={'email': KATA_EMAIL, 'password': KATA_PASSWORD, 'remember': 'true'},
            timeout=45,
            allow_redirects=True
        )
        
        # 检查是否依然被验证码拦截
        if 'error=captcha' in login_resp.url:
            log('❌ 依然被拦截：当前代理 IP 仍触发了验证码。建议更换代理节点。')
            return
            
        if '/auth/login' in login_resp.url:
            log('❌ 登录失败：请确认 Secrets 中的账号密码。')
            return

        log('✅ 登录成功！正在检测服务器状态...')
        # 访问服务器页面获取 CSRF
        res = session.get(f'{DASHBOARD_URL}/server/{SERVER_ID}/', timeout=45)
        csrf = re.search(r'name="csrf" value="(.*?)"', res.text)
        csrf_token = csrf.group(1) if csrf else ''
        
        log('🔄 提交续订请求...')
        renew_url = f'{DASHBOARD_URL}/api-client/renew?id={SERVER_ID}'
        renew_resp = session.post(renew_url, data={'csrf': csrf_token}, timeout=45, allow_redirects=False)
        
        if renew_resp.status_code == 302 and 'success' in renew_resp.headers.get('Location', ''):
            log('🎉 续订成功！')
            send_telegram(f'✅ <b>KataBump 续订成功</b>\n🖥 服务器: {SERVER_ID}')
        else:
            log('⚠️ 续订未生效，可能还未到续订时间。')
            
    except Exception as e:
        log(f'💥 出错: {e}')
        send_telegram(f'❌ <b>KataBump 运行出错</b>\n{e}')

if __name__ == '__main__':
    run()
