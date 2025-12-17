from flask import Flask, render_template
import requests
from bs4 import BeautifulSoup
import time
import random
from datetime import datetime

app = Flask(__name__)

# Tarayıcı gibi görünmek için gerekli kimlik bilgisi
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9',
}

def get_steam_data():
    """Steam İndirimli Oyunları - Sayfalarca Veri Çeker"""
    base_url = "https://store.steampowered.com/search/results/"
    games_list = []
    print("\n--- Steam Taranıyor (Genişletilmiş) ---")
    
    # DİKKAT: Steam'de binlerce indirim olabilir. 
    # Sonsuz döngüye girmemesi için şimdilik 'max_pages' koyuyoruz.
    # Tümünü istersen bu sayıyı arttırabilirsin (Örn: 50).
    max_pages = 5  
    count_per_page = 50 
    
    start = 0
    page = 1

    while page <= max_pages:
        print(f"Steam Sayfa {page} taranıyor...")
        # Steam 'infinite scroll' yapısını parametrelerle yönetir
        params = {
            'specials': 1,
            'l': 'turkish',
            'start': start,
            'count': count_per_page,
            'infinite': 1
        }
        
        try:
            response = requests.get(base_url, headers=HEADERS, params=params, timeout=10)
            if response.status_code == 200:
                # Steam JSON ve HTML karışık dönebilir, genelde bu endpoint HTML snippet döner
                data = response.json()
                html_content = data.get('results_html', '')
                
                soup = BeautifulSoup(html_content, 'html.parser')
                rows = soup.select('a.search_result_row')
                
                if not rows:
                    print("Steam: Başka oyun kalmadı.")
                    break

                for row in rows:
                    try:
                        title = row.find('span', class_='title').text.strip()
                        price_div = row.find('div', class_='discount_final_price')
                        price = price_div.text.strip() if price_div else "Fiyat Yok"
                        link = row.get('href')
                        
                        img_tag = row.find('img')
                        img_url = img_tag.get('src') if img_tag else ""
                        
                        games_list.append({
                            'name': title, 'price': price, 'image': img_url, 'link': link, 'store': 'steam'
                        })
                    except: continue
                
                start += count_per_page
                page += 1
                # IP ban yememek için minik bir bekleme
                time.sleep(1) 
            else:
                print("Steam yanıt vermedi.")
                break
        except Exception as e:
            print(f"Steam Hatası: {e}")
            break
            
    return games_list

def get_itchio_data():
    """Itch.io - 'Bağlantı Koptu' Hatasına Karşı Korumalı Mod"""
    base_url = "https://itch.io/games/on-sale"
    games_list = []
    print("\n--- Itch.io Taranıyor (Korumalı Mod) ---")

    max_pages = 5
    current_page = 1

    # Oturum açarak bağlantıyı daha kararlı tutmaya çalışalım
    session = requests.Session()
    session.headers.update(HEADERS)

    while current_page <= max_pages:
        print(f"Itch.io Sayfa {current_page} taranıyor...")
        
        try:
            url = f"{base_url}?page={current_page}"
            
            # Bağlantı hatası olursa diye try-except bloğu
            response = session.get(url, timeout=20)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                cells = soup.find_all('div', class_='game_cell')
                
                if not cells:
                    print("Itch.io: Başka oyun kalmadı.")
                    break
                
                for cell in cells:
                    try:
                        title_tag = cell.find('a', class_='title')
                        if not title_tag: continue
                        title = title_tag.text.strip()
                        
                        link = title_tag.get('href')
                        if link and not link.startswith('http'):
                            link = f"https://itch.io{link}"

                        price_tag = cell.find('div', class_='price_value') or cell.find('div', class_='sale_tag')
                        price = price_tag.text.strip() if price_tag else "İndirimde"
                        
                        img_div = cell.find('div', class_='game_thumb')
                        img_url = img_div.get('data-background_image', '') if img_div else ""
                        
                        games_list.append({
                            'name': title, 'price': price, 'image': img_url, 'link': link, 'store': 'itch'
                        })
                    except: continue
                
                # Başarılı olursa bir sonraki sayfaya geç
                current_page += 1
                time.sleep(3) # Beklemeyi 3 saniyeye çıkardık, sunucu sakinleşsin
                
            else:
                print(f"Itch.io Hata Kodu: {response.status_code}")
                break

        except (requests.exceptions.ConnectionError, requests.exceptions.ChunkedEncodingError) as e:
            # İŞTE BURASI ÇÖKMEYİ ENGELLER
            print(f"Itch.io Bağlantıyı Kesti (Sayfa {current_page} atlanıyor): {e}")
            # Hata veren sayfayı geç, diğerine şans ver
            current_page += 1
            time.sleep(5) # Ceza yedik, 5 saniye bekle
            continue

        except requests.exceptions.Timeout:
            print(f"Itch.io Zaman Aşımı (Sayfa {current_page} atlanıyor)")
            current_page += 1
            continue
            
        except Exception as e:
            print(f"Itch Kritik Hata: {e}")
            break
            
    return games_list

def get_epic_data():
    """Epic Games - Ücretsizler (Epic) + İndirimler (CheapShark API)"""
    games_list = []
    print("\n--- Epic Games Taranıyor (Hibrit Mod) ---")
    
    # -----------------------------------------------------------
    # BÖLÜM 1: ÜCRETSİZ OYUNLAR (Epic Statik Endpoint - Çalışıyor)
    # -----------------------------------------------------------
    try:
        free_url = "https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions"
        response = requests.get(free_url, headers=HEADERS, timeout=10)
        if response.status_code == 200:
            data = response.json()
            elements = data['data']['Catalog']['searchStore']['elements']
            print(f"Epic Ücretsiz: {len(elements)} öge bulundu.")

            for game in elements:
                promotions = game.get('promotions')
                if promotions and promotions.get('promotionalOffers') and len(promotions['promotionalOffers']) > 0:
                    title = game['title']
                    slug = game.get('productSlug') or game.get('urlSlug')
                    link = f"https://store.epicgames.com/p/{slug}" if slug else "https://store.epicgames.com/free-games"
                    
                    img_url = ""
                    for img in game.get('keyImages', []):
                        if img.get('type') in ['Thumbnail', 'OfferImageWide', 'DieselStoreFrontWide']:
                            img_url = img.get('url')
                            break
                    
                    games_list.append({
                        'name': title, 
                        'price': "ÜCRETSİZ", 
                        'image': img_url, 
                        'link': link, 
                        'store': 'epic'
                    })
    except Exception as e:
        print(f"Epic Free Hatası: {e}")

    # -----------------------------------------------------------
    # BÖLÜM 2: İNDİRİMLİ OYUNLAR (CheapShark API - Garanti Çözüm)
    # -----------------------------------------------------------
    # CheapShark Store ID'leri: Steam=1, Epic Games Store=25
    try:
        # Epic Games (ID:25) mağazasındaki fırsatları çekiyoruz.
        # pageSize=20 -> 20 oyun getirir. Arttırabilirsin.
        cs_url = "https://www.cheapshark.com/api/1.0/deals?storeID=25&pageSize=20&sortBy=Savings"
        
        response = requests.get(cs_url, headers=HEADERS, timeout=10)
        
        if response.status_code == 200:
            deals = response.json()
            print(f"CheapShark (Epic İndirimleri): {len(deals)} öge çekildi.")
            
            for deal in deals:
                title = deal.get('title')
                
                # Eğer oyun zaten ücretsiz listesinde varsa tekrar ekleme
                if any(g['name'] == title for g in games_list):
                    continue

                normal_price = deal.get('normalPrice')
                sale_price = deal.get('salePrice')
                
                # CheapShark'ın verdiği resimler bazen çok küçüktür, 
                # ama "steam" kelimesini "capsule_sm_120" ile değiştirerek büyütme taktikleri vardır
                # şimdilik direkt alıyoruz.
                thumb = deal.get('thumb')
                
                # DealID ile yönlendirme linki
                deal_id = deal.get('dealID')
                link = f"https://www.cheapshark.com/redirect?dealID={deal_id}"
                
                # Gösterim: "$100 -> $20" (CheapShark genelde USD döner ama oran doğrudur)
                # Not: CheapShark fiyatları genelde Dolar bazlıdır. 
                # Ancak TL simgesi yerine genel bir indirim oranı da yazdırabiliriz.
                # Basitlik adına fiyatları olduğu gibi yazıyoruz.
                price_str = f"${normal_price} -> ${sale_price}"

                games_list.append({
                    'name': title,
                    'price': price_str,
                    'image': thumb,
                    'link': link,
                    'store': 'epic'
                })
        else:
            print(f"CheapShark Yanıt Vermedi: {response.status_code}")

    except Exception as e:
        print(f"CheapShark Hatası: {e}")

    return games_list

@app.route('/')
def index():
    # Verileri çek
    steam = get_steam_data()
    itch = get_itchio_data()
    epic = get_epic_data()
    
    # Python'da tarih hesaplamaya veya stats sözlüğüne GEREK YOK.
    # Direkt verileri gönderiyoruz.
    return render_template('index.html', steam_games=steam, itch_games=itch, epic_games=epic)

if __name__ == '__main__':
    app.run(debug=True, port=5001)
