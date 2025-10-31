import asyncio
from playwright.async_api import async_playwright
import json

async def scrape_kickass_anime():
    """
    Fungsi ini melakukan scrape data anime terbaru dari kickass-anime.ru
    menggunakan Playwright.
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

            # Ambil detail untuk beberapa anime pertama (misalnya, 5 anime)
            for item in anime_items[:5]:
                try:
                    # Ambil URL halaman detail anime
                    detail_link_element = await item.query_selector("a.v-card")
                    detail_url = await detail_link_element.get_attribute("href")
                    full_detail_url = f"https://kickass-anime.ru{detail_url}"

                    # Ambil URL Poster dari halaman utama
                    poster_div = await item.query_selector(".v-image__image")
                    poster_style = await poster_div.get_attribute("style")
                    poster_url = poster_style.split('url("')[1].split('")')[0]

                    # Buka halaman detail di tab baru
                    detail_page = await browser.new_page()
                    await detail_page.goto(full_detail_url, timeout=60000)
                    print(f"Membuka halaman detail: {full_detail_url}")

                    # Tunggu hingga elemen sinopsis dan judul muncul
                    await detail_page.wait_for_selector(".show-title", timeout=30000)
                    await detail_page.wait_for_selector(".show-synopsis", timeout=30000)

                    # Ambil judul dari halaman detail
                    title_element = await detail_page.query_selector(".show-title")
                    title = await title_element.inner_text()

                    # Ambil sinopsis
                    synopsis_element = await detail_page.query_selector(".show-synopsis")
                    synopsis = await synopsis_element.inner_text()

                    # Ambil genre
                    genre_elements = await detail_page.query_selector_all(".v-chip.v-chip--label.v-chip--outlined .v-chip__content")
                    genres = [await genre.inner_text() for genre in genre_elements]
                    # Filter out non-genre text like 'TV', 'PG-13', etc.
                    # This part is heuristic and might need adjustment if site structure changes.
                    # Based on the image provided, we will take the first few relevant tags.
                    # A better approach would be to have a more specific selector if available.
                    
                    anime_info = {
                        "judul": title.strip(),
                        "sinopsis": synopsis.strip(),
                        "genre": [g for g in genres if g not in ['TV', 'PG-13', 'Airing', '2025', '24 min', 'SUB', 'DUB']],
                        "url_poster": poster_url
                    }
                    scraped_data.append(anime_info)

                    # Tutup halaman detail
                    await detail_page.close()

                except Exception as e:
                    print(f"Gagal mengambil data untuk satu item: {e}")
                    if 'detail_page' in locals() and not detail_page.is_closed():
                        await detail_page.close()


            # Cetak hasil dalam format yang diminta
            for anime in scraped_data:
                print("\n" + "="*50)
                print(anime['judul'])
                print(", ".join(anime['genre']))
                print("\nSynopsis")
                print(anime['sinopsis'])
                print("\nURL Poster:")
                print(anime['url_poster'])
                print("="*50)
                
            # Simpan ke file JSON jika diperlukan
            with open('anime_data.json', 'w', encoding='utf-8') as f:
                json.dump(scraped_data, f, ensure_ascii=False, indent=4)
            print("\nData berhasil disimpan ke anime_data.json")

        except Exception as e:
            print(f"Terjadi kesalahan: {e}")
        finally:
            await browser.close()

# Jalankan fungsi async
if __name__ == "__main__":
    asyncio.run(scrape_kickass_anime())
