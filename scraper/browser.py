from playwright.async_api import Page
from scraper.tools import generate_quantity_variants


async def fetch_html(page: Page, url: str, shop_config: dict, product: dict) -> str:
    """Wchodzi na podany URL i zwraca wyrenderowany kod HTML strony."""
    try:
        # wczytanie strony
        await page.goto(url, wait_until="networkidle", timeout=15000)

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

                
            if len(quantities) == len(quantities_to_remove): return ""

            for quantity in quantities_to_remove:
                await quantity.evaluate("node => node.remove()")
        
        # zwrócenie html
        html_content = await page.content()
        
                    
        return html_content
        
    except Exception as e:
        print(f"[Error] Błąd podczas ładowania strony {url}: {e}")
        return ""