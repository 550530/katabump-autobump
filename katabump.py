#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KataBump 自动续订/提醒脚本（稳定版：放弃Cookie复用）
cron: 0 9,21 * * *
new Env('KataBump续订');
"""

import os
import sys
import re
import ssl
import requests
import time
from datetime import datetime, timezone, timedelta
from urllib3.poolmanager import PoolManager
from urllib3.contrib.socks import SOCKSProxyManager

# ========== 核心配置（严格匹配你的环境变量名） ==========
DASHBOARD_URL = 'https://dashboard.katabump.com'

# 原有环境变量配置（完全保留）
KATA_SERVER_ID = os.environ.get('KATA_SERVER_ID', '08549d19')
USER_EMAIL = os.environ.get('USER_EMAIL', '')
USER_PASSWORD = os.environ.get('USER_PASSWORD', '')
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '')
SOCKS5_PROXY = os.environ.get('SOCKS5_PROXY', '')  # 格式：socks5://用户名:密码@IP:端口
EXECUTOR_NAME = os.environ.get('EXECUTOR_NAME', 'https://ql.api.sld.tw')

def log(msg):
    """日志输出（带北京时间）"""
    tz = timezone(timedelta(hours=8))
    t = datetime.now(tz).strftime('%Y-%m-%d %H:%M:%S')
    print(f'[{t}] {msg}')

def send_telegram(message):
    """发送Telegram通知（适配Socks5代理）"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        log('⚠️ Telegram配置未完善，跳过通知')
        return False
    try:
        telegram_session = requests.Session()
        
        # Telegram通知适配Socks5代理
        if SOCKS5_PROXY:
            telegram_session.verify = False
            requests.packages.urllib3.disable_warnings()
            adapter = Socks5Adapter(SOCKS5_PROXY)
            telegram_session.mount('http://', adapter)
            telegram_session.mount('https://', adapter)
        
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

# 自定义Socks5适配器（修复SSL版本错误）
class Socks5Adapter(requests.adapters.HTTPAdapter):
    def __init__(self, proxy_url, **kwargs):
        self.proxy_url = proxy_url
        super().__init__(**kwargs)

    def init_poolmanager(self, connections, maxsize, block=False):
        if 'socks5' in self.proxy_url:
            self.poolmanager = SOCKSProxyManager(
                proxy_url=self.proxy_url,
                num_pools=connections,
                maxsize=maxsize,
                block=block,
                ssl_version=ssl.PROTOCOL_TLSv1_2
            )
        else:
            self.poolmanager = PoolManager(
                num_pools=connections,
                maxsize=maxsize,
                block=block
            )

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
        proxy_log = SOCKS5_PROXY.replace("://", "://***:@").split('@')[0] + '@***.***.***.***:' + SOCKS5_PROXY.split(':')[-1]
        log(f'🔌 使用 Socks5 代理: {proxy_log}')
    else:
        log('🔌 未配置 Socks5 代理')
    
    # 初始化请求会话
    session = requests.Session()
    
    # ========== 修复Socks5代理SSL错误 ==========
    session.verify = False
    requests.packages.urllib3.disable_warnings()
    
    # 配置Socks5代理适配器
    if SOCKS5_PROXY:
        adapter = Socks5Adapter(SOCKS5_PROXY)
        session.mount('http://', adapter)
        session.mount('https://', adapter)
    
    # 模拟真实浏览器请求头
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
        # ========== 直接走账号密码登录（核心修改：放弃Cookie复用） ==========
        log('🔐 开始账号密码登录...')
        # 先获取登录页Cookie（禁用重定向，避免提前循环）
        session.get(f'{DASHBOARD_URL}/auth/login', timeout=30, allow_redirects=False)
        # 模拟真人操作，延迟5秒提交（降低验证码概率）
        log('⏳ 模拟真人输入，延迟5秒提交登录请求...')
        time.sleep(5)
        
        # 提交登录请求（允许重定向，登录成功需要跳转）
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
        
        # 检查登录是否触发验证码
        if '/auth/login' in login_resp.url:
            log('⚠️ 登录触发验证码验证，无法自动登录')
            send_telegram(
                f'⚠️ KataBump 登录触发验证码\n\n'
                f'🖥 服务器 ID: <code>{KATA_SERVER_ID}</code>\n'
                f'🔌 代理状态: {"已使用" if SOCKS5_PROXY else "未使用"}\n'
                f'👉 <a href="{DASHBOARD_URL}/auth/login">点击手动登录验证</a>'
            )
            return
        else:
            log('✅ 账号密码登录成功！')
        
        # ========== 获取服务器信息（关键：限制重定向次数） ==========
        log('📄 获取服务器到期信息...')
        # 设置重定向次数限制为5次，避免无限循环
        session.max_redirects = 5
        server_page = session.get(
            f'{DASHBOARD_URL}/servers/edit?id={KATA_SERVER_ID}',
            timeout=30,
            allow_redirects=True
        )
        
        # 检查页面是否有效
        if server_page.status_code != 200:
            log(f'⚠️ 服务器页面响应异常: {server_page.status_code}')
            send_telegram(
                f'⚠️ KataBump 服务器页面访问异常\n\n'
                f'🖥 服务器 ID: <code>{KATA_SERVER_ID}</code>\n'
                f'📝 响应状态码: {server_page.status_code}\n'
                f'🔌 代理状态: {"已使用" if SOCKS5_PROXY else "未使用"}'
            )
            return
        
        # 提取服务器信息
        expiry_date = get_expiry(server_page.text) or '未知'
        remaining_days = days_until(expiry_date)
        csrf_token = get_csrf(server_page.text)
        
        log(f'📅 服务器到期时间: {expiry_date} (剩余 {remaining_days} 天)')
        
        # 检查续订限制
        renew_error, renew_date = parse_renew_error(server_page.url)
        if renew_error:
            log(f'⏳ 续订限制: {renew_error}')
            send_telegram(
                f'ℹ️ KataBump 续订提醒\n\n'
                f'🖥 服务器 ID: <code>{KATA_SERVER_ID}</code>\n'
                f'📅 到期时间: {expiry_date}\n'
                f'⏰ 剩余天数: {remaining_days} 天\n'
                f'📝 续订限制: {renew_error}\n'
                f'🔌 代理状态: {"已使用" if SOCKS5_PROXY else "未使用"}'
            )
            return
        
        # ========== 尝试续订 ==========
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
                    f'✅ KataBump 续订成功！\n\n'
                    f'🖥 服务器 ID: <code>{KATA_SERVER_ID}</code>\n'
                    f'📅 原到期时间: {expiry_date}\n'
                    f'📅 新到期时间: {new_expiry}\n'
                    f'🔌 代理状态: {"已使用" if SOCKS5_PROXY else "未使用"}'
                )
                return
            
            # 续订需要验证码
            elif 'error=captcha' in location:
                log('❌ 续订触发验证码验证')
                send_telegram(
                    f'⚠️ KataBump 续订触发验证码\n\n'
                    f'🖥 服务器 ID: <code>{KATA_SERVER_ID}</code>\n'
                    f'📅 到期时间: {expiry_date}\n'
                    f'🔌 代理状态: {"已使用" if SOCKS5_PROXY else "未使用"}\n'
                    f'👉 <a href="{DASHBOARD_URL}/servers/edit?id={KATA_SERVER_ID}">点击手动续订验证</a>'
                )
                return
            
            # 其他续订错误
            elif 'renew-error' in location:
                error_msg, _ = parse_renew_error(location)
                log(f'❌ 续订失败: {error_msg}')
                send_telegram(
                    f'❌ KataBump 续订失败\n\n'
                    f'🖥 服务器 ID: <code>{KATA_SERVER_ID}</code>\n'
                    f'📅 到期时间: {expiry_date}\n'
                    f'📝 失败原因: {error_msg}\n'
                    f'🔌 代理状态: {"已使用" if SOCKS5_PROXY else "未使用"}'
                )
                return
        
        # 最终验证续订结果
        check_page = session.get(f'{DASHBOARD_URL}/servers/edit?id={KATA_SERVER_ID}', timeout=30)
        new_expiry = get_expiry(check_page.text) or '未知'
        if new_expiry > expiry_date:
            log(f'🎉 续订成功！新到期时间: {new_expiry}')
            send_telegram(
                f'✅ KataBump 续订成功！\n\n'
                f'🖥 服务器 ID: <code>{KATA_SERVER_ID}</code>\n'
                f'📅 原到期时间: {expiry_date}\n'
                f'📅 新到期时间: {new_expiry}\n'
                f'🔌 代理状态: {"已使用" if SOCKS5_PROXY else "未使用"}'
            )
        else:
            log('⚠️ 续订状态未知，未检测到到期时间变化')
            send_telegram(
                f'⚠️ KataBump 续订状态未知\n\n'
                f'🖥 服务器 ID: <code>{KATA_SERVER_ID}</code>\n'
                f'📅 当前到期时间: {new_expiry}\n'
                f'🔌 代理状态: {"已使用" if SOCKS5_PROXY else "未使用"}\n'
                f'👉 <a href="{DASHBOARD_URL}/servers/edit?id={KATA_SERVER_ID}">手动检查续订状态</a>'
            )
    
    except requests.exceptions.TooManyRedirects:
        log('❌ 脚本执行出错: 重定向次数过多（服务器会话异常）')
        send_telegram(
            f'❌ KataBump 重定向次数过多\n\n'
            f'🖥 服务器 ID: <code>{KATA_SERVER_ID}</code>\n'
            f'📝 错误原因: 服务器会话异常（IP/代理不匹配）\n'
            f'🔌 代理状态: {"已使用" if SOCKS5_PROXY else "未使用"}\n'
            f'👉 建议：更换代理IP或手动登录一次'
        )
    except Exception as e:
        log(f'❌ 脚本执行出错: {str(e)}')
        send_telegram(
            f'❌ KataBump 脚本执行出错\n\n'
            f'🖥 服务器 ID: <code>{KATA_SERVER_ID}</code>\n'
            f'❗ 错误信息: <code>{str(e)}</code>\n'
            f'🔌 代理状态: {"已使用" if SOCKS5_PROXY else "未使用"}'
        )
        raise

def main():
    """脚本入口"""
    log('=' * 50)
    log('   KataBump 自动续订/提醒脚本（稳定版）')
    log('=' * 50)
    
    # 检查核心配置
    if not USER_EMAIL or not USER_PASSWORD:
        log('❌ 请配置 USER_EMAIL 和 USER_PASSWORD 环境变量')
        sys.exit(1)
    
    # 检查代理格式
    if SOCKS5_PROXY and not SOCKS5_PROXY.startswith('socks5://'):
        log('❌ Socks5代理格式错误！正确格式：socks5://用户名:密码@IP:端口')
        sys.exit(1)
    
    # 执行核心逻辑
    run()
    log('🏁 脚本执行完成')

if __name__ == '__main__':
    main()
