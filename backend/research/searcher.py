import os
import re
import time
import traceback
import urllib.parse
from typing import Optional

_CLOAK_AVAILABLE = False
try:
    from cloakbrowser import launch as cloak_launch
    # Only set available if binary is already cached (lazy check)
    import os
    from cloakbrowser.download import get_binary_path
    if os.path.exists(get_binary_path()):
        _CLOAK_AVAILABLE = True
        print("[Research] CloakBrowser Chromium binary ready")
    else:
        print("[Research] CloakBrowser binary not cached (use httpx only)")
except (ImportError, Exception) as _cb_err:
    print(f"[Research] CloakBrowser not available: {_cb_err}")

SEARCH_DELAY = 1.5
DEBUG_DIR = "/tmp/research_debug"

_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) "
    "Version/17.0 Safari/605.1.15"
)


def _debug_screenshot(page, name: str):
    os.makedirs(DEBUG_DIR, exist_ok=True)
    try:
        page.screenshot(path=f"{DEBUG_DIR}/{name}.png")
        print(f"[Research DEBUG] Screenshot: {DEBUG_DIR}/{name}.png")
    except Exception:
        pass


def _extract_google_results(html: str) -> list[dict]:
    results = []
    for m in re.finditer(r'<h3[^>]*>(.*?)</h3>', html, re.DOTALL):
        a_match = re.search(r'<a[^>]*href="?/url\?q=([^"&]+)', m.group(0))
        if not a_match:
            a_match = re.search(r'<a[^>]*href="(https?://[^"]+)"', m.group(0))
        title_match = re.search(r'<a[^>]*>(.*?)</a>', m.group(0), re.DOTALL)
        if a_match and title_match:
            url = a_match.group(1)
            title = re.sub(r'<[^>]+>', '', title_match.group(1)).strip()
            results.append({"title": title, "url": url, "snippet": ""})
    snippets = re.findall(
        r'<div[^>]*class="[^"]*(?:VwiC3b|aCOpRe)[^"]*"[^>]*>(.*?)</div>',
        html, re.DOTALL,
    )
    for i, snip in enumerate(snippets[:len(results)]):
        results[i]["snippet"] = re.sub(r'<[^>]+>', '', snip).strip()
    return results


def _extract_scholar_results(html: str) -> list[dict]:
    results = []
    for block in re.findall(r'<div[^>]*class="gs_ri"[^>]*>(.*?)</div>\s*</div>', html, re.DOTALL):
        title_match = re.search(r'<h3[^>]*class="gs_rt"[^>]*>(.*?)</h3>', block, re.DOTALL)
        if not title_match:
            continue
        a_match = re.search(r'<a[^>]*href="([^"]+)"', title_match.group(1))
        url = a_match.group(1) if a_match else ""
        raw_title = re.sub(r'<[^>]+>', '', title_match.group(1)).strip()
        title_text = re.sub(r'^\[[\w/]+\]\s*(\[[\w/]+\]\s*)?', '', raw_title).strip()
        snippet_match = re.search(r'<div[^>]*class="gs_rs"[^>]*>(.*?)</div>', block, re.DOTALL)
        snippet = re.sub(r'<[^>]+>', '', snippet_match.group(1)).strip() if snippet_match else ""
        results.append({"title": title_text, "url": url, "snippet": snippet})
    return results


def _extract_pubmed_results(html: str) -> list[dict]:
    results = []
    for article in re.findall(r'<article[^>]*class="full-docsum"[^>]*>(.*?)</article>', html, re.DOTALL):
        title_match = re.search(r'<a[^>]*href="/[^"]*"[^>]*>(.*?)</a>', article, re.DOTALL)
        if not title_match:
            continue
        title = re.sub(r'<[^>]+>', '', title_match.group(1)).strip()
        href_match = re.search(r'href="([^"]+)"', title_match.group(0))
        url = f"https://pubmed.ncbi.nlm.nih.gov{href_match.group(1)}" if href_match else ""
        snippet_match = re.search(
            r'<div[^>]*class="full-view-snippet"[^>]*>(.*?)</div>', article, re.DOTALL,
        )
        snippet = re.sub(r'<[^>]+>', '', snippet_match.group(1)).strip() if snippet_match else ""
        results.append({"title": title, "url": url, "snippet": snippet})
    return results


def _browser_search(page, url: str, extract_fn, source_name: str, max_results: int = 5) -> list[dict]:
    print(f"[Research] {source_name} (browser): navigating...")
    try:
        page.goto(url, timeout=25000)
        page.wait_for_load_state("domcontentloaded")
        time.sleep(SEARCH_DELAY)
        html = page.content()
        results = extract_fn(html)
        if not results:
            _debug_screenshot(page, f"{source_name}_no_results")
        return results[:max_results]
    except Exception as e:
        print(f"[Research] {source_name} browser error: {e}")
        try:
            _debug_screenshot(page, f"{source_name}_error")
        except Exception:
            pass
        return []


def _extract_bing_results(html: str) -> list[dict]:
    results = []
    for item in re.findall(r'<li[^>]*class="b_algo"[^>]*>(.*?)</li>', html, re.DOTALL):
        title_match = re.search(
            r'<h2[^>]*>.*?<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', item, re.DOTALL,
        )
        if not title_match:
            continue
        url = title_match.group(1).replace("&amp;", "&")  # Bing tracking URL (unescape)
        title = re.sub(r'<[^>]+>', '', title_match.group(2)).strip()
        snippet_match = re.search(r'<p[^>]*>(.*?)</p>', item, re.DOTALL)
        snippet = re.sub(r'<[^>]+>', '', snippet_match.group(1)).strip() if snippet_match else ""
        results.append({"title": title, "url": url, "snippet": snippet})
    return results


def _resolve_bing_url(tracking_url: str) -> str:
    """Follow a Bing tracking URL to extract the real URL from JS var u."""
    import httpx
    headers = {"User-Agent": _UA}
    try:
        r = httpx.get(tracking_url, headers=headers, timeout=5, follow_redirects=False)
        m = re.search(r'var u = "([^"]+)"', r.text)
        if m:
            return m.group(1)
    except Exception:
        pass
    return tracking_url


def _extract_bing_news_results(html: str) -> list[dict]:
    results = []
    for a_tag in re.findall(r'<a[^>]*class="title"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', html, re.DOTALL):
        url = a_tag[0]
        title = re.sub(r'<[^>]+>', '', a_tag[1]).strip()
        results.append({"title": title, "url": url, "snippet": ""})
    # Extract snippets (class="snip")
    snippets = re.findall(r'<div[^>]*class="snip"[^>]*>(.*?)</div>', html, re.DOTALL)
    for i, snip in enumerate(snippets[:len(results)]):
        results[i]["snippet"] = re.sub(r'<[^>]+>', '', snip).strip()
    return results


def _search_httpx(url: str, extract_fn, source_name: str) -> list[dict]:
    try:
        import httpx
        # Simple UA-only header — extra headers (Accept/Accept-Language) trigger
        # captcha on some engines (e.g. Bing)
        headers = {"User-Agent": _UA}
        resp = httpx.get(url, headers=headers, timeout=15, follow_redirects=True)
        if resp.status_code == 200:
            results = extract_fn(resp.text)
            if results:
                print(f"[Research] {source_name}: {len(results)} results (httpx)")
                return results
            else:
                print(f"[Research] {source_name}: no results parsed from httpx response "
                      f"({len(resp.text)} chars)")
        else:
            print(f"[Research] {source_name}: httpx status {resp.status_code}")
    except Exception as e:
        print(f"[Research] {source_name} httpx error: {e}")
    return []


def search_sources_sync(query: str, browser=None, max_results: int = 5) -> dict[str, list[dict]]:
    encoded = urllib.parse.quote(query)
    sources = {}
    configs = [
        ("bing_web",  f"https://www.bing.com/search?q={encoded}&count={max_results}",  _extract_bing_results),
        ("scholar",   f"https://scholar.google.com/scholar?q={encoded}&num={max_results}", _extract_scholar_results),
        ("bing_news", f"https://www.bing.com/news/search?q={encoded}&count={max_results}", _extract_bing_news_results),
    ]

    for name, url, extract_fn in configs:
        print(f"[Research] Searching {name}...")
        raw = []

        # Try browser first if available
        if browser:
            page = browser.new_page()
            try:
                raw = _browser_search(page, url, extract_fn, name, max_results)
            finally:
                page.close()

        # Fallback to httpx
        if not raw:
            raw = _search_httpx(url, extract_fn, name)

        # Resolve Bing tracking URLs to real URLs
        if name == "bing_web" and raw:
            print(f"[Research] Resolving {len(raw)} Bing tracking URLs...")
            import httpx as _httpx
            with _httpx.Client(timeout=5) as _client:
                for r in raw:
                    if "bing.com/ck/" in r["url"]:
                        try:
                            _resp = _client.get(r["url"], headers={"User-Agent": _UA})
                            _m = re.search(r'var u = "([^"]+)"', _resp.text)
                            if _m:
                                r["url"] = _m.group(1)
                        except Exception:
                            pass

        sources[name] = raw[:max_results]
        print(f"[Research] {name}: {len(raw)} results")

    return sources
