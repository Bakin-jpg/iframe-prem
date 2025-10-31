# scraper.py (Final Version - Mengambil data dari JSON di dalam <script>)

import json
import time
import os
import re
from playwright.sync_api import sync_playwright, TimeoutError

DATABASE_FILE = "anime_database.json"

def load_database():
    """Memuat database dari file JSON. Menggunakan JUDUL ANIME sebagai kunci unik."""
    if os.path.exists(DATABASE_FILE):
        try:
            with open(DATABASE_FILE, 'r', encoding='utf-8') as f:
                print(f"Database '{DATABASE_FILE}' ditemukan dan dimuat.")
                return {show['title']: show for show in json.load(f)}
        except (json.JSONDecodeError, KeyError, TypeError):
            print(f"[PERINGATAN] File database '{DATABASE_FILE}' rusak atau formatnya lama. Memulai dari awal.")
            return {}
    print(f"Database '{DATABASE_FILE}' tidak ditemukan. Akan membuat yang baru.")
    return {}

def save_database(data_dict):
    """Menyimpan data dari dictionary kembali ke file JSON, diurutkan berdasarkan judul."""
    sorted_data = sorted(data_dict.values(), key=lambda x: x.get('title', ''))
    with open(DATABASE_FILE, 'w', encoding='utf-8') as f:
        json.dump(sorted_data, f, ensure_ascii=False, indent=4)
    print(f"   Database berhasil disimpan.")

def get_shows_from_main_page(page):
    """
    METODE BARU: Ekstrak data langsung dari objek JavaScript 'window.KAA'
    yang ada di dalam HTML. Ini lebih cepat dan jauh lebih andal.
    """
    url = "https://kickass-anime.ru/"
    print("\n=== TAHAP 1: MENGAMBIL DATA ANIME DARI SCRIPT TAG ===")
    shows = {}
    try:
        page.goto(url, timeout=120000, wait_until='domcontentloaded')
        
        # Ambil seluruh konten HTML halaman
        html_content = page.content()
        
        # Gunakan regex untuk menemukan blok 'latestShow' di dalam script
        match = re.search(r'latestShow:(\[.*?\]),trendingShow', html_content, re.DOTALL)
        
        if not match:
            print("[ERROR] Tidak dapat menemukan blok data 'latestShow' di dalam halaman.")
            return []
        
        # Grup 1 dari match adalah string array '[{...}, {...}]'
        latest_show_str = match.group(1)

        # Temukan semua objek di dalam string array (setiap objek adalah satu anime)
        anime_objects = re.findall(r'({.*?})', latest_show_str, re.DOTALL)

        for obj_str in anime_objects:
            # Ekstrak title_en dan watch_uri dari setiap objek
            title_match = re.search(r'title_en:"(.*?)"', obj_str)
            uri_match = re.search(r'watch_uri:"(.*?)"', obj_str)

            if title_match and uri_match:
                title = title_match.group(1).encode('utf-8').decode('unicode-escape')
                watch_uri = uri_match.group(1).encode('utf-8').decode('unicode-escape')
                
                if title and watch_uri:
                    full_url = "https://kickass-anime.ru" + watch_uri
                    shows[title] = {
                        'title': title,
                        'episode_page_url': full_url
                    }

        print(f"Menemukan {len(shows)} anime unik dari data script.")
        return list(shows.values())

    except Exception as e:
        print(f"[ERROR di Tahap 1] Gagal mengekstrak data anime: {e}")
        return []

def scrape_episodes_from_url(page, episode_page_url, existing_episode_numbers):
    """
    Membuka halaman episode dan mengambil semua link iframe untuk episode baru.
    (Fungsi ini tidak perlu diubah)
    """
    newly_scraped_episodes = []
    try:
        print(f"   - Mengunjungi: {episode_page_url}")
        page.goto(episode_page_url, timeout=90000)
        page.wait_for_selector("div.episode-item", timeout=60000)

        all_on_page_ep_elements = page.locator("div.episode-item").all()
        
        episodes_to_scrape = []
        for el in all_on_page_ep_elements:
            try:
                ep_num = el.locator("span.v-chip__content").inner_text(timeout=2000)
                if ep_num not in existing_episode_numbers:
                    episodes_to_scrape.append(ep_num)
            except TimeoutError:
                continue

        episodes_to_scrape.sort(key=lambda x: int(''.join(filter(str.isdigit, x.split()[-1])) or 0))

        if not episodes_to_scrape:
            print("     Tidak ada episode baru untuk di-scrape.")
            return []

        print(f"     Ditemukan {len(episodes_to_scrape)} episode baru. Memproses...")
        
        for ep_num in episodes_to_scrape:
            try:
                print(f"        - Memproses Episode: {ep_num}")
                page.locator(f"div.episode-item:has-text('{ep_num}')").first.click(timeout=15000)
                
                iframe_src = None
                page.wait_for_selector("div.player-container iframe", state='attached', timeout=20000)
                
                for frame in page.locator("div.player-container iframe").all():
                    src_attr = frame.get_attribute('src') or ''
                    if 'disqus' not in src_attr and src_attr:
                        iframe_src = src_attr
                        print(f"           Iframe ditemukan: {iframe_src[:50]}...")
                        break
                
                if iframe_src:
                    newly_scraped_episodes.append({
                        "episode_number": ep_num,
                        "iframe_url": iframe_src
                    })
                else:
                    print(f"           Gagal menemukan iframe valid untuk episode {ep_num}.")

            except Exception as e:
                print(f"        [PERINGATAN] Gagal memproses episode {ep_num}: {e}")
                continue
                
    except Exception as e:
        print(f"     [ERROR] Gagal memuat/memproses halaman episode. Detail: {e}")

    return newly_scraped_episodes

def main():
    db = load_database()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
        page = context.new_page()

        shows_list = get_shows_from_main_page(page)

        if not shows_list:
            print("Tidak dapat mengambil daftar anime. Program berhenti.")
            if not os.path.exists(DATABASE_FILE):
                save_database({})
            browser.close()
            return
        
        print("\n=== TAHAP 2: MEMPROSES EPISODE SETIAP ANIME ===")
        for show in shows_list:
            title = show['title']
            print(f"\nProcessing: '{title}'")

            if title not in db:
                db[title] = {
                    'title': title,
                    'episode_page_url': show['episode_page_url'],
                    'episodes': []
                }
            
            existing_eps = {ep['episode_number'] for ep in db[title].get('episodes', [])}
            new_episodes = scrape_episodes_from_url(page, show['episode_page_url'], existing_eps)

            if new_episodes:
                db[title]['episodes'].extend(new_episodes)
                db[title]['episodes'].sort(key=lambda x: int(''.join(filter(str.isdigit, x.get('episode_number', '0').split()[-1])) or 0))
                print(f"   Berhasil menambahkan {len(new_episodes)} episode baru untuk '{title}'.")
            
            save_database(db)

        page.close()
        browser.close()
        print("\n=== SEMUA PROSES SELESAI ===")

if __name__ == "__main__":
    main()
