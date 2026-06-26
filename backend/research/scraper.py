import os
import re
import time

DEBUG_DIR = "/tmp/research_debug"


def _debug_screenshot(page, name: str):
    os.makedirs(DEBUG_DIR, exist_ok=True)
    try:
        page.screenshot(path=f"{DEBUG_DIR}/{name}.png")
        print(f"[Research DEBUG] Screenshot: {DEBUG_DIR}/{name}.png")
    except Exception:
        pass


def _scrape_httpx(url: str) -> str:
    try:
        import httpx
        from bs4 import BeautifulSoup
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) "
                "Version/17.0 Safari/605.1.15"
            ),
        }
        resp = httpx.get(url, headers=headers, timeout=15, follow_redirects=True)
        if resp.status_code != 200:
            return ""
        # Try to extract article content
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()
        text = soup.get_text(separator=" ", strip=True)
        text = re.sub(r'\s+', ' ', text).strip()
        return text[:8000]
    except ImportError:
        # Fallback with basic HTML stripping (no BeautifulSoup)
        try:
            import httpx
            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                              "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"
            }
            resp = httpx.get(url, headers=headers, timeout=15, follow_redirects=True)
            if resp.status_code != 200:
                return ""
            text = re.sub(r'<[^>]+>', ' ', resp.text)
            text = re.sub(r'\s+', ' ', text).strip()
            return text[:8000]
        except Exception as e:
            print(f"[Research] scrape httpx error for {url[:60]}: {e}")
            return ""
    except Exception as e:
        print(f"[Research] scrape httpx error for {url[:60]}: {e}")
        return ""


def extract_text_sync(page=None, url: str = "", timeout: int = 20000) -> str:
    start = time.time()
    print(f"[Research] Scraping: {url[:80]}...")

    # Try browser first if page provided
    if page:
        try:
            page.goto(url, timeout=timeout)
            page.wait_for_load_state("domcontentloaded")
            time.sleep(0.5)
            text = page.evaluate("document.body.innerText")
            if text and len(text.strip()) >= 100:
                text = re.sub(r'\s+', ' ', text).strip()
                elapsed = time.time() - start
                print(f"[Research] Scraped {len(text)} chars (browser) in {elapsed:.1f}s")
                return text[:8000]
            else:
                print(f"[Research] Short browser text ({len(text or '')} chars), "
                      f"trying httpx fallback")
                _debug_screenshot(page, f"scrape_short_{int(start)}")
        except Exception as e:
            print(f"[Research] browser scrape error: {e}")
            try:
                _debug_screenshot(page, f"scrape_error_{int(start)}")
            except Exception:
                pass

    # Fallback to httpx
    text = _scrape_httpx(url)
    if text:
        elapsed = time.time() - start
        print(f"[Research] Scraped {len(text)} chars (httpx) in {elapsed:.1f}s")
    else:
        print(f"[Research] httpx scrape returned empty for {url[:60]}")
    return text
