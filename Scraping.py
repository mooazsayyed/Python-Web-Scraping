import asyncio
import argparse
import json
import re
from pathlib import Path
from typing import Optional

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError


SEARCH_URL = "https://www.propertyfinder.ae/en/search?l=50&c=1&fu=0&ob=mr&page={page}"
OUTPUT_DIR = Path("outputs")
OUTPUT_JSON = OUTPUT_DIR / "propertyfinder_listings.json"
OUTPUT_CSV = OUTPUT_DIR / "propertyfinder_listings.csv"
PROBE_JSON = OUTPUT_DIR / "propertyfinder_probe.json"


async def safe_text(locator, selector: str) -> Optional[str]:
    try:
        item = locator.locator(selector).first
        if await item.count() == 0:
            return None
        text = (await item.inner_text()).strip()
        return text or None
    except Exception:
        return None


async def safe_attr(locator, selector: str, attr: str) -> Optional[str]:
    try:
        item = locator.locator(selector).first
        if await item.count() == 0:
            return None
        value = await item.get_attribute(attr)
        return value.strip() if value else None
    except Exception:
        return None


def compact(text: Optional[str], limit: int = 300) -> Optional[str]:
    if not text:
        return text
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit] + ("..." if len(text) > limit else "")


async def probe_page(page, page_number: int, max_items: int = 5) -> dict:
    probe = {
        "page": page_number,
        "url": page.url,
        "title": await page.title(),
        "candidate_selectors": {},
        "data_testids": [],
        "sample_items": [],
    }

    selector_map = {
        "property_card": '[data-testid="property-card"]',
        "property_card_link": '[data-testid="property-card-link"]',
        "any_data_testid_card": '[data-testid*="card"]',
        "article": "article",
        "listing_links": 'a[href*="/en/"], a[href*="/property/"], a[href*="/listing/"]',
    }

    for name, selector in selector_map.items():
        loc = page.locator(selector)
        count = await loc.count()
        probe["candidate_selectors"][name] = count

    probe["data_testids"] = await page.eval_on_selector_all(
        "[data-testid]",
        "els => [...new Set(els.map(el => el.getAttribute('data-testid')).filter(Boolean))].slice(0, 100)",
    )

    sample_locator = page.locator('[data-testid="property-card"]')
    if await sample_locator.count() == 0:
        sample_locator = page.locator('article, [data-testid*="card"], a[href*="/en/"], a[href*="/listing/"]')
    sample_count = min(await sample_locator.count(), max_items)

    for idx in range(sample_count):
        item = sample_locator.nth(idx)
        try:
            html = await item.inner_html()
        except Exception:
            html = None
        try:
            text = await item.inner_text()
        except Exception:
            text = None
        try:
            tag = await item.evaluate("(el) => el.tagName")
        except Exception:
            tag = None
        try:
            href = await item.get_attribute("href")
        except Exception:
            href = None

        probe["sample_items"].append(
            {
                "index": idx + 1,
                "tag": tag,
                "href": href,
                "text": compact(text, 800),
                "html": compact(html, 1200),
            }
        )

    return probe


async def extract_card(card, page_number: int, index: int) -> dict:
    raw_text = (await card.inner_text()).strip()
    href = await safe_attr(card, '[data-testid="property-card-link"]', "href")
    if not href:
        href = await safe_attr(card, "a[href*='/en/plp/']", "href")

    title = (
        await safe_text(card, '[data-testid="property-card-link"]')
        or await safe_attr(card, '[data-testid="property-card-link"]', "aria-label")
        or await safe_text(card, "h2")
        or await safe_text(card, "h3")
    )

    price = (
        await safe_text(card, '[data-testid="property-card-price"]')
        or await safe_text(card, '[class*="price"]')
    )

    location = (
        await safe_text(card, '[data-testid="property-card-location"]')
        or await safe_text(card, '[class*="location"]')
    )

    agent = (
        await safe_text(card, '[data-testid="agent-image"]')
        or await safe_attr(card, '[data-testid="agent-image"] img', "alt")
        or await safe_text(card, '[class*="agent"]')
    )

    area = await safe_text(card, '[data-testid="property-card-spec-area"]')
    price_per_sqft = await safe_text(card, '[data-testid="property-card-spec-price-per-area"]')
    bedrooms = await safe_text(card, '[data-testid="property-card-spec-bedroom"]')
    bathrooms = await safe_text(card, '[data-testid="property-card-spec-bathroom"]')
    property_type = await safe_text(card, '[data-testid="property-card-spec-propertyType"]')

    return {
        "page": page_number,
        "index": index,
        "title": title,
        "price": price,
        "price_per_sqft": price_per_sqft,
        "area": area,
        "bedrooms": bedrooms,
        "bathrooms": bathrooms,
        "property_type": property_type,
        "location": location,
        "agent": agent,
        "url": href,
        "raw_text": raw_text,
    }


def resolve_output_paths(filename: Optional[str]) -> tuple[Path, Path, Path]:
    if not filename:
        return OUTPUT_JSON, OUTPUT_CSV, PROBE_JSON

    base_path = Path(filename)
    suffix = base_path.suffix.lower()

    if suffix in {".json", ".csv"}:
        base_path = base_path.with_suffix("")

    if not base_path.is_absolute() and len(base_path.parts) == 1:
        base_path = OUTPUT_DIR / base_path

    return (
        base_path.with_suffix(".json"),
        base_path.with_suffix(".csv"),
        base_path.with_name(f"{base_path.name}_probe.json"),
    )


async def scrape_propertyfinder():
    browser_args = [
        "--disable-blink-features=AutomationControlled",
        "--no-sandbox",
    ]

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=browser_args,
        )
        results = await scrape_with_browser(browser)
        await browser.close()
        return results


async def scrape_with_browser(browser, *, probe_only: bool = False, max_pages: int = 2):
    context = await browser.new_context(
        viewport={"width": 1366, "height": 900},
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        ),
        locale="en-US",
    )

    page = await context.new_page()
    results = []
    seen_urls = set()

    card_selector = '[data-testid="property-card"]'

    probe_results = []
    running_index = 1

    for page_number in range(1, max_pages + 1):
        url = SEARCH_URL.format(page=page_number)
        print(f"Loading page {page_number}: {url}")

        await page.goto(url, wait_until="domcontentloaded", timeout=60000)

        try:
            await page.wait_for_load_state("networkidle", timeout=15000)
        except PlaywrightTimeoutError:
            pass

        await page.wait_for_timeout(2000)

        if probe_only:
            probe = await probe_page(page, page_number)
            probe_results.append(probe)
            print(json.dumps(probe, indent=2, ensure_ascii=False))
            continue

        cards = page.locator(card_selector)
        count = await cards.count()

        if count == 0:
            print(f"No cards found on page {page_number}")
            continue

        for idx in range(count):
            card = cards.nth(idx)
            try:
                data = await extract_card(card, page_number, running_index)
                url_value = data.get("url")
                raw_text = data.get("raw_text") or ""

                if "/new-projects/" in (url_value or ""):
                    continue
                if not raw_text.strip():
                    continue
                if url_value in seen_urls:
                    continue
                if url_value:
                    seen_urls.add(url_value)
                data["page_index"] = idx + 1
                results.append(data)
                running_index += 1
            except Exception as exc:
                print(f"Skipping card {idx + 1} on page {page_number}: {exc}")

        print(f"Page {page_number}: collected {count} cards")

    await context.close()
    return probe_results if probe_only else results


def save_results(results, output_json: Path, output_csv: Path):
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(results, ensure_ascii=True, indent=2), encoding="utf-8")

    import csv

    fieldnames = [
        "page",
        "index",
        "page_index",
        "title",
        "price",
        "price_per_sqft",
        "area",
        "bedrooms",
        "bathrooms",
        "property_type",
        "location",
        "agent",
        "url",
        "raw_text",
    ]
    with output_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)


def save_probe_results(results, output_probe_json: Path):
    output_probe_json.parent.mkdir(parents=True, exist_ok=True)
    output_probe_json.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")


async def main():
    parser = argparse.ArgumentParser(
        description="Scrape PropertyFinder listings from the results pages and save text-only output to JSON/CSV.",
        epilog=(
            "Examples:\n"
            "  python Scraping.py\n"
            "  python Scraping.py --pages 2\n"
            "  python Scraping.py -f propertyfinder_listings\n"
            "  python Scraping.py --probe --pages 1\n"
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--probe",
        action="store_true",
        help="Inspect page structure and save probe JSON instead of extracting listings.",
    )
    parser.add_argument(
        "--pages",
        type=int,
        default=2,
        help="Number of PropertyFinder result pages to scrape. Default: 2",
    )
    parser.add_argument(
        "-f",
        "--filename",
        help=(
            "Base output filename. A plain name is saved under outputs/. "
            "Example: -f propertyfinder_listings"
        ),
    )
    args = parser.parse_args()

    output_json, output_csv, output_probe_json = resolve_output_paths(args.filename)

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
        )
        results = await scrape_with_browser(browser, probe_only=args.probe, max_pages=args.pages)
        await browser.close()

    if args.probe:
        save_probe_results(results, output_probe_json)
        print(f"\nSaved probe data to {output_probe_json.resolve()}")
        return

    save_results(results, output_json, output_csv)

    print(f"\nSaved {len(results)} listings")
    print(f"- JSON: {output_json.resolve()}")
    print(f"- CSV:  {output_csv.resolve()}")

    if results:
        print("\nSample listing:")
        print(json.dumps(results[0], indent=2, ensure_ascii=True))


if __name__ == "__main__":
    asyncio.run(main())
