#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import re
import requests
from datetime import datetime, timezone, timedelta

# --- 核心配置：直接硬编码防止环境变量干扰 ---
DASHBOARD_URL = 'https://dashboard.katabump.com'
SERVER_ID = '08549d19' 

# 从 GitHub Secrets 读取映射后的变量
KATA_EMAIL = os.environ.get('KATA_EMAIL', '')
KATA_PASSWORD = os.environ.get('KATA_PASSWORD', '')
TG_BOT_TOKEN = os.environ.get('TG_BOT_TOKEN', '')
TG_CHAT_ID = os.environ.get('TG_USER_ID', '')
S5_PROXY = os.environ.get('S5_PROXY', '')

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
    log(f'🚀 启动自检 | 目标服务器: {SERVER_ID}')
    
    # --- 关键诊断：检查 Secrets 是否成功传入 ---
    e_len = len(KATA_EMAIL) if KATA_EMAIL else 0
    p_len = len(KATA_PASSWORD) if KATA_PASSWORD else 0
    log(f'📊 诊断 -> 邮箱长度: {e_len} | 密码长度: {p_len} | 代理长度: {len(S5_PROXY) if S5_PROXY else 0}')

    if e_len == 0 or p_len == 0:
        log('❌ 严重错误：未能读取到账号或密码！请检查 GitHub Secrets 名字是否为 USER_EMAIL 和 USER_PASSWORD')
        return

    session = requests.Session()
    if S5_PROXY:
        session.proxies = {'http': S5_PROXY, 'https': S5_PROXY}
        log('🌐 已启用 SOCKS5 代理')

    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    })
    
    try:
        log('🔐 正在尝试登录...')
        # 增加超时时间以应对可能的网络波动
        session.get(f'{DASHBOARD_URL}/auth/login', timeout=45)
        
        login_resp = session.post(
            f'{DASHBOARD_URL}/auth/login',
            data={'email': KATA_EMAIL, 'password': KATA_PASSWORD, 'remember': 'true'},
            timeout=45,
            allow_redirects=True
        )
        
        # 检查是否撞到验证码
        if 'error=captcha' in login_resp.url:
            log('❌ 登录拦截：触发了人机验证码 (Captcha)。请更换代理 IP 或使用 Puppeteer 方案。')
            return
            
        if '/auth/login' in login_resp.url:
            log('❌ 登录失败：官网拒绝了账号密码。请检查密码是否包含特殊字符或有多余空格。')
            return

        log('✅ 登录成功！正在解析页面...')
        # 访问服务器详情页
        res = session.get(f'{DASHBOARD_URL}/server/{SERVER_ID}/', timeout=45)
        csrf = re.search(r'name="csrf" value="(.*?)"', res.text)
        csrf_token = csrf.group(1) if csrf else ''
        
        log('🔄 发送续订指令...')
        renew_url = f'{DASHBOARD_URL}/api-client/renew?id={SERVER_ID}'
        renew_resp = session.post(renew_url, data={'csrf': csrf_token}, timeout=45, allow_redirects=False)
        
        if renew_resp.status_code == 302 and 'success' in renew_resp.headers.get('Location', ''):
            log('🎉 续订成功！')
            send_telegram(f'✅ <b>KataBump 续订成功</b>\n🖥 服务器: <code>{SERVER_ID}</code>')
        else:
            log('⚠️ 续订未生效：可能尚未到续订时间，或 CSRF 校验失败。')
            
    except Exception as e:
        log(f'💥 运行崩溃: {e}')
        send_telegram(f'❌ <b>KataBump 运行出错</b>\n服务器: {SERVER_ID}\n错误: {e}')

if __name__ == '__main__':
    run()
