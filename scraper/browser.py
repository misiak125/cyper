from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError
from scraper.tools import generate_quantity_variants
import logging


async def fetch_html(page: Page, url: str, shop_config: dict, product: dict, max_retries: int = 3) -> str:
    """Wchodzi na podany URL i zwraca wyrenderowany kod HTML strony."""
    for attempt in range(1, max_retries + 1):
        try:
            
            await page.goto(url, wait_until="domcontentloaded", timeout=15000)

            selectors = shop_config["selectors"]


            #ustawienie odpowiedniej pojemnosci
            if product["quantity"] != "" and "quantity_button" in selectors:
                quantity_selector = selectors["quantity_button"]
                quantities = await page.locator(quantity_selector).all()
                quantities_to_remove = []

                for quantity in reversed(quantities):
                    quantity_value = await quantity.inner_text()
                    
                    if any(q in quantity_value for q in generate_quantity_variants(product["quantity"]) ) and \
                    not any(s + q in quantity_value for q in generate_quantity_variants(product["quantity"]) \
                        for s in ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9', ',', '.']):
                        try: 
                            await quantity.evaluate("node => node.click()")
                        except: 
                            pass

                        try: 
                            await quantity.evaluate("""option_node => {
                            
                                const select_node = option_node.closest('select');
                                
                                select_node.value = option_node.value;
                                
                                select_node.dispatchEvent(new Event('change', { bubbles: true }));
                            }""")
                        except: 
                            pass
                        
                        await page.wait_for_timeout(1000)

                        
                    else:
                        quantities_to_remove.append(quantity)

                    
                if len(quantities) == len(quantities_to_remove) and len(quantities) != 0: 
                    return ""
                    

                for quantity in quantities_to_remove:
                    await quantity.evaluate("node => node.remove()")
            
            # zwrócenie html
            html_content = await page.content()
            
                        
            return html_content
        
    
        except PlaywrightTimeoutError:
            logging.warning(f"[Timeout] Próba {attempt}/{max_retries} wczytania strony nieudana: {url}")
        except Exception as e:
            logging.warning(f"[Błąd sieci] Próba {attempt}/{max_retries} nieudana dla {url} | Powód: {e}")