from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError
from scraper.tools import generate_quantity_variants, fake_hover
import logging
import random

async def fetch_html(page: Page, url: str, shop_name: int, shop_config: dict, product: dict, max_retries: int = 3) -> str:
    """ wchodzi na podany URL, klika odpowiednią pojemność i zwraca wyrenderowany HTML strony """

    for attempt in range(1, max_retries + 1):
        try:
            #wejscie na strone
            await page.goto(url, wait_until="domcontentloaded", timeout=15000)

            selectors = shop_config["selectors"]


            #ustawienie odpowiedniej pojemnosci
            if product["quantity"] != "" and "quantity_button" in selectors:
                quantity_selector = selectors["quantity_button"]
                quantities = await page.locator(quantity_selector).all()
                quantities_to_remove = []
                searched_quantity_values = generate_quantity_variants(product["quantity"])

                for quantity in reversed(quantities):
                    quantity_value = await quantity.inner_text()
                    
                    if any(q.lower() in quantity_value.lower() for q in searched_quantity_values ) and \
						not any(s + q.lower() in quantity_value.lower() for q in searched_quantity_values \
                        for s in ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9', ',', '.']):
                            #klikamy element jeśli pasuje
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
                        
                        await page.wait_for_timeout(1500)

                        
                    else:
						#usuwamy element jesli nie pasuje
                        quantities_to_remove.append(quantity)

                    
                if len(quantities) == len(quantities_to_remove) and len(quantities) != 0: 
                    return ""
                    
                
                if "product_title" in selectors and len(quantities) == 0:
                    this_product_title = await page.locator(selectors["product_title"]).first()
                    if not (any(q.lower() in this_product_title.lower() for q in searched_quantity_values ) and \
						not any(s + q.lower() in this_product_title.lower() for q in searched_quantity_values \
                        for s in ['1', '2', '3', '4', '5', '6', '7', '8', '9', ',', '.'])):
                        
                        return ""
                        
                            

                if "quantity_button" in selectors:
                    await fake_hover(page, selectors["quantity_button"])
                else:
                    await fake_hover(page, selectors["product_price"])
				

                for quantity in quantities_to_remove:
                    await quantity.evaluate("node => node.remove()")
            
            # zwrócenie html
            html_content = await page.content()
            
                        
            return html_content
        
        #łapiemy niewczytanie strony
        except PlaywrightTimeoutError:
            logging.warning(f"[{shop_name}][Timeout] Próba {attempt}/{max_retries} wczytania strony nieudana: {url}")
        except Exception as e:
            logging.warning(f"[{shop_name}][Błąd sieci] Próba {attempt}/{max_retries} nieudana dla {url} | Powód: {e}")

    await asyncio.sleep(random.uniform(2, 3))
    raise PlaywrightTimeoutError("Wyczerpano limit prób połączenia ze sklepem.")
