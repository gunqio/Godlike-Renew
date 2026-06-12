import os
import time
import signal
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from datetime import datetime

# ==================== 配置项 ====================
SERVER_URL = "https://ultra.panel.godlike.host/server/dc3b034c"
LOGIN_URL = "https://ultra.panel.godlike.host/login"
COOKIE_NAME = "remember_web_59ba36addc2b2f9401580f014c7f58ea4e30989d"

# 超时配置（秒）
TASK_TIMEOUT_SECONDS = 300    # 全局任务超时 5 分钟
AD_WAIT_SECONDS = 120         # 广告观看等待时长 2 分钟
DEFAULT_PAGE_TIMEOUT = 60000  # 页面默认超时 60 秒

IS_WINDOWS = os.name == "nt"

# ==================== 自定义异常 & 超时信号 ====================
class TaskTimeoutError(Exception):
    """自定义任务超时异常"""
    pass

def timeout_handler(signum, frame):
    raise TaskTimeoutError("任务执行超出最大时长限制")

# 仅非 Windows 注册信号
if not IS_WINDOWS:
    signal.signal(signal.SIGALRM, timeout_handler)

# ==================== 登录逻辑 ====================
def login_with_playwright(page):
    """优先Cookie登录，失败则账号密码登录"""
    cookie_val = os.environ.get("PTERODACTYL_COOKIE", "")
    email = os.environ.get("PTERODACTYL_EMAIL", "")
    pwd = os.environ.get("PTERODACTYL_PASSWORD", "")

    if cookie_val:
        print("🔑 检测到 Cookie，尝试免密登录...")
        cookie = {
            "name": COOKIE_NAME,
            "value": cookie_val,
            "domain": ".ultra.panel.godlike.host",
            "path": "/",
            "secure": True,
            "httpOnly": True,
            "sameSite": "Lax"
        }
        page.context.add_cookies([cookie])
        page.goto(SERVER_URL, wait_until="domcontentloaded")

        if "login" in page.url or "auth/login" in page.url:
            print("❌ Cookie 失效，切换账号密码登录")
            page.context.clear_cookies()
        else:
            print("✅ Cookie 登录成功")
            return True

    if not (email and pwd):
        print("❌ 缺少账号密码环境变量，无法登录")
        return False

    print("🔐 使用账号密码登录...")
    page.goto(LOGIN_URL, wait_until="domcontentloaded")
    try:
        # 🔴 关键修复：用正则兼容大小写和格式变化
        print("正在点击 'Through Login/Password' 按钮...")
        page.locator('a:has-text(/Through.*login\/password/i)').click(timeout=20000)
        
        # 等待登录表单加载
        print("等待登录表单元素加载...")
        email_selector = 'input[name="username"]'
        password_selector = 'input[name="password"]'
        login_button_selector = 'button[type="submit"]:has-text("Login")'
        
        page.wait_for_selector(email_selector, timeout=30000)
        page.wait_for_selector(password_selector, timeout=30000)
        
        print("正在填写邮箱和密码...")
        page.fill(email_selector, email)
        page.fill(password_selector, pwd)
        
        print("正在点击登录按钮...")
        with page.expect_navigation(wait_until="domcontentloaded"):
            page.click(login_button_selector)

        if "login" in page.url:
            print("❌ 账号密码登录失败，可能是凭据错误")
            page.screenshot(path="login_fail.png")
            return False
        print("✅ 账号密码登录成功")
        return True
    except Exception as e:
        print(f"❌ 登录异常: {str(e)}")
        page.screenshot(path="login_error.png")
        return False

# ==================== 续时核心任务 ====================
def add_time_task(page):
    """执行增加时长 + 看广告流程"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n[{now}] ⏳ 开始执行续时任务")

    # 确保在目标页面
    if page.url.strip() != SERVER_URL.strip():
        print(f"🔄 跳转至服务器页面: {SERVER_URL}")
        page.goto(SERVER_URL, wait_until="domcontentloaded")

    try:
        # 1. 点击 Add 90 minutes
        add_btn = page.locator('button:has-text("Add 90 minutes")')
        add_btn.wait_for(state="visible", timeout=30000)
        add_btn.click()
        print("✅ 点击 Add 90 minutes")

        # 2. 点击 Watch advertisement
        ad_btn = page.locator('button:has-text("Watch advertisement")')
        ad_btn.wait_for(state="visible", timeout=30000)
        ad_btn.click()
        print("✅ 点击 Watch advertisement，开始等待广告")

        # 3. 固定等待广告时长
        time.sleep(AD_WAIT_SECONDS)
        now_end = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{now_end}] ✅ 广告等待完成，本轮续时结束")
        return True

    except PlaywrightTimeoutError:
        print("❌ 元素加载超时，页面结构可能变更")
        page.screenshot(path="task_timeout.png")
        return False
    except Exception as e:
        print(f"❌ 任务未知异常: {str(e)}")
        page.screenshot(path="task_error.png")
        return False

# ==================== 主入口 ====================
def main():
    print("================ 启动自动化续时脚本 ================")
    with sync_playwright() as p:
        # 启动浏览器，增加防风控和无头环境适配
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled"
            ]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        page.set_default_timeout(DEFAULT_PAGE_TIMEOUT)
        print("✅ 浏览器启动完成")

        try:
            # 登录
            if not login_with_playwright(page):
                exit(1)

            # 开启全局超时（仅Linux/macOS生效）
            if not IS_WINDOWS:
                signal.alarm(TASK_TIMEOUT_SECONDS)

            # 执行任务
            task_ok = add_time_task(page)

            # 关闭闹钟
            if not IS_WINDOWS:
                signal.alarm(0)

            if not task_ok:
                exit(1)

        except TaskTimeoutError:
            print(f"\n🔥 全局超时 {TASK_TIMEOUT_SECONDS}s，任务强制终止")
            page.screenshot(path="force_timeout.png")
            exit(1)
        except Exception as e:
            print(f"\n🔥 主程序致命错误: {str(e)}")
            page.screenshot(path="main_error.png")
            exit(1)
        finally:
            browser.close()
            print("\n✅ 浏览器已关闭，脚本运行结束")

if __name__ == "__main__":
    main()
