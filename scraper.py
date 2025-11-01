import json
from playwright.sync_api import sync_playwright, TimeoutError
import time

# URL Target
BASE_URL = "https://kickass-anime.ru"
ANIME_LIST_URL = f"{BASE_URL}/anime" 

def run_scraper():
    """
    Fungsi utama untuk menjalankan scraper dengan Playwright.
    """
    all_anime_data = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True) 
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        )
        page = context.new_page()

        try:
            # 1. Buka halaman daftar anime
            print(f"Mengunjungi halaman daftar anime: {ANIME_LIST_URL}")
            page.goto(ANIME_LIST_URL, wait_until='networkidle', timeout=90000)

            # Scroll ke bawah untuk memuat semua anime
            print("Melakukan scroll untuk memuat semua daftar anime...")
            last_height = page.evaluate("document.body.scrollHeight")
            while True:
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(2)
                new_height = page.evaluate("document.body.scrollHeight")
                if new_height == last_height:
                    break
                last_height = new_height
            print("Scroll selesai.")

            # 2. Ambil semua link anime
            anime_locators = page.locator("div.show-item h2.show-title > a")
            anime_elements = anime_locators.all()
            
            anime_links = []
            for element in anime_elements:
                href = element.get_attribute('href')
                title = element.text_content().strip()
                if href:
                    full_url = BASE_URL + href if href.startswith('/') else href
                    anime_links.append({'title': title, 'url': full_url})
            
            print(f"Ditemukan {len(anime_links)} anime.")

            # Loop melalui setiap anime (hapus '[:3]' untuk scrape semua)
            for anime in anime_links[:3]:
                print(f"\n--- Memproses Anime: {anime['title']} ---")
                anime_data = {'title': anime['title'], 'episodes': []}

                try:
                    # 3. Kunjungi halaman detail anime
                    page.goto(anime['url'], wait_until='domcontentloaded', timeout=60000)
                    
                    # Selector untuk daftar episode
                    episode_locators = page.locator("a.v-list-item[href*='/ep-']")
                    episode_locators.first.wait_for(timeout=15000)
                    episode_elements = episode_locators.all()
                    
                    episode_links = []
                    for element in episode_elements:
                        href = element.get_attribute('href')
                        if href:
                            full_url = BASE_URL + href if href.startswith('/') else href
                            episode_links.append(full_url)
                    
                    print(f"Ditemukan {len(episode_links)} episode.")
                    episode_links.reverse()

                    # 4. Kunjungi setiap halaman episode (dibatasi 2 untuk tes)
                    for episode_url in episode_links[:2]:
                        try:
                            page.goto(episode_url, wait_until='domcontentloaded', timeout=60000)
                            
                            # Selector untuk iframe video
                            iframe_locator = page.locator("div#player iframe")
                            iframe_locator.wait_for(timeout=15000)
                            
                            iframe_src = iframe_locator.get_attribute('src')
                            if iframe_src:
                                print(f"  [OK] Ditemukan iframe: {iframe_src}")
                                anime_data['episodes'].append({
                                    'episode_url': episode_url,
                                    'iframe_url': iframe_src
                                })
                            else:
                                print(f"  [WARN] Iframe tidak memiliki src untuk {episode_url}")
                                
                        except TimeoutError:
                            print(f"  [ERROR] Timeout mencari iframe di {episode_url}")
                        except Exception as e:
                            print(f"  [ERROR] Gagal memproses {episode_url}: {e}")

                except Exception as e:
                    print(f"Gagal memproses episode untuk {anime['title']}: {e}")

                if anime_data['episodes']:
                    all_anime_data.append(anime_data)

        except Exception as e:
            print(f"Terjadi kesalahan fatal: {e}")
        finally:
            browser.close()

    # 5. Simpan hasil ke file JSON
    with open('anime_iframes.json', 'w', encoding='utf-8') as f:
        json.dump(all_anime_data, f, indent=4, ensure_ascii=False)

    print("\nProses scraping selesai. Hasil disimpan di anime_iframes.json")

if __name__ == '__main__':
    run_scraper()
