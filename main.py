from playwright.async_api import TimeoutError as PlaywrightTimeoutError, Error as PlaywrightError
import aiohttp
import asyncio
import csv
import logging
import time
import os
import sys
import json
import random
import statistics
import argparse
from datetime import datetime
from tqdm import tqdm
from config import SHOPS, USER_AGENTS
from scraper.searcher import find_product_url
from scraper.browser import fetch_html
from scraper.parser import extract_product_data

# ustawienie ścieżki domowiej w zależności od kompilacji
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

if getattr(sys, 'frozen', False):
    custom_browser_path = os.path.join(os.path.expanduser("~"), "AppData", "Local", "CyperScraperBrowsers")
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = custom_browser_path

from playwright.async_api import async_playwright
from playwright_stealth import Stealth

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

# maksymalna liczba zadan jednoczesnie obslugiwanych
MAX_CONCURRENT_SHOPS = 6

async def process_shop(semaphore, browser, shop_name, shop_config, products_to_scrape, 
                       csv_writer, csv_file, master_writer, master_f, csv_lock, shop_stats, product_prices):
    """
    asynchroniczna funkcja obsługująca wskazany sklep
    """
    MAX_CONSECUTIVE_ERRORS = 3 
    consecutive_errors = 0
    async with semaphore:
        logging.info(f"[{shop_name}] Uruchamiam agenta dla sklepu...")
        
        #losowanie kolejnosci produktow
        randomized_products = list(products_to_scrape)
        random.shuffle(randomized_products)
        
        #konfiguracja przeglądarki
        current_ua = random.choice(USER_AGENTS)
        context = await browser.new_context(user_agent=current_ua)
        page = await context.new_page()
        
        try:
            for product in randomized_products:
                shop_stats[shop_name]["attempts"] += 1
                
                #rezygnuje jesli sklep wielokrotnie zdaje sie odmawiac polaczenia
                if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                    logging.error(f"[{shop_name}] Zbyt wiele błędów sieciowych (Timeout/Brak połączenia). Zaprzestaję wyszukiwania w tym sklepie.")
                    break
                    
                logging.info(f"[{shop_name}] Szukam: {product['name']}...")
                try:
					# znajdujemy produkt  
                    product_url = await find_product_url(page, shop_name, shop_config, product)

					
					
                    if product_url:
                        html = await fetch_html(page, product_url, shop_name, shop_config, product)
						
                        consecutive_errors = 0
						
                        #pobranie danych i formatoanie CSV
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

                                logging.info(f"[{shop_name}][{product['name']}] Znaleziono! Cena: {data['price']} PLN ({data['tax_info']}) | Dostępny: {data['is_available']}")
								
                                row = [
									datetime.now().strftime("%Y-%m-%d %H:%M"),
									shop_name, product["id"], product["name"] + " " + product.get("quantity", ""), 
									data["price"], data["tax_info"], 
									"Tak" if data["is_available"] else "Nie", 
									product_url
								]

								# zablokowanie dostepu do plikow na czas zapisu
                                async with csv_lock:
                                    csv_writer.writerow(row)
                                    csv_file.flush() 
									
                                    if master_writer:
                                        master_writer.writerow(row)
                                        master_f.flush()
                            else:
                                logging.warning(f"[{shop_name}][{product['name']}] Zlokalizowano produkt, ale nie udało się wyciągnąć ceny: {product_url}")
                        else:
                            logging.warning(f"[{shop_name}][{product['name']}] Zlokalizowano produkt, ale nie udało się zaznaczyć wariantu: {product_url}")
                    else:
                        logging.info(f"[{shop_name}][{product['name']}] Nie znaleziono produktu")
                except PlaywrightTimeoutError as e:
                    consecutive_errors += 1
					
            await asyncio.sleep(shop_config["slow"]*random.uniform(4, 7))
                
        except Exception as e:
            consecutive_errors = 0
            logging.exception(f"[{shop_name}] Wystąpił błąd podczas działania wyszukiwarki: {e}")
        finally:
            await context.close()


async def main(args):
    setup_playwright_browser()

    # Zebranie sklepów 
    shops_to_scrape = SHOPS
    if args.shops:
        shops_to_scrape = {k: v for k, v in SHOPS.items() if k in args.shops}
        if not shops_to_scrape:
            logging.error(f"Błąd: Żaden z podanych sklepów {args.shops} nie istnieje w config.py!")
            logging.info(f"Dostępne sklepy to: {list(SHOPS.keys())}")
            return

    shop_stats = {shop: {"attempts": 0, "successes": 0} for shop in shops_to_scrape.keys()}
    
    # ustalenie plikow odczytu i zapisu 
    products_file = os.path.join(data_dir, "products_to_search.json")
    results_file = os.path.join(data_dir, f"results_{datetime.now().strftime('%Y_%m_%d__%H_%M')}.csv")

    master_f = None
    master_writer = None
    headers = ["Data", "Sklep", "ID", "Nazwa", "Cena", "Podatek", "Dostepnosc", "URL"]
    
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
        csv_writer.writerow(headers)

    logging.info("Rozpoczynam scraping")

    # inicjalizacja async
    csv_lock = asyncio.Lock()
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_SHOPS)

    try:
        async with Stealth().use_async(async_playwright()) as p:
            # uruchomienie przegladarki
            browser = await p.chromium.launch(headless=False,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-automation',
                    '--no-sandbox',
                    '--window-size=1920,1080'
                ]
            )

            # zeebranie zadan scrapowania sklepow
            tasks = []
            
            # losowanie kolejnosci sklepow
            shops_list = list(shops_to_scrape.items())
            random.shuffle(shops_list)
            
            for shop_name, shop_config in shops_list:
                task = asyncio.create_task(
                    process_shop(
                        semaphore, browser, shop_name, shop_config, products_to_scrape, 
                        csv_writer, csv_file, master_writer, master_f, csv_lock, shop_stats, product_prices
                    )
                )
                tasks.append(task)
                
            # uruchomienie scrapowania
            await asyncio.gather(*tasks)

            await browser.close()
            
    except Exception as e:
        logging.exception(f"Wystąpił globalny błąd podczas działania mechanizmu Playwright: {e}")
    finally:
        csv_file.close()
        if master_f:
            master_f.close()

        # podsumowanie
        logging.info("=" * 40)
        logging.info("RAPORT KOŃCOWY I ANALIZA BŁĘDÓW:")
        logging.info("=" * 40)

        # analiza skutecznosci sklepow
        for shop, stats in shop_stats.items():
            if stats["attempts"] > 0:
                rate = (stats["successes"] / stats["attempts"]) * 100
                
                if rate < 20:
                    logging.error(f"Sklep '{shop}' ma zaledwie {rate:.1f}% skuteczności ({stats['successes']}/{stats['attempts']}).")
                elif rate < 50:
                    logging.warning(f"Sklep '{shop}' ma niską skuteczność ({rate:.1f}%). Znalazł {stats['successes']} z {stats['attempts']} produktów.")
                else:
                    logging.info(f"Sklep '{shop}' - Skuteczność: {rate:.1f}%")

        logging.info("-" * 40)

        # analiza anomalii cenowych
        for prod_id, prod_data in product_prices.items():
            prices_list = [entry["price"] for entry in prod_data["prices"]]
            
            if len(prices_list) >= 3:
                median_price = statistics.median(prices_list)
                
                for entry in prod_data["prices"]:
                    price = entry["price"]
                    shop = entry["shop"]
                    
                    lower_bound = median_price * 0.70
                    upper_bound = median_price * 1.30
                    
                    if price < lower_bound or price > upper_bound:
                        diff = ((price - median_price) / median_price) * 100
                        direction = "wyższa" if diff > 0 else "niższa"
                        logging.warning(
                            f"[ANOMALIA] '{prod_data['name']}' w sklepie '{shop}' kosztuje {price} zł. "
                            f"To o {abs(diff):.1f}% {direction} niż rynkowa mediana ({median_price:.2f} zł)!"
                        )

        logging.info("Zakończono scrapowanie i zamknięto pliki.")


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
