import asyncio
from playwright.async_api import async_playwright
import json

async def scrape_kickass_anime():
    """
    Fungsi ini melakukan scrape SEMUA anime terbaru dari kickass-anime.ru
    dan menangani lazy loading untuk gambar poster.
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        )
        page = await context.new_page()

        try:
            await page.goto("https://kickass-anime.ru/", timeout=90000)
            print("Berhasil membuka halaman utama.")

            await page.wait_for_selector(".latest-update .row.mt-0 .show-item", timeout=60000)
            print("Bagian 'Latest Update' ditemukan.")

            anime_items = await page.query_selector_all(".latest-update .row.mt-0 .show-item")
            print(f"Menemukan {len(anime_items)} item anime terbaru.")

            scraped_data = []

            # --- [PERBAIKAN 1] Batasan '[:5]' dihapus untuk memproses semua item ---
            for index, item in enumerate(anime_items):
                print(f"\n--- Memproses Item #{index + 1} ---")
                detail_page = None
                try:
                    # --- [PERBAIKAN 2] Scroll ke item untuk memicu lazy loading gambar ---
                    await item.scroll_into_view_if_needed()
                    await page.wait_for_timeout(100) # Beri jeda sesaat agar gambar sempat dimuat

                    poster_url = "Tidak tersedia"
                    poster_div = await item.query_selector(".v-image__image")
                    if poster_div:
                        poster_style = await poster_div.get_attribute("style")
                        if poster_style and 'url("' in poster_style:
                            parts = poster_style.split('url("')
                            if len(parts) > 1:
                                poster_url = parts[1].split('")')[0]
                    print(f"URL Poster: {poster_url}")

                    detail_link_element = await item.query_selector("h2.show-title a")
                    if not detail_link_element:
                        print("Gagal menemukan link judul seri, melewati item ini.")
                        continue
                        
                    detail_url = await detail_link_element.get_attribute("href")
                    full_detail_url = f"https://kickass-anime.ru{detail_url}"
                    print(f"Membuka halaman detail seri: {full_detail_url}")

                    detail_page = await context.new_page()
                    await detail_page.goto(full_detail_url, timeout=90000)
                    
                    await detail_page.wait_for_selector(".anime-info-card", timeout=30000)

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
                    
                    print(f"Sinopsis: {synopsis[:50].strip()}...")

                    genre_elements = await detail_page.query_selector_all(".anime-info-card .v-chip--outlined .v-chip__content")
                    all_tags = [await genre.inner_text() for genre in genre_elements]
                    
                    irrelevant_tags = ['TV', 'PG-13', 'Airing', '2025', '23 min', '24 min', 'SUB', 'DUB', 'ONA']
                    genres = [tag for tag in all_tags if tag not in irrelevant_tags and not tag.startswith('EP')]
                    print(f"Genre: {genres}")

                    anime_info = {
                        "judul": title.strip(),
                        "sinopsis": synopsis.strip(),
                        "genre": genres,
                        "url_poster": poster_url
                    }
                    scraped_data.append(anime_info)

                    await detail_page.close()

                except Exception as e:
                    print(f"!!! Gagal mengambil data untuk item #{index + 1}: {e}")
                    if detail_page and not detail_page.is_closed():
                        await detail_page.close()

            print("\n" + "="*50)
            print(f"HASIL SCRAPING SELESAI. Total {len(scraped_data)} data berhasil diambil.")
            print("="*50)
                
            with open('anime_data.json', 'w', encoding='utf-8') as f:
                json.dump(scraped_data, f, ensure_ascii=False, indent=4)
            print("\nData berhasil disimpan ke anime_data.json")

        except Exception as e:
            print(f"Terjadi kesalahan fatal: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(scrape_kickass_anime())
