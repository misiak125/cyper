import asyncio
import csv
import logging
import os
import sys
import json
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
            products = json.load(f)
    except FileNotFoundError:
        logging.error(f"Nie znaleziono pliku {products_file}. Przerywam działanie.")
        return

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
                
                for product in products:
                    logging.info(f"Szukam: {product['name']}...")
                    #wyszukanie właściwego produktu ze strony  
                    product_url = await find_product_url(page, shop_config, product)
                    
                    if product_url:
                        html = await fetch_html(page, product_url, shop_config, product)
                        data = extract_product_data(html, shop_config)
                        
                        if data["price"]:
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
                    
                    await asyncio.sleep(1)

            await browser.close()
    except Exception as e:
        logging.exception("Wystąpił błąd podczas działania wyszukiwarki. {e}")
    finally:
        csv_file.close()
        if master_f:
            master_f.close()

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
    
    
    parsed_args = parser.parse_args()
    asyncio.run(main(parsed_args))