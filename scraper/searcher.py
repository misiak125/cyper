import urllib.parse
from urllib.parse import urlparse
from playwright.async_api import Page
from thefuzz import fuzz
from scraper.tools import generate_quantity_variants
async def find_product_url(page: Page, shop_config: dict, product: dict) -> str | None:
    """Wchodzi na wyszukiwarkę, filtruje i używa Fuzzy Matchingu do wyboru najlepszego linku."""
    
    query_encoded = urllib.parse.quote_plus(product["name"])
    search_url = shop_config["search_url_template"].format(query_encoded)
    
    try:
        await page.goto(search_url, wait_until="domcontentloaded", timeout=15000)
    except Exception as e:
        print(f"[Error] Błąd ładowania wyszukiwarki: {e}")
        return None
        
    selector = shop_config["selectors"]["search_result_link"]
    selectors = shop_config["selectors"]
    
    try:
        #zebranie listy tytułów za pomocą selektora klasy
        await page.wait_for_selector(selector, timeout=1500)
        elements = await page.locator(selector).all()
        
        best_match_url = None
        best_match_title = ""
        best_score = 0
        min_score = 5
        
        
        for element in elements:


            title = await element.inner_text()
            title_lower = title.lower()

            
            required_words = product.get("required_words", [])
            exclude_words = product.get("exclude_words", [])
            target_name = product["name"]

            #ustawienie wymagania pojemnosci
            if not "quantity_button" in selectors:
                if not any(q.lower() in title_lower for q in generate_quantity_variants(product["quantity"])) or \
                    any(s + q in title_lower for q in generate_quantity_variants(product["quantity"]) \
                     for s in ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9', ',', '.']):
                    continue;

                target_name = target_name + product["quantity"]
                
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
            print(f"  [Success] Najlepsze dopasowanie: '{best_match_title}' (Zgodność: {best_score}%)")
            
            if not best_match_url.startswith("http"):
                parsed_uri = urlparse(search_url)
                domain = f"{parsed_uri.scheme}://{parsed_uri.netloc}"
                best_match_url = domain + best_match_url if best_match_url.startswith("/") else domain + "/" + best_match_url
                
            return best_match_url
            
        print(f"  [Error] Żaden wynik nie przeszedł walidacji dla: {product['name']}")
        return None
        
    except Exception as e:
        print(f"[Error] Nie znaleziono wyników dla {product['name']}. Błąd: {e}")
        return None