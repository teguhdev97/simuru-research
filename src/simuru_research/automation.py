import asyncio

from playwright.async_api import async_playwright


async def create_mail_accounts():
    async with async_playwright() as p:
        # Jalankan browser (bisa headless=False untuk debugging visual)
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        # 1. Login ke Panel Hosting / cPanel Mail Anda
        await page.goto("https://mail.teguhharits.com:2083") # Ganti dengan URL login panel mail/cPanel Anda
        await page.fill("input[id='user']", "username_hosting_anda")
        await page.fill("input[id='pass']", "password_hosting_anda")
        await page.click("button#login_submit")
        await page.wait_for_load_state("networkidle")

        # 2. Loop otomatisasi pembuatan 5 akun email
        accounts = [
            {"user": "user1", "pass": "SecurePass123!"},
            {"user": "user2", "pass": "SecurePass123!"},
            {"user": "user3", "pass": "SecurePass123!"},
            {"user": "user4", "pass": "SecurePass123!"},
            {"user": "user5", "pass": "SecurePass123!"},
        ]

        for acc in accounts:
            print(f"Membuat akun: {acc['user']}@teguhharits.com")
            # Navigasi ke menu Add Email Account di cPanel/Webmail
            await page.goto("https://mail.teguhharits.com:2083/frontend/jupiter/mail/add.html")
            
            await page.fill("input#email", acc["user"])
            await page.fill("input#password", acc["pass"])
            await page.fill("input#password_again", acc["pass"])
            await page.click("button#create_account_btn")
            
            # Berikan jeda atau tunggu konfirmasi sukses
            await page.wait_for_timeout(2000)

        await browser.close()

asyncio.run(create_mail_accounts())