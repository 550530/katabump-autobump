#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KataBump 自动续订/提醒脚本
cron: 0 9,21 * * *
new Env('KataBump续订');
"""

import os
import sys
import re
import requests
import time  # 新增：导入时间模块用于延迟
from datetime import datetime, timezone, timedelta

# ========== 核心配置（严格匹配你的环境变量名） ==========
DASHBOARD_URL = 'https://dashboard.katabump.com'
KATA_SERVER_ID = os.environ.get('KATA_SERVER_ID', '08549d19')
USER_EMAIL = os.environ.get('USER_EMAIL', '')
USER_PASSWORD = os.environ.get('USER_PASSWORD', '')
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '')
SOCKS5_PROXY = os.environ.get('SOCKS5_PROXY', '')
EXECUTOR_NAME = os.environ.get('EXECUTOR_NAME', 'https://ql.api.sld.tw')

def log(msg):
    """日志输出（带北京时间）"""
    tz = timezone(timedelta(hours=8))
    t = datetime.now(tz).strftime('%Y-%m-%d %H:%M:%S')
    print(f'[{t}] {msg}')

def send_telegram(message):
    """发送Telegram通知（可选走代理）"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        log('⚠️ Telegram配置未完善，跳过通知')
        return False
    try:
        telegram_session = requests.Session()
        if SOCKS5_PROXY:
            telegram_session.proxies = {
                'http': SOCKS5_PROXY,
                'https': SOCKS5_PROXY
            }
        telegram_session.post(
            f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage',
            json={'chat_id': TELEGRAM_CHAT_ID, 'text': message, 'parse_mode': 'HTML'},
            timeout=30
        )
        log('✅ Telegram 通知已发送')
        return True
    except Exception as e:
        log(f'❌ Telegram 发送失败: {e}')
    return False

def get_expiry(html):
    """从页面提取到期日期"""
    match = re.search(r'Expiry[\s\S]*?(\d{4}-\d{2}-\d{2})', html, re.IGNORECASE)
    return match.group(1) if match else None

def get_csrf(html):
    """从页面提取CSRF令牌"""
    patterns = [
        r'<input[^>]*name=["\']csrf["\'][^>]*value=["\']([^"\']+)["\']',
        r'<input[^>]*value=["\']([^"\']+)["\'][^>]*name=["\']csrf["\']',
    ]
    for p in patterns:
        m = re.search(p, html, re.IGNORECASE)
        if m and len(m.group(1)) > 10:
            return m.group(1)
    return None

def days_until(date_str):
    """计算距离到期的天数"""
    try:
        exp = datetime.strptime(date_str, '%Y-%m-%d')
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        return (exp - today).days
    except:
        return None

def parse_renew_error(url):
    """解析续订错误信息"""
    if 'renew-error' not in url:
        return None, None
    
    error_match = re.search(r'renew-error=([^&]+)', url)
    if not error_match:
        return '未知错误', None
    
    error = requests.utils.unquote(error_match.group(1).replace('+', ' '))
    date_match = re.search(r'as of (\d+) (\w+)', error)
    if date_match:
        day = date_match.group(1)
        month = date_match.group(2)
        return error, f'{month} {day}'
    
    return error, None

def run():
    """核心执行逻辑"""
    log('🚀 KataBump 自动续订/提醒脚本启动')
    log(f'🖥 服务器 ID: {KATA_SERVER_ID}')
    
    # 代理状态日志（脱敏显示）
    if SOCKS5_PROXY:
        proxy_log = SOCKS5_PROXY.replace("://", "://***:@") if "@" in SOCKS5_PROXY else SOCKS5_PROXY
        log(f'🔌 使用 Socks5 代理: {proxy_log}')
    else:
        log('🔌 未配置 Socks5 代理')
    
    # 初始化请求会话
    session = requests.Session()
    if SOCKS5_PROXY:
        session.proxies = {
            'http': SOCKS5_PROXY,
            'https': SOCKS5_PROXY
        }
# 模拟更真实的浏览器请求头（降低验证码触发概率）
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
    'Accept-Language': 'en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7',
    'Accept-Encoding': 'gzip, deflate, br',
    'Referer': 'https://dashboard.katabump.com/',
    'DNT': '1',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'same-origin',
    'Sec-Fetch-User': '?1',
    'Upgrade-Insecure-Requests': '1',
    'Cache-Control': 'max-age=0'
})

    try:
        # ========== 步骤1：登录（含5秒延迟） ==========
        log('🔐 开始登录...')
        # 先获取登录页Cookie
        session.get(f'{DASHBOARD_URL}/auth/login', timeout=30)
        
        # 核心修改：模拟真人操作，延迟5秒提交登录
        log('⏳ 模拟真人输入，延迟5秒提交登录请求...')
        time.sleep(5)  # 5秒延迟
        
        # 提交登录请求
        login_resp = session.post(
            f'{DASHBOARD_URL}/auth/login',
            data={
                'email': USER_EMAIL,
                'password': USER_PASSWORD,
                'remember': 'true'
            },
            headers={
                'Content-Type': 'application/x-www-form-urlencoded',
                'Origin': DASHBOARD_URL,
                'Referer': f'{DASHBOARD_URL}/auth/login',
            },
            timeout=30,
            allow_redirects=True
        )
        
        log(f'📍 登录后跳转URL: {login_resp.url}')
        log(f'🍪 登录后Cookie: {list(session.cookies.keys())}')
        
        # 登录状态判断（区分验证码和真失败）
        if '/auth/login' in login_resp.url:
            if 'error=captcha' in login_resp.url:
                log('⚠️ 登录触发验证码验证，无法自动登录')
                send_telegram(
                    f'⚠️ KataBump 需要手动验证\n\n'
                    f'🖥 服务器: <code>{KATA_SERVER_ID}</code>\n'
                    f'❗ 登录时触发了验证码验证，请手动登录完成验证\n'
                    f'🔌 代理状态: {"已使用" if SOCKS5_PROXY else "未使用"}\n'
                    f'💻 执行器: {EXECUTOR_NAME}\n\n'
                    f'👉 <a href="{DASHBOARD_URL}/auth/login">点击手动登录</a>'
                )
                return
            else:
                raise Exception('登录失败（账号/密码错误或其他原因）')
        
        log('✅ 登录成功')
        
        # ========== 步骤2：获取服务器信息 ==========
        log('📄 获取服务器到期信息...')
        server_page = session.get(f'{DASHBOARD_URL}/servers/edit?id={KATA_SERVER_ID}', timeout=30)
        expiry_date = get_expiry(server_page.text) or '未知'
        remaining_days = days_until(expiry_date)
        csrf_token = get_csrf(server_page.text)
        
        log(f'📅 服务器到期时间: {expiry_date} (剩余 {remaining_days} 天)')
        
        # 检查续订限制
        renew_error, renew_date = parse_renew_error(server_page.url)
        if renew_error:
            log(f'⏳ 续订限制: {renew_error}')
            if remaining_days is not None and remaining_days <= 2:
                send_telegram(
                    f'ℹ️ KataBump 续订提醒\n\n'
                    f'🖥 服务器: <code>{KATA_SERVER_ID}</code>\n'
                    f'📅 到期时间: {expiry_date}\n'
                    f'⏰ 剩余天数: {remaining_days} 天\n'
                    f'📝 续订限制: {renew_error}\n'
                    f'🔌 代理状态: {"已使用" if SOCKS5_PROXY else "未使用"}\n'
                    f'💻 执行器: {EXECUTOR_NAME}\n\n'
                    f'👉 <a href="{DASHBOARD_URL}/servers/edit?id={KATA_SERVER_ID}">查看详情</a>'
                )
            return
        
        # ========== 步骤3：尝试续订 ==========
        if not csrf_token:
            log('❌ 未获取到CSRF令牌，跳过续订')
            return
        
        log('🔄 尝试自动续订...')
        renew_resp = session.post(
            f'{DASHBOARD_URL}/api-client/renew?id={KATA_SERVER_ID}',
            data={'csrf': csrf_token},
            headers={
                'Content-Type': 'application/x-www-form-urlencoded',
                'Origin': DASHBOARD_URL,
                'Referer': f'{DASHBOARD_URL}/servers/edit?id={KATA_SERVER_ID}'
            },
            timeout=30,
            allow_redirects=False
        )
        
        log(f'📥 续订请求状态码: {renew_resp.status_code}')
        
        # 处理续订响应
        if renew_resp.status_code == 302:
            location = renew_resp.headers.get('Location', '')
            log(f'📍 续订跳转URL: {location}')
            
            # 续订成功
            if 'renew=success' in location:
                check_page = session.get(f'{DASHBOARD_URL}/servers/edit?id={KATA_SERVER_ID}', timeout=30)
                new_expiry = get_expiry(check_page.text) or '未知'
                log(f'🎉 续订成功！新到期时间: {new_expiry}')
                send_telegram(
                    f'✅ KataBump 续订成功\n\n'
                    f'🖥 服务器: <code>{KATA_SERVER_ID}</code>\n'
                    f'📅 原到期时间: {expiry_date}\n'
                    f'📅 新到期时间: {new_expiry}\n'
                    f'🔌 代理状态: {"已使用" if SOCKS5_PROXY else "未使用"}\n'
                    f'💻 执行器: {EXECUTOR_NAME}'
                )
                return
            
            # 续订需要验证码
            elif 'error=captcha' in location:
                log('❌ 续订触发验证码验证')
                if remaining_days is not None and remaining_days <= 2:
                    send_telegram(
                        f'⚠️ KataBump 需要手动续订\n\n'
                        f'🖥 服务器: <code>{KATA_SERVER_ID}</code>\n'
                        f'📅 到期时间: {expiry_date}\n'
                        f'⏰ 剩余天数: {remaining_days} 天\n'
                        f'❗ 续订需要验证码验证\n'
                        f'🔌 代理状态: {"已使用" if SOCKS5_PROXY else "未使用"}\n'
                        f'💻 执行器: {EXECUTOR_NAME}\n\n'
                        f'👉 <a href="{DASHBOARD_URL}/servers/edit?id={KATA_SERVER_ID}">点击手动续订</a>'
                    )
                return
            
            # 其他续订错误
            elif 'renew-error' in location:
                error_msg, _ = parse_renew_error(location)
                log(f'❌ 续订失败: {error_msg}')
                if remaining_days is not None and remaining_days <= 2:
                    send_telegram(
                        f'ℹ️ KataBump 续订提醒\n\n'
                        f'🖥 服务器: <code>{KATA_SERVER_ID}</code>\n'
                        f'📅 到期时间: {expiry_date}\n'
                        f'⏰ 剩余天数: {remaining_days} 天\n'
                        f'📝 续订失败原因: {error_msg}\n'
                        f'🔌 代理状态: {"已使用" if SOCKS5_PROXY else "未使用"}\n'
                        f'💻 执行器: {EXECUTOR_NAME}\n\n'
                        f'👉 <a href="{DASHBOARD_URL}/servers/edit?id={KATA_SERVER_ID}">查看详情</a>'
                    )
                return
        
        # 最终验证续订结果
        check_page = session.get(f'{DASHBOARD_URL}/servers/edit?id={KATA_SERVER_ID}', timeout=30)
        new_expiry = get_expiry(check_page.text) or '未知'
        if new_expiry > expiry_date:
            log(f'🎉 续订成功！新到期时间: {new_expiry}')
            send_telegram(
                f'✅ KataBump 续订成功\n\n'
                f'🖥 服务器: <code>{KATA_SERVER_ID}</code>\n'
                f'📅 原到期时间: {expiry_date}\n'
                f'📅 新到期时间: {new_expiry}\n'
                f'🔌 代理状态: {"已使用" if SOCKS5_PROXY else "未使用"}\n'
                f'💻 执行器: {EXECUTOR_NAME}'
            )
        else:
            log('⚠️ 续订状态未知，未检测到到期时间变化')
            if remaining_days is not None and remaining_days <= 2:
                send_telegram(
                    f'⚠️ KataBump 请检查续订状态\n\n'
                    f'🖥 服务器: <code>{KATA_SERVER_ID}</code>\n'
                    f'📅 当前到期时间: {new_expiry}\n'
                    f'⏰ 剩余天数: {remaining_days} 天\n'
                    f'🔌 代理状态: {"已使用" if SOCKS5_PROXY else "未使用"}\n'
                    f'💻 执行器: {EXECUTOR_NAME}\n\n'
                    f'👉 <a href="{DASHBOARD_URL}/servers/edit?id={KATA_SERVER_ID}">手动检查</a>'
                )
    
    except Exception as e:
        log(f'❌ 脚本执行出错: {str(e)}')
        send_telegram(
            f'❌ KataBump 脚本执行出错\n\n'
            f'🖥 服务器: <code>{KATA_SERVER_ID}</code>\n'
            f'❗ 错误信息: {str(e)}\n'
            f'🔌 代理状态: {"已使用" if SOCKS5_PROXY else "未使用"}\n'
            f'💻 执行器: {EXECUTOR_NAME}'
        )
        raise

def main():
    """脚本入口"""
    log('=' * 50)
    log('   KataBump 自动续订/提醒脚本')
    log('=' * 50)
    
    # 检查核心配置
    if not USER_EMAIL or not USER_PASSWORD:
        log('❌ 请配置 USER_EMAIL 和 USER_PASSWORD 环境变量')
        sys.exit(1)
    
    # 执行核心逻辑
    run()
    log('🏁 脚本执行完成')

if __name__ == '__main__':
    main()
