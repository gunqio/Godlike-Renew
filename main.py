import os
import time
import signal
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from datetime import datetime

# ==================== 配置项 ====================
SERVER_URL = "https://ultra.panel.godlike.host/server/dc3b034"
LOGIN_URL = "https://ultra.panel.godlike.host/login"
COOKIE_NAME = "remember_web_59ba36addc2b2f9401580f014c7f58ea4e30989d"

TASK_TIMEOUT_SECONDS = 300
AD_WAIT_SECONDS = 120
DEFAULT_PAGE_TIMEOUT = 60000

IS_WINDOWS = os.name == "nt"

# ==================== 自定义异常 & 超时信号 ====================
class TaskTimeoutError(Exception):
    pass

def timeout_handler(signum, frame):
    raise TaskTimeoutError("任务执行超出最大时长限制")

if not IS_WINDOWS:
    signal.signal(signal.SIGALRM, timeout_handler)

# ==================== 登录逻辑（精准点击按钮版） ====================
def login_with_playwright(page):
    cookie_val = os.environ.get("PTERODACTYL_COOKIE", "")
    email = os.environ.get("PTERODACTYL_EMAIL", "")
    pwd = os.environ.get("PTERODACTYL_PASSWORD", "")

    # 尝试 Cookie 登录
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
        # 精确匹配并点击
        link_loc = page.locator('a:has-text("Through Login/Password")')
        link_loc.wait_for(state="visible", timeout=15000)
        print("正在点击 'Through Login/Password' 按钮...")
        link_loc.click()

        # 等待表单
        email_selector = 'input[name="username"]'
        password_selector = 'input[name="password"]'
        login_btn = 'button[type="submit"]'

        page.wait_for_selector(email_selector, timeout=30000)
        page.wait_for_selector(password_selector, timeout=30000)

        print("✅ 表单已加载，填写账号密码...")
        page.fill(email_selector, email)
        page.fill(password_selector, pwd)

        print("点击登录按钮...")
        with page.expect_navigation(wait_until="domcontentloaded"):
            page.click(login_btn)

        if "login" in page.url:
            print("❌ 账号密码登录失败，请检查凭据")
            page.screenshot(path="login_fail.png")
            return False

        print("✅ 账号密码登录成功")
        return True

    except Exception as e:
        print(f"❌ 登录异常: {str(e)}")
        page.screenshot(path="login_error.png")
        return False

# ==================== 续时任务 ====================
def add_time_task(page):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n[{now}] ⏳ 开始执行续时任务")

    if page.url.strip() != SERVER_URL.strip():
        print(f"🔄 跳转至服务器页面")
        page.goto(SERVER_URL, wait_until="domcontentloaded")

    try:
        add_btn = page.locator('button:has-text("Add 90 minutes")')
        add_btn.wait_for(state="visible", timeout=30000)
        add_btn.click()
        print("✅ 点击 Add 90 minutes")

        ad_btn = page.locator('button:has-text("Watch advertisement")')
        ad_btn.wait_for(state="visible", timeout=30000)
        ad_btn.click()
        print("✅ 点击 Watch advertisement，开始等待广告")

        time.sleep(AD_WAIT_SECONDS)
        now_end = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{now_end}] ✅ 广告等待完成，本轮续时结束")
        return True

    except PlaywrightTimeoutError:
        print("❌ 元素加载超时")
        page.screenshot(path="task_timeout.png")
        return False
    except Exception as e:
        print(f"❌ 任务异常: {str(e)}")
        page.screenshot(path="task_error.png")
        return False

# ==================== 主程序 ====================
def main():
    print("================ 启动自动化续时脚本 ================")
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled"
            ]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        page.set_default_timeout(DEFAULT_PAGE_TIMEOUT)
        print("✅ 浏览器启动完成")

        try:
            if not login_with_playwright(page):
                exit(1)

            if not IS_WINDOWS:
                signal.alarm(TASK_TIMEOUT_SECONDS)

            task_ok = add_time_task(page)

            if not IS_WINDOWS:
                signal.alarm(0)

            if not task_ok:
                exit(1)

        except TaskTimeoutError:
            print(f"\n🔥 全局超时 {TASK_TIMEOUT_SECONDS}s，任务终止")
            page.screenshot(path="force_timeout.png")
            exit(1)
        except Exception as e:
            print(f"\n🔥 主程序错误: {str(e)}")
            page.screenshot(path="main_error.png")
            exit(1)
        finally:
            browser.close()
            print("\n✅ 浏览器已关闭，脚本运行结束")

if __name__ == "__main__":
    main()
