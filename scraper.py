import asyncio
from playwright.async_api import async_playwright
import json

async def scrape_kickass_anime():
    """
    Fungsi ini melakukan scrape data anime terbaru dari kickass-anime.ru
    menggunakan Playwright dengan penanganan error yang lebih baik.
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        try:
            # Buka halaman utama
            await page.goto("https://kickass-anime.ru/", timeout=60000)
            print("Berhasil membuka halaman utama.")

            # Tunggu hingga bagian "Latest Update" muncul
            await page.wait_for_selector(".latest-update .row.mt-0", timeout=30000)
            print("Bagian 'Latest Update' ditemukan.")

            # Ambil semua item anime di bagian "Latest Update"
            anime_items = await page.query_selector_all(".latest-update .row.mt-0 .show-item")
            print(f"Menemukan {len(anime_items)} item anime terbaru.")

            scraped_data = []

            # Ambil detail untuk 5 anime pertama untuk pengujian
            for index, item in enumerate(anime_items[:5]):
                print(f"\n--- Memproses Item #{index + 1} ---")
                try:
                    # 1. Ambil URL Poster dari halaman utama dengan aman
                    poster_url = "Tidak tersedia"  # Nilai default
                    poster_div = await item.query_selector(".v-image__image")
                    if poster_div:
                        poster_style = await poster_div.get_attribute("style")
                        if poster_style and 'url("' in poster_style:
                            parts = poster_style.split('url("')
                            if len(parts) > 1:
                                poster_url = parts[1].split('")')[0]
                    print(f"URL Poster: {poster_url}")

                    # 2. Ambil URL halaman detail anime
                    detail_link_element = await item.query_selector("a.v-card")
                    if not detail_link_element:
                        print("Gagal menemukan link detail, melewati item ini.")
                        continue
                        
                    detail_url = await detail_link_element.get_attribute("href")
                    full_detail_url = f"https://kickass-anime.ru{detail_url}"
                    print(f"Membuka halaman detail: {full_detail_url}")

                    # 3. Buka halaman detail di tab baru dan ekstrak data
                    detail_page = await browser.new_page()
                    await detail_page.goto(full_detail_url, timeout=60000)

                    await detail_page.wait_for_selector(".show-title", timeout=30000)
                    title_element = await detail_page.query_selector(".show-title")
                    title = await title_element.inner_text() if title_element else "Judul tidak ditemukan"
                    print(f"Judul: {title.strip()}")

                    await detail_page.wait_for_selector(".show-synopsis", timeout=30000)
                    synopsis_element = await detail_page.query_selector(".show-synopsis")
                    synopsis = await synopsis_element.inner_text() if synopsis_element else "Sinopsis tidak ditemukan"

                    genre_elements = await detail_page.query_selector_all(".v-chip--outlined .v-chip__content")
                    all_tags = [await genre.inner_text() for genre in genre_elements]
                    
                    # Filter tag yang tidak relevan. Daftar ini mungkin perlu disesuaikan.
                    irrelevant_tags = ['TV', 'PG-13', 'Airing', '2025', '24 min', 'SUB', 'DUB', 'ONA']
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
                    if 'detail_page' in locals() and not detail_page.is_closed():
                        await detail_page.close()

            print("\n" + "="*50)
            print("HASIL SCRAPING SELESAI")
            print("="*50)

            # Cetak hasil akhir
            for anime in scraped_data:
                print(f"\nJudul: {anime['judul']}")
                print(f"Genre: {', '.join(anime['genre'])}")
                print(f"Sinopsis: {anime['sinopsis'][:100]}...") # Tampilkan 100 karakter pertama
                print(f"URL Poster: {anime['url_poster']}")
                
            # Simpan ke file JSON
            with open('anime_data.json', 'w', encoding='utf-8') as f:
                json.dump(scraped_data, f, ensure_ascii=False, indent=4)
            print("\nData berhasil disimpan ke anime_data.json")

        except Exception as e:
            print(f"Terjadi kesalahan fatal: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(scrape_kickass_anime())
