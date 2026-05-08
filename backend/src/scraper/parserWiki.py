import re
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode



async def mainWiki(url: str, html: str = None, crawler: AsyncWebCrawler = None) -> dict:

    browser_cfg = BrowserConfig(headless=True)
    title_cfg = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        css_selector=".mw-page-title-main",
        remove_forms=True,
        exclude_external_links=True,
        exclude_internal_links=True
    )
    crawler_cfg = CrawlerRunConfig(

            cache_mode=CacheMode.BYPASS,
     
            remove_forms=True,
            exclude_external_links=True,
            exclude_internal_links=True,

            css_selector="#mw-content-text .mw-parser-output", #Wikipedia

            excluded_tags=[  
                "figure",
                "img",
                "style",
                "script",
                "aside",
                "mystyle",
                "mi",
                "mo",
                "mrow",
                "mover",
                "mtext",
                "mstyle",
                "msup",
                "mspace",
                "mfrac",
                "munderover"
            ],

            excluded_selector="""
                .infobox,
                .navbox,
                .reflist,
                .mw-editsection,
                .mw-cite-backlink,
                .hatnote,
                .metadata,
                .toc,
                .sidebar
            """
        )

    async def esegui_scraping(c_instance):
        if html:
            target_url = "raw://" + html
            # Facciamo entrambe le chiamate
            res = await c_instance.arun(url=target_url, config=crawler_cfg)
            title_res = await c_instance.arun(url=target_url, config=title_cfg)
            return res, title_res, html
        else:
            res = await c_instance.arun(url=url, config=crawler_cfg)
            title_res = await c_instance.arun(url=url, config=title_cfg)
            return res, title_res, res.html

    # Estraiamo TRE variabili (result, title_result, html_text)
    if crawler:
        result, title_result, html_text = await esegui_scraping(crawler)
    else:
        browser_cfg = BrowserConfig(headless=True)
        async with AsyncWebCrawler(config=browser_cfg) as temp_crawler:
            result, title_result, html_text = await esegui_scraping(temp_crawler)

    if result.markdown:
        md = result.markdown
    else:
        md = ""

    domain = url.split("//")[-1].split("/")[0] #Prende il primo elemento dell'url che sarà il dominio

    raw_title = title_result.html or ""
    t = re.search(r'<span class="mw-page-title-main">(.*?)</span>', raw_title)
    if t and t.group(1).strip():
        title = t.group(1).strip()
    else:
        t = re.search(r'<h1[^>]*id="firstHeading"[^>]*>(.*?)</h1>', raw_title)
        if t and t.group(1).strip():
            title = re.sub(r"<.*?>", "", t.group(1)).strip()
        else:
            title = "Titolo non disponibile"

    return {
            "url": url,
            "domain": domain,
            "title": title,
            "html_text": html_text,
            "parsed_text": md
        }