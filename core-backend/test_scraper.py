import asyncio
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from playwright.async_api import async_playwright

async def test():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0'
        )
        page = await context.new_page()
        await page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")
        print('Opening page...')
        await page.goto(
            'https://www.minhngoc.net.vn/ket-qua-xo-so/dien-toan-vietlott/mega-6x45.html',
            wait_until='networkidle',
            timeout=30000
        )
        await page.wait_for_timeout(5000)
        
        # Method 1: spinners in bangkq6x36
        nums = await page.evaluate("""() => {
            const nums = [];
            document.querySelectorAll('.bangkq6x36 .spinner').forEach(el => {
                const t = el.textContent.trim();
                if (t && /^\d+$/.test(t)) nums.push(t);
            });
            return nums;
        }""")
        print('Spinner nums:', nums)
        
        # Method 2: result-number
        rn = await page.locator('.result-number').all_text_contents()
        print('result-number:', rn[:10])
        
        # Method 3: find first row of table with jackpot
        jackpot_html = await page.evaluate("""() => {
            const el = document.querySelector('.bangkq6x36');
            return el ? el.innerHTML.substring(0, 2000) : 'NOT FOUND';
        }""")
        print('bangkq6x36 HTML snippet:', jackpot_html[:1000])
        
        # Method 4: all text in .lotto-result
        lr = await page.locator('.lotto-result').all_text_contents()
        print('lotto-result:', str(lr)[:300])
        
        # Method 5: get page title to confirm no bot block
        title = await page.title()
        print('Page title:', title)
        
        await browser.close()

asyncio.run(test())
