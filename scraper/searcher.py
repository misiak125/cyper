import urllib.parse
from urllib.parse import urlparse
from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError
from thefuzz import fuzz
from scraper.tools import generate_quantity_variants, fake_scroll
import logging
import asyncio


async def find_product_url(page: Page, shop_name: int, shop_config: dict, product: dict, max_retries: int = 3) -> str | None:
    """Wchodzi na wyszukiwarkę, filtruje i używa Fuzzy Matchingu do wyboru najlepszego linku."""
    
    product_name = product["name"]
    query_encoded = urllib.parse.quote_plus(product_name)
    search_url = shop_config["search_url_template"].format(query_encoded)
    
        
    selector = shop_config["selectors"]["search_result_link"]
    selectors = shop_config["selectors"]
    
    for attempt in range(1, max_retries + 1):
        try:
            logging.info(f"[{shop_name}][{product_name}]Ładowanie wyszukiwarki (Próba {attempt}/{max_retries}) dla: {product['name']}")
            
            # wejscie na strone wyszukiwania
            await page.goto(search_url, wait_until="domcontentloaded", timeout=15000)
            
            await fake_scroll(page, 1, shop_config["slow"]*2)
            
            #zebranie listy tytułów za pomocą selektora klasy
            try:
                # wyszukujemy kafelki wynikowe
                await page.wait_for_selector(selector, timeout=2500)
                elements = await page.locator(selector).all()
            except PlaywrightTimeoutError:
                logging.info(f"[{shop_name}][{product_name}]  -> Strona wczytana, ale nie znaleziono produktów (Pusta lista).")
                return None 
            
            best_match_url = None
            best_match_title = ""
            best_score = 0
            min_score = 5
            
            possible_quantities = generate_quantity_variants(product["quantity"])
                
            
            for element in elements:


                title = await element.inner_text()
                title_lower = title.lower()

                required_words = product.get("required_words", [])
                exclude_words = product.get("exclude_words", [])
                target_name = product_name
                target_name = target_name + " " + product["quantity"]
                
                #ustawienie wymagania pojemnosci
                if not "quantity_button" in selectors and product["quantity"] != "":
                    if not any(q.lower() in title_lower for q in possible_quantities) or \
                        any(s + q in title_lower for q in possible_quantities \
                        for s in [ '1', '2', '3', '4', '5', '6', '7', '8', '9', ',', '.']):
                        continue;

                    
                #wykluczenie wynikow bez wymaganych slow oraz zawierajacych wykluczone slowa
                if exclude_words and any(bad.lower() in title_lower for bad in exclude_words):
                    continue
                
                if required_words and not all(good.lower() in title_lower for good in required_words):
                    continue
                
                #ocena fuzzy search
                score = fuzz.token_sort_ratio(target_name.lower(), title_lower)
                
                # nadpisanie lidera
                if score > min_score and score > best_score:
                    best_score = score
                    best_match_url = await element.evaluate("node => { const a = node.closest('a'); return a ? a.href : null; }")
                    best_match_title = title.strip()
                    
            # formatowanie url
            if best_match_url:
                logging.info(f"[{shop_name}][{product_name}] Najlepsze dopasowanie: '{best_match_title}' (Zgodność: {best_score}%)")
                
                if not best_match_url.startswith("http"):
                    parsed_uri = urlparse(search_url)
                    domain = f"{parsed_uri.scheme}://{parsed_uri.netloc}"
                    best_match_url = domain + best_match_url if best_match_url.startswith("/") else domain + "/" + best_match_url
                    
                return best_match_url
                
            logging.info(f"[{shop_name}][{product_name}]Żaden wynik nie przeszedł walidacji dla: {product['name']}")
            return None
            
        # złapanie nie wczytania strony 
        except PlaywrightTimeoutError:
            logging.warning(f"[{shop_name}][{product_name}][Timeout] Wyszukiwarka w sklepie długo nie odpowiada (Próba {attempt}/{max_retries}).")
        except Exception as e:
            logging.error(f"[{shop_name}][{product_name}][Błąd] Nieoczekiwany problem przy wyszukiwaniu (Próba {attempt}/{max_retries}): {e}")
            
        # odczekanie i ponowienie proby wczytania
        if attempt < max_retries:
            wait_time = attempt * 2
            logging.info(f"[{shop_name}][{product_name}]Ponawiam połączenie z wyszukiwarką za {wait_time}s...")
            await asyncio.sleep(wait_time)

    logging.error(f"[{shop_name}][{product_name}][KRYTYCZNE] Wyszukiwarka dla zapytania '{product['name']}' jest całkowicie niedostępna po {max_retries} próbach.")
    raise PlaywrightTimeoutError("Wyczerpano limit prób połączenia ze sklepem.")
