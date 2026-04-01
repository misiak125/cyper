from bs4 import BeautifulSoup
import re
from scraper.tools import parse_price

#wyciąga informacje z pliku html
def extract_product_data(html: str, shop_config: dict) -> dict:


    result = {"price": None, "tax_info": None, "is_available": False}
    
    if not html:
        return result
        
    soup = BeautifulSoup(html, "html.parser")
    selectors = shop_config["selectors"]
        

    # zebranie ceny
    price_selectors = selectors.get("product_price", "")
    
    price_element = soup.select_one(price_selectors[0])
    for price_selector in price_selectors:
        price_element = soup.select_one(price_selector)
        
        if price_element: 
            break
    if price_element:
        price_text = price_element.get_text(strip=True)
        clean_price = parse_price(price_text)
        try:
            result["price"] = float(clean_price)
        except ValueError:
            pass

    #  sprawszenie czy cena jest netto/brutto 
    if "product_tax" in selectors:
        tax_element = soup.select_one(selectors["product_tax"])
        if tax_element:
            result["tax_info"] = tax_element.get_text(strip=True)

        if result["tax_info"] and "brutto" in result["tax_info"].lower():
            result["tax_info"] = "brutto"
        else:
            result["tax_info"] = "netto"

    else: 
        result["tax_info"] = "brutto"

    # sprawdzenie dostepnosci
    if "product_availability" in selectors and "available_string" in selectors:
        availability_element = soup.select_one(selectors["product_availability"])
        if availability_element:
            availability_text = availability_element.get_text(strip=True)

            if selectors["available_string"].lower() in availability_text.lower():
                result["is_available"] = True
    elif "product_availability" in selectors and "unavailable_string" in selectors:
        availability_element = soup.select_one(selectors["product_availability"])
        if availability_element:
            availability_text = availability_element.get_text(strip=True)

            if selectors["unavailable_string"].lower() in availability_text.lower():
                result["is_available"] = False

    else:
        result["is_available"] = True

    return result 