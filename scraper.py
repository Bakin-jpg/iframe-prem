import asyncio
from playwright.async_api import async_playwright
import json
from urllib.parse import urljoin

async def scrape_kickass_anime():
    """
    Mengambil poster dari halaman utama dengan andal menggunakan scroll dan wait,
    lalu mengambil sisa data dari halaman detail.
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        )
        page = await context.new_page()

        try:
            base_url = "https://kickass-anime.ru/"
            await page.goto(base_url, timeout=90000, wait_until="domcontentloaded")
            print("Berhasil membuka halaman utama.")

            await page.wait_for_selector(".latest-update .row.mt-0 .show-item", timeout=60000)
            print("Bagian 'Latest Update' ditemukan.")

            anime_items = await page.query_selector_all(".latest-update .row.mt-0 .show-item")
            print(f"Menemukan {len(anime_items)} item anime terbaru.")

            scraped_data = []

            for index, item in enumerate(anime_items):
                print(f"\n--- Memproses Item #{index + 1} ---")
                detail_page = None
                try:
                    # --- [STRATEGI POSTER BARU DAN ANDAL] ---
                    # 1. Scroll ke item untuk memicu lazy loading
                    await item.scroll_into_view_if_needed()
                    
                    # 2. Tunggu secara eksplisit hingga gambar dimuat (maksimal 5 detik)
                    poster_div = await item.query_selector(".v-image__image--cover")
                    try:
                        await poster_div.wait_for_element_state("stable", timeout=5000)
                        await page.wait_for_function(
                            """(element) => {
                                const style = window.getComputedStyle(element);
                                return style.backgroundImage && style.backgroundImage !== 'none';
                            }""",
                            poster_div,
                            timeout=5000
                        )
                    except Exception as wait_error:
                        print(f"Peringatan: Gagal menunggu gambar poster dimuat: {wait_error}")

                    # 3. Ekstrak URL poster setelah menunggu
                    poster_url = "Tidak tersedia"
                    if poster_div:
                        poster_style = await poster_div.get_attribute("style")
                        if poster_style and 'url("' in poster_style:
                            parts = poster_style.split('url("')
                            if len(parts) > 1:
                                poster_url_path = parts[1].split('")')[0]
                                poster_url = urljoin(base_url, poster_url_path)
                    print(f"URL Poster: {poster_url}")

                    # --- Logika Mengambil Data Detail (yang sudah berhasil) ---
                    detail_link_element = await item.query_selector("h2.show-title a")
                    if not detail_link_element:
                        print("Gagal menemukan link judul seri, melewati item ini.")
                        continue
                        
                    detail_url_path = await detail_link_element.get_attribute("href")
                    full_detail_url = urljoin(base_url, detail_url_path)
                    print(f"Membuka halaman detail seri: {full_detail_url}")

                    detail_page = await context.new_page()
                    await detail_page.goto(full_detail_url, timeout=90000)
                    
                    await detail_page.wait_for_selector(".anime-info-card .v-card__title span", timeout=30000)
                    title_element = await detail_page.query_selector(".anime-info-card .v-card__title span")
                    title = await title_element.inner_text() if title_element else "Judul tidak ditemukan"
                    print(f"Judul: {title.strip()}")

                    synopsis_card_title = await detail_page.query_selector("div.v-card__title:has-text('Synopsis')")
                    synopsis = "Sinopsis tidak ditemukan"
                    if synopsis_card_title:
                        parent_card = await synopsis_card_title.query_selector("xpath=..")
                        synopsis_element = await parent_card.query_selector("div.text-caption")
                        if synopsis_element:
                            synopsis = await synopsis_element.inner_text()
                    
                    genre_elements = await detail_page.query_selector_all(".anime-info-card .v-chip--outlined .v-chip__content")
                    all_tags = [await genre.inner_text() for genre in genre_elements]
                    irrelevant_tags = ['TV', 'PG-13', 'Airing', '2025', '23 min', '24 min', 'SUB', 'DUB', 'ONA']
                    genres = [tag for tag in all_tags if tag not in irrelevant_tags and not tag.startswith('EP')]

                    anime_info = {
                        "judul": title.strip(),
                        "sinopsis": synopsis.strip(),
                        "genre": genres,
                        "url_poster": poster_url
                    }
                    scraped_data.append(anime_info)
                    await detail_page.close()

                except Exception as e:
                    print(f"!!! Gagal memproses item #{index + 1}: {type(e).__name__}: {e}")
                    if detail_page and not detail_page.is_closed():
                        await detail_page.close()

            print("\n" + "="*50)
            print(f"HASIL SCRAPING SELESAI. Total {len(scraped_data)} data berhasil diambil.")
            print("="*50)
                
            with open('anime_data.json', 'w', encoding='utf-8') as f:
                json.dump(scraped_data, f, ensure_ascii=False, indent=4)
            print("\nData berhasil disimpan ke anime_data.json")

        except Exception as e:
            print(f"Terjadi kesalahan fatal: {type(e).__name__}: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(scrape_kickass_anime())
