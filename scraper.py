import asyncio
from playwright.async_api import async_playwright
import json
from urllib.parse import urljoin
import re

async def scrape_episodes_via_api(context, base_url, anime_slug):
    """
    Scrape daftar episode menggunakan API, lalu kunjungi episode terpilih
    untuk mendapatkan URL iframe.
    """
    episodes_data = []
    api_url = urljoin(base_url, f"/api/show/{anime_slug}/episodes")
    
    try:
        # Gunakan context untuk membuat halaman sementara untuk request API
        api_page = await context.new_page()
        print(f"   -> Mengambil daftar episode dari API: {api_url}")
        
        # Pergi ke URL API dan dapatkan konten JSON-nya
        await api_page.goto(api_url)
        json_response = await api_page.json()
        await api_page.close()

        if not json_response or 'result' not in json_response or not json_response['result']:
            print("   -> API tidak mengembalikan data episode.")
            return []

        all_episodes = json_response['result']
        print(f"   -> API mengembalikan total {len(all_episodes)} episode.")

        # Urutkan episode berdasarkan nomor, dari terbaru ke terlama
        # Menggunakan float untuk menangani episode .5
        all_episodes.sort(key=lambda x: float(x.get('episode_number', 0)), reverse=True)

        episodes_to_scrape = all_episodes
        # Terapkan logika cicilan
        if len(all_episodes) > 20:
            print(f"   -> Lebih dari 20 episode, menerapkan cicilan (mengambil 10 terbaru).")
            episodes_to_scrape = all_episodes[:10]

        print(f"   -> Akan men-scrape detail untuk {len(episodes_to_scrape)} episode.")

        for episode in episodes_to_scrape:
            ep_slug = episode.get('slug')
            ep_number_text = f"EP {episode.get('episode_string', '')}"
            if not ep_slug:
                continue

            ep_url = urljoin(base_url, f"{anime_slug}/{ep_slug}")
            ep_page = None
            try:
                print(f"      -> Mengambil iframe untuk {ep_number_text}...")
                ep_page = await context.new_page()
                await ep_page.goto(ep_url, timeout=60000, wait_until="domcontentloaded")
                await ep_page.wait_for_selector("iframe.player", timeout=30000)

                iframe_element = await ep_page.query_selector("iframe.player")
                iframe_src = await iframe_element.get_attribute("src") if iframe_element else "iframe tidak ditemukan"
                
                # Logika untuk mendeteksi bahasa dan membuat URL server
                base_iframe_src = iframe_src.split('&ln=')[0] if '&ln=' in iframe_src else iframe_src
                available_languages = {}

                sub_dub_dropdown = await ep_page.query_selector("div.v-select__slot:has-text('Sub/Dub')")
                if sub_dub_dropdown:
                    await sub_dub_dropdown.click()
                    await ep_page.wait_for_timeout(500)
                    lang_options = await ep_page.query_selector_all(".v-menu__content.menuable__content__active .v-list-item__title")
                    for lang_option in lang_options:
                        lang_text = (await lang_option.inner_text()).upper()
                        if "JAPANESE" in lang_text or "SUB" in lang_text:
                            available_languages["SUB"] = f"{base_iframe_src}&ln=ja-JP"
                        if "ENGLISH" in lang_text or "DUB" in lang_text:
                            available_languages["DUB"] = f"{base_iframe_src}&ln=en-US"
                        if "ESPAÑOL" in lang_text:
                            available_languages["ES"] = f"{base_iframe_src}&ln=es-ES"
                    await ep_page.click("body", position={"x": 5, "y": 5})
                else:
                    available_languages["SUB"] = iframe_src
                
                if "vidstream" not in iframe_src.lower():
                    available_languages["CN"] = iframe_src

                episodes_data.append({"episode": ep_number_text, "servers": {k: v for k, v in available_languages.items() if v}})
                await ep_page.close()

            except Exception as e:
                print(f"      -> Gagal mengambil iframe untuk {ep_number_text}: {type(e).__name__}: {e}")
                if ep_page and not ep_page.is_closed():
                    await ep_page.close()
        
        return episodes_data

    except Exception as e:
        print(f"   -> Gagal total saat mengambil daftar episode dari API: {type(e).__name__}: {e}")
        if 'api_page' in locals() and not api_page.is_closed():
            await api_page.close()
        return []


async def scrape_kickass_anime():
    """
    Fungsi utama untuk scrape data anime dan memanggil fungsi scrape episode via API.
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36",
            viewport={'width': 1920, 'height': 1080}
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

            for index, item in enumerate(anime_items[:5]): # Ambil 5 anime pertama untuk demonstrasi
                print(f"\n--- Memproses Anime #{index + 1} ---")
                detail_page = None
                try:
                    await item.scroll_into_view_if_needed()
                    
                    poster_url = "Tidak tersedia"
                    for attempt in range(5):
                        poster_div = await item.query_selector(".v-image__image--cover")
                        if poster_div:
                            poster_style = await poster_div.get_attribute("style")
                            if poster_style and 'url("' in poster_style:
                                poster_url_path = poster_style.split('url("')[1].split('")')[0]
                                poster_url = urljoin(base_url, poster_url_path)
                                break
                        await page.wait_for_timeout(300) 
                    
                    detail_link_element = await item.query_selector("h2.show-title a")
                    if not detail_link_element: continue
                        
                    detail_url_path = await detail_link_element.get_attribute("href")
                    # Ekstrak slug dari URL path
                    anime_slug = detail_url_path.strip('/').split('/')[-1]
                    full_detail_url = urljoin(base_url, detail_url_path)
                    
                    detail_page = await context.new_page()
                    await detail_page.goto(full_detail_url, timeout=90000)
                    await detail_page.wait_for_selector(".anime-info-card", timeout=30000)
                    
                    title_element = await detail_page.query_selector(".anime-info-card .v-card__title span")
                    title = await title_element.inner_text() if title_element else "Judul tidak ditemukan"

                    synopsis_card_title = await detail_page.query_selector("div.v-card__title:has-text('Synopsis')")
                    synopsis = "Sinopsis tidak ditemukan"
                    if synopsis_card_title:
                        parent_card = await synopsis_card_title.query_selector("xpath=..")
                        synopsis_element = await parent_card.query_selector(".text-caption")
                        if synopsis_element:
                            synopsis = await synopsis_element.inner_text()
                    
                    genre_elements = await detail_page.query_selector_all(".anime-info-card .v-chip--outlined .v-chip__content")
                    all_tags = [await el.inner_text() for el in genre_elements]
                    irrelevant_tags = ['TV', 'PG-13', 'Airing', '2025', '2024', '23 min', '24 min', 'SUB', 'DUB', 'ONA']
                    genres = [tag for tag in all_tags if tag not in irrelevant_tags and not tag.startswith('EP')]

                    metadata_selector = ".anime-info-card .d-flex.mb-3, .anime-info-card .d-flex.mt-2.mb-3"
                    metadata_container = await detail_page.query_selector(metadata_selector)
                    metadata = []
                    if metadata_container:
                        metadata_elements = await metadata_container.query_selector_all(".text-subtitle-2")
                        all_meta_texts = [await el.inner_text() for el in metadata_elements]
                        metadata = [text.strip() for text in all_meta_texts if text and text.strip() != '•']
                    
                    print(f"   -> Memulai scraping episode untuk: {title.strip()} (slug: {anime_slug})")
                    episodes_list = await scrape_episodes_via_api(context, base_url, anime_slug)

                    anime_info = {"judul": title.strip(), "sinopsis": synopsis.strip(), "genre": genres, "metadata": metadata, "url_poster": poster_url, "episodes": episodes_list}
                    scraped_data.append(anime_info)

                except Exception as e:
                    print(f"!!! Gagal memproses anime #{index + 1}: {type(e).__name__}: {e}")
                finally:
                    if detail_page and not detail_page.is_closed():
                        await detail_page.close()

            print("\n" + "="*50)
            print(f"HASIL SCRAPING SELESAI. Total {len(scraped_data)} anime berhasil diproses.")
            print("="*50)
                
            with open('anime_data_with_episodes.json', 'w', encoding='utf-8') as f:
                json.dump(scraped_data, f, ensure_ascii=False, indent=4)
            print("\nData berhasil disimpan ke anime_data_with_episodes.json")

        except Exception as e:
            print(f"Terjadi kesalahan fatal: {type(e).__name__}: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(scrape_kickass_anime())
