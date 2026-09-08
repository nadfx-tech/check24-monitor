"""
Check24 Hotel-Preismonitor (Cloud-Version für GitHub Actions)
- Einzelner Durchlauf: prüft alle Hotels, benachrichtigt bei Änderung
- Preisdaten werden in prices.json gespeichert und ins Repo committed
"""

import asyncio
import json
import os
import re
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

from playwright.async_api import async_playwright

# ─── Konfiguration ───────────────────────────────────────────────────────────

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

BASE_DIR = Path(__file__).parent
PRICES_FILE = BASE_DIR / "prices.json"

REMOVE_PARAMS = {"hotelListId", "budgetMax", "bestSeller"}

HOTELS = [
    {
        "id": "9279",
        "url": "https://urlaub.check24.de/suche/angebot?airport=FRA&areaId=600&areaSort=topregion&cateringList=allinclusive%2CallinclusivePlus&days=8-10&departureDate=2026-10-18&departureFlightTimeFrom=660&ds=r&extendedSearch=1&hotelId=9279&offerSort=offerRanking&pageArea=package&rating=8&returnDate=2026-10-30&returnFlightTimeFrom=600&roomAllocation=A-13%2CA-9&sorting=categoryDistribution&transfer=transfer&transportType=flight",
    },
    {
        "id": "18493",
        "url": "https://urlaub.check24.de/suche/angebot?airport=FRA&areaId=600&areaSort=topregion&cateringList=allinclusive,allinclusivePlus&days=8-10&departureDate=2026-10-18&departureFlightTimeFrom=630&departureFlightTimeUntil=1439&ds=r&offerSort=offerRanking&pageArea=package&rating=8&returnDate=2026-10-30&returnFlightTimeFrom=630&returnFlightTimeUntil=1439&roomAllocation=A-13,A-9&sorting=categoryDistribution&transfer=transfer&transportType=flight&hotelId=18493&extendedSearch=1",
    },
    {
        "id": "3703",
        "url": "https://urlaub.check24.de/suche/angebot?airport=FRA&areaId=600&areaSort=topregion&cateringList=allinclusive,allinclusivePlus&days=8-10&departureDate=2026-10-18&departureFlightTimeFrom=630&departureFlightTimeUntil=1439&ds=r&offerSort=offerRanking&pageArea=package&rating=8&returnDate=2026-10-30&returnFlightTimeFrom=630&returnFlightTimeUntil=1439&roomAllocation=A-13,A-9&sorting=categoryDistribution&transfer=transfer&transportType=flight&hotelId=3703&extendedSearch=1",
    },
    {
        "id": "3694",
        "url": "https://urlaub.check24.de/suche/angebot?airport=FRA&areaId=600&areaSort=topregion&cateringList=allinclusive,allinclusivePlus&days=8-10&departureDate=2026-10-18&departureFlightTimeFrom=630&departureFlightTimeUntil=1439&ds=r&offerSort=offerRanking&pageArea=package&rating=8&returnDate=2026-10-30&returnFlightTimeFrom=630&returnFlightTimeUntil=1439&roomAllocation=A-13,A-9&sorting=categoryDistribution&transfer=transfer&transportType=flight&hotelId=3694&extendedSearch=1",
    },
    {
        "id": "61801",
        "url": "https://urlaub.check24.de/suche/angebot?airport=FRA&areaId=600&areaSort=topregion&cateringList=allinclusive,allinclusivePlus&days=8-10&departureDate=2026-10-18&departureFlightTimeFrom=630&departureFlightTimeUntil=1439&ds=r&offerSort=offerRanking&pageArea=package&rating=8&returnDate=2026-10-30&returnFlightTimeFrom=630&returnFlightTimeUntil=1439&roomAllocation=A-13,A-9&sorting=categoryDistribution&transfer=transfer&transportType=flight&hotelId=61801&extendedSearch=1",
    },
    {
        "id": "68",
        "url": "https://urlaub.check24.de/suche/angebot?airport=FRA&areaId=600&areaSort=topregion&cateringList=allinclusive,allinclusivePlus&days=8-10&departureDate=2026-10-18&departureFlightTimeFrom=630&departureFlightTimeUntil=1439&ds=r&offerSort=offerRanking&pageArea=package&rating=8&returnDate=2026-10-30&returnFlightTimeFrom=630&returnFlightTimeUntil=1439&roomAllocation=A-13,A-9&sorting=categoryDistribution&transfer=transfer&transportType=flight&hotelId=68&extendedSearch=1",
    },
    {
        "id": "4409",
        "url": "https://urlaub.check24.de/suche/angebot?airport=FRA&areaId=600&areaSort=topregion&cateringList=allinclusive,allinclusivePlus&days=8-10&departureDate=2026-10-18&departureFlightTimeFrom=630&departureFlightTimeUntil=1439&ds=r&offerSort=offerRanking&pageArea=package&rating=8&returnDate=2026-10-30&returnFlightTimeFrom=630&returnFlightTimeUntil=1439&roomAllocation=A-13,A-9&sorting=categoryDistribution&transfer=transfer&transportType=flight&hotelId=4409&extendedSearch=1",
    },
]

SUMMARY_HOURS = [8, 12, 16, 20, 23]

# ─── Hilfsfunktionen ─────────────────────────────────────────────────────────

def clean_url(url):
    parsed = urllib.parse.urlparse(url)
    params = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
    cleaned = {k: v[0] for k, v in params.items() if k not in REMOVE_PARAMS}
    new_query = urllib.parse.urlencode(cleaned)
    return urllib.parse.urlunparse(parsed._replace(query=new_query))


def log(msg):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")


def load_prices():
    if PRICES_FILE.exists():
        return json.loads(PRICES_FILE.read_text(encoding="utf-8"))
    return {}


def save_prices(data):
    PRICES_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def send_telegram(text):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        log("Telegram nicht konfiguriert, ueberspringe.")
        return
    try:
        params = urllib.parse.urlencode({
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": "true",
        })
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage?{params}"
        urllib.request.urlopen(urllib.request.Request(url), timeout=15)
        log("Telegram-Nachricht gesendet.")
    except Exception as e:
        log(f"Telegram-Fehler: {e}")

# ─── Scraping ────────────────────────────────────────────────────────────────

async def accept_cookies(page):
    try:
        btn = page.locator("button.c24-cookie-consent-button, button:has-text('geht klar')")
        if await btn.count() > 0:
            await btn.first.click()
            await page.wait_for_timeout(1000)
    except Exception:
        pass


async def scrape_hotel(page, hotel):
    url = hotel["url"]
    hotel_id = hotel["id"]
    log(f"  Lade Hotel {hotel_id}...")

    try:
        await page.goto(url, wait_until="networkidle", timeout=60000)
        await accept_cookies(page)
        await page.wait_for_timeout(5000)

        # Hotelname
        hotel_name = None
        detail_box = page.locator(".js-hotel-detail-box")
        if await detail_box.count() > 0:
            raw = await detail_box.get_attribute("data-hotel")
            if raw:
                try:
                    hotel_name = json.loads(raw).get("name")
                except Exception:
                    pass
        if not hotel_name:
            title = await page.title()
            if title and " - " in title:
                hotel_name = title.split(" - ")[0].strip()

        # Preis
        preis = None
        price_selectors = [
            ".js-offer-list-box .offer-price-amount",
            ".js-offer-list-box [class*='price'] [class*='amount']",
            ".js-offer-list-box [class*='Price']",
            ".offer-price .price-amount",
            "[class*='offer'] [class*='rice'] [class*='mount']",
            ".price-calendar-min-price",
        ]
        for sel in price_selectors:
            el = page.locator(sel)
            if await el.count() > 0:
                raw_text = await el.first.text_content()
                if raw_text:
                    cleaned = raw_text.replace(".", "").replace(",", ".").strip()
                    digits = "".join(ch for ch in cleaned if ch.isdigit() or ch == ".")
                    if digits:
                        try:
                            preis = float(digits)
                            break
                        except ValueError:
                            continue

        if preis is None:
            content = await page.content()
            matches = re.findall(r'(\d{1,2}\.?\d{3})\s*€', content)
            if matches:
                prices = []
                for m in matches:
                    try:
                        prices.append(float(m.replace(".", "")))
                    except ValueError:
                        pass
                if prices:
                    preis = min(prices)

        log(f"  Hotel: {hotel_name} | Preis: {preis}")
        return hotel_id, hotel_name, preis

    except Exception as e:
        log(f"  Fehler bei Hotel {hotel_id}: {e}")
        return hotel_id, None, None

# ─── Hauptlogik ──────────────────────────────────────────────────────────────

async def main():
    prices_data = load_prices()
    log("=== Starte Preischeck ===")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            locale="de-DE",
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        )
        page = await context.new_page()

        for hotel in HOTELS:
            hotel_id, hotel_name, preis = await scrape_hotel(page, hotel)

            if preis is None:
                log(f"  Kein Preis fuer Hotel {hotel_id}, ueberspringe.")
                continue

            link = clean_url(hotel["url"])
            prev = prices_data.get(hotel_id, {})
            last_price = prev.get("price")
            name = hotel_name or prev.get("name") or f"Hotel {hotel_id}"

            # History aktualisieren
            history = prev.get("history", [])
            history.append({
                "price": preis,
                "timestamp": datetime.now().isoformat(),
            })
            # Max 500 Einträge behalten
            if len(history) > 500:
                history = history[-500:]

            prices_data[hotel_id] = {
                "name": name,
                "price": preis,
                "min_price": min(prev.get("min_price", preis), preis),
                "max_price": max(prev.get("max_price", preis), preis),
                "first_price": prev.get("first_price", preis),
                "url": link,
                "last_check": datetime.now().isoformat(),
                "history": history,
            }

            if last_price is None:
                send_telegram(
                    f"<b>Neues Hotel erfasst</b>\n\n"
                    f"<b>{name}</b>\n"
                    f"Preis: <b>{preis:,.0f} EUR</b>\n\n"
                    f'<a href="{link}">Zum Angebot</a>'
                )
            elif preis != last_price:
                diff = preis - last_price
                pct = (diff / last_price) * 100
                emoji = "\U0001f4c9" if diff < 0 else "\U0001f4c8"
                trend = "GESUNKEN" if diff < 0 else "GESTIEGEN"

                send_telegram(
                    f"{emoji} <b>Preis {trend}</b>\n\n"
                    f"<b>{name}</b>\n"
                    f"Vorher: {last_price:,.0f} EUR\n"
                    f"Jetzt: <b>{preis:,.0f} EUR</b>\n"
                    f"Differenz: {diff:+,.0f} EUR ({pct:+.1f}%)\n\n"
                    f'<a href="{link}">Zum Angebot</a>'
                )
            else:
                log(f"  Preis unveraendert: {preis:,.0f} EUR")

        await browser.close()

    # Zusammenfassung senden falls passende Uhrzeit
    current_hour = datetime.now().hour
    if current_hour in SUMMARY_HOURS:
        lines = [f"<b>Preisübersicht — {datetime.now().strftime('%d.%m.%Y %H:%M')}</b>\n"]
        for hid, info in prices_data.items():
            current = info["price"]
            first = info.get("first_price", current)
            diff = current - first
            if diff < 0:
                trend_str = f"\U0001f4c9 {diff:+,.0f}"
            elif diff > 0:
                trend_str = f"\U0001f4c8 {diff:+,.0f}"
            else:
                trend_str = "\u2796 0"
            lines.append(
                f"\n<b>{info['name']}</b>\n"
                f"  Aktuell: <b>{current:,.0f} EUR</b>  ({trend_str})\n"
                f"  Min: {info['min_price']:,.0f}  |  Max: {info['max_price']:,.0f}"
            )
        lines.append(f"\n\U0001f4ca {len(prices_data)} Hotels werden überwacht.")
        send_telegram("\n".join(lines))

    save_prices(prices_data)
    log("=== Preischeck abgeschlossen ===")


if __name__ == "__main__":
    asyncio.run(main())
