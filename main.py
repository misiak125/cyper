import asyncio
import csv
import logging
import os
import sys
import json
import statistics
import argparse
from datetime import datetime
from playwright.async_api import async_playwright
from config import SHOPS, USER_AGENT
from scraper.searcher import find_product_url
from scraper.browser import fetch_html
from scraper.parser import extract_product_data

# ustawienie ścieżki domowiej w zależności od kompilacji
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))


#ustawienie logowania błędów do pliku
log_path = os.path.join(BASE_DIR, 'scraper.log')
data_dir = os.path.join(BASE_DIR, 'data')

os.makedirs(data_dir, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_path, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

#instalacja przeglądarki
def setup_playwright_browser():
    
    logging.info("Weryfikacja plików silnika przeglądarki (Chromium)...")
    try:
        from playwright._impl._driver import compute_driver_executable, get_driver_env
        import subprocess
        
        driver_executable = compute_driver_executable()
        env = get_driver_env()
        
        
        if isinstance(driver_executable, tuple):
            
            cmd = [*driver_executable, "install", "chromium"]
        else:
            cmd = [driver_executable, "install", "chromium"]
            
        subprocess.check_call(cmd, env=env)
        logging.info("Silnik Chromium jest gotowy do pracy.")
    except Exception as e:
        logging.error(f"Nie udało się zainstalować przeglądarki Playwright: {e}")


async def main(args):
    setup_playwright_browser()


    #zebranie sklepow 
    shops_to_scrape = SHOPS
    if args.shops:
        shops_to_scrape = {k: v for k, v in SHOPS.items() if k in args.shops}
        if not shops_to_scrape:
            logging.error(f"Błąd: Żaden z podanych sklepów {args.shops} nie istnieje w config.py!")
            logging.info(f"Dostępne sklepy to: {list(SHOPS.keys())}")
            return

    shop_stats = {shop: {"attempts": 0, "successes": 0} for shop in shops_to_scrape.keys()}
    
    #ustalenie plików odczytyu i zapisu 
    products_file = os.path.join(data_dir, "products_to_search.json")
    results_file = os.path.join(data_dir, f"results{str(datetime.now()).replace(' ', '_')[:-7]}.csv")

    master_f = None
    master_writer = None
    if args.log_all:
        master_run_file = os.path.join(data_dir, "all_results.csv")
        file_exists = os.path.isfile(master_run_file)
        master_f = open(master_run_file, mode="a", newline="", encoding="utf-8")
        master_writer = csv.writer(master_f)
        if not file_exists:
            master_writer.writerow(headers)

    try:
        with open(products_file, "r", encoding="utf-8") as f:
            all_products = json.load(f)
    except FileNotFoundError:
        logging.error(f"Nie znaleziono pliku {products_file}. Przerywam.")
        return

    products_to_scrape = all_products
    
    if args.products:
        products_to_scrape = []
        for prod in all_products:
            
            prod_id_str = str(prod.get("id", ""))
            prod_name_lower = prod.get("name", "").lower()
            
            for term in args.products:
                term_lower = term.lower()
                if term_lower == prod_id_str or term_lower in prod_name_lower:
                    products_to_scrape.append(prod)
                    break

        if not products_to_scrape:
            logging.error(f"Błąd: Nie znaleziono żadnych produktów pasujących do kryteriów: {args.products}")
            return
            
        logging.info(f"Filtrowanie aktywne. Będę szukał {len(products_to_scrape)} z {len(all_products)} produktów.")

    product_prices = {}

    file_exists = os.path.isfile(results_file)
    csv_file = open(results_file, mode="a", newline="", encoding="utf-8")
    csv_writer = csv.writer(csv_file)
    
    if not file_exists:
        csv_writer.writerow(["Data", "Sklep", "ID", "Nazwa", "Cena", "Podatek", "Dostepnosc", "URL"])

    logging.info("Rozpoczynam scraping")

    try:
        async with async_playwright() as p:
            # uruchomienie przeglądarki
            browser = await p.chromium.launch(headless=False) 
            context = await browser.new_context(user_agent=USER_AGENT)
            page = await context.new_page()


            #pętla orzeszukiwania sklepów
            for shop_name, shop_config in shops_to_scrape.items():
                logging.info(f"--- Przeszukiwanie sklepu: {shop_name} ---")
                
                for product in products_to_scrape:
                    shop_stats[shop_name]["attempts"] += 1
                    logging.info(f"Szukam: {product['name']}...")
                    #wyszukanie właściwego produktu ze strony  
                    product_url = await find_product_url(page, shop_config, product)
                    
                    if product_url:
                        html = await fetch_html(page, product_url, shop_config, product)
                        if html != "":
                            data = extract_product_data(html, shop_config)
                            
                            if data["price"]:
                                shop_stats[shop_name]["successes"] += 1
                                
                                prod_id = product["id"]
                                if prod_id not in product_prices:
                                    product_prices[prod_id] = {"name": product["name"], "prices": []}
                                    
                                product_prices[prod_id]["prices"].append({
                                    "shop": shop_name, 
                                    "price": data["price"]
                                })

                                logging.info(f"Znaleziono! Cena: {data['price']} PLN ({data['tax_info']}) | Dostępny: {data['is_available']}")
                                
                                row = [
                                    datetime.now().strftime("%Y-%m-%d %H:%M"),
                                    shop_name, product["id"], product["name"]+ " " + product["quantity"], 
                                    data["price"], data["tax_info"], 
                                    "Tak" if data["is_available"] else "Nie", 
                                    product_url
                                ]

                                #zapisuje pliku
                                csv_writer.writerow(row)
                                
                                if master_writer:
                                    master_writer.writerow(row)
                            else:
                                logging.warning(f"Zlokalizowano produkt, ale nie udało się wyciągnąć ceny: {product_url}")
                        else:
                            logging.warning(f"Zlokalizowano produkt, ale nieudało się zaznaczyć wariantu: {product_url}")
                    else:
                        logging.warning(f"Nie znaleziono produktu")
                    
                    await asyncio.sleep(1)

            await browser.close()
    except Exception as e:
        logging.exception("Wystąpił błąd podczas działania wyszukiwarki. {e}")
    finally:
        csv_file.close()
        if master_f:
            master_f.close()


        #analiza błędów
        logging.info("=" * 40)
        logging.info("RAPORT KOŃCOWY I ANALIZA BŁĘDÓW:")
        logging.info("=" * 40)

        # 1. Analiza skuteczności sklepów
        for shop, stats in shop_stats.items():
            if stats["attempts"] > 0:
                rate = (stats["successes"] / stats["attempts"]) * 100
                
                # Progi alarmowe: 
                # < 20% to krytyczny błąd (prawdopodobnie sklep zmienił układ HTML)
                # < 50% to ostrzeżenie (może produkty zniknęły, albo blokuje nas CAPTCHA)
                if rate < 20:
                    logging.error(f"[KRYTYCZNE] Sklep '{shop}' ma zaledwie {rate:.1f}% skuteczności ({stats['successes']}/{stats['attempts']}).")
                elif rate < 50:
                    logging.warning(f"[OSTRZEŻENIE] Sklep '{shop}' ma niską skuteczność ({rate:.1f}%). Znalazł {stats['successes']} z {stats['attempts']} produktów.")
                else:
                    logging.info(f"[OK] Sklep '{shop}' - Skuteczność: {rate:.1f}%")

        logging.info("-" * 40)

        # 2. Analiza anomalii cenowych
        for prod_id, prod_data in product_prices.items():
            prices_list = [entry["price"] for entry in prod_data["prices"]]
            
            # Aby anomalia miała sens, musimy mieć ceny z minimum 3 różnych sklepów
            if len(prices_list) >= 3:
                median_price = statistics.median(prices_list)
                
                for entry in prod_data["prices"]:
                    price = entry["price"]
                    shop = entry["shop"]
                    
                    # Definicja anomalii: Cena o 30% wyższa lub o 30% niższa od mediany rynkowej
                    lower_bound = median_price * 0.70
                    upper_bound = median_price * 1.30
                    
                    if price < lower_bound or price > upper_bound:
                        diff = ((price - median_price) / median_price) * 100
                        direction = "wyższa" if diff > 0 else "niższa"
                        logging.warning(
                            f"[ANOMALIA] '{prod_data['name']}' w sklepie '{shop}' kosztuje {price} zł. "
                            f"To o {abs(diff):.1f}% {direction} niż rynkowa mediana ({median_price:.2f} zł)!"
                        )

        logging.info("Zakończono scrapowanie i zapisano plik.")


if __name__ == "__main__":

    #flaga sklepow do przeszukania
    parser = argparse.ArgumentParser(description="Scraper cen do e-commerce.")
    parser.add_argument(
        '-s', '--shops', 
        nargs='+',
        help='Wskazane klucze sklepów z config.py do przeszukania. Jeśli brak, przeszuka wszystkie.'
    )
    
    #flaga dopisywania do pliku zbiorowego
    parser.add_argument(
        '-l', '--log-all', 
        action='store_true', 
        
        help='Dopisuj wyniki na koniec zbiorczego pliku master_results.csv'
    )

    #flaga wyboru produktów
    parser.add_argument(
        '-p', '--products', 
        nargs='+', 
        help='Filtruje produkty do przeszukania po ID lub fragmencie nazwy (np. -p 101 priaxor).'
    )

    
    
    parsed_args = parser.parse_args()
    asyncio.run(main(parsed_args))