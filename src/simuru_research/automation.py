from __future__ import annotations

import asyncio

from playwright.async_api import async_playwright


async def create_mail_accounts() -> None:
    async with async_playwright() as p:
        # Jalankan browser (headless=False untuk debugging visual)
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        # 1. Login ke Panel Hosting / cPanel Mail Rumahweb
        cpanel_url = "https://juwana.iixcp.rumahweb.net:2083"
        await page.goto(cpanel_url)
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

        add_url = (
            "https://juwana.iixcp.rumahweb.net:2083"
            "/frontend/jupiter/mail/add.html"
        )
        for acc in accounts:
            print(f"Membuat akun: {acc['user']}@teguhharits.com")
            await page.goto(add_url)

            await page.fill("input#email", acc["user"])
            await page.fill("input#password", acc["pass"])
            await page.fill("input#password_again", acc["pass"])
            await page.click("button#create_account_btn")

            # Jeda untuk menunggu konfirmasi sukses server cPanel
            await page.wait_for_timeout(2000)

        await browser.close()


if __name__ == "__main__":
    asyncio.run(create_mail_accounts())