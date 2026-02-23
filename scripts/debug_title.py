# scripts/debug_title.py
# Quick script to debug title extraction problem returned by checkpoint inspection. 
# Run with `uv run python scripts/debug_title.py` to see raw metadata and markdown output for a sample page. 
# Adjust the URL and css_selector in the CrawlerRunConfig as needed to test different pages or site structures.
import asyncio
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

async def main():
    browser_cfg = BrowserConfig(headless=True, verbose=False)
    run_cfg = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        markdown_generator=DefaultMarkdownGenerator(),
        wait_until="domcontentloaded",
        page_timeout=30000,
        css_selector=".td-content",
    )

    async with AsyncWebCrawler(config=browser_cfg) as crawler:
        result = await crawler.arun(url="https://kubernetes.io/docs/", config=run_cfg)

    print(f"result.metadata     : {result.metadata}")
    print(f"result.title        : {getattr(result, 'title', 'ATTR NOT FOUND')}")
    print(f"result.html[:500]   : {result.html[:500] if result.html else 'NONE'}")

asyncio.run(main())