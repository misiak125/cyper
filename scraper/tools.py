import re
import asyncio
import random
from playwright.async_api import Page


def generate_quantity_variants(quantity_str: str) -> list[str]:
    ''' przyjmuje string z wartoscia jedonstka i tworzy wszystkie potencjalne sposoby zapisania tej pojemnosci '''

    match = re.match(r'^\s*([\d.,\s]+?)\s*([a-zA-Z]+(?:\^?2)?)\s*$', quantity_str.lower())
    
    if not match:
        return [quantity_str]
        
    num_str, unit = match.groups()
    num_str = num_str.strip()
    
    
    clean = re.sub(r'[^\d.,]', '', num_str)
    last_dot = clean.rfind('.')
    last_comma = clean.rfind(',')
    
    try:
        if last_dot == -1 and last_comma == -1:
            val = float(clean)
        elif last_dot > last_comma:
            val = float(clean.replace(',', ''))
        else:
            val = float(clean.replace('.', '').replace(',', '.'))
    except ValueError:
        return [quantity_str]
        
    categories = {
        'volume': {'ml': 1, 'l': 1000},
        'mass': {'g': 1, 'kg': 1000, 'dag': 10, 'mg': 0.001},
        'area': {'m2': 1, 'm^2': 1, 'a': 100, 'ha': 10000} 
    }
    
    target_category = None
    for cat, units in categories.items():
        if unit in units:
            target_category = cat
            break
            
    variants = set() 
    
    if target_category:
        base_value = val * categories[target_category][unit]
        
        for target_unit, multiplier in categories[target_category].items():
            new_val = base_value / multiplier
            
            if new_val.is_integer():
                formatted_val = str(int(new_val))
            else:
                formatted_val = f"{new_val:.4f}".rstrip('0').rstrip('.')
                
            val_dot = formatted_val
            val_comma = formatted_val.replace('.', ',')
            
            variants.add(f"{val_dot}{target_unit}")
            variants.add(f"{val_dot} {target_unit}")
            variants.add(f"{val_comma}{target_unit}")
            variants.add(f"{val_comma} {target_unit}")
            
            if target_unit == 'l':
                variants.add(f"{val_dot}L")
                variants.add(f"{val_dot} L")
                variants.add(f"{val_comma}L")
                variants.add(f"{val_comma} L")
    else:
        formatted_val = str(int(val)) if val.is_integer() else str(val)
        val_dot = formatted_val
        val_comma = formatted_val.replace('.', ',')
        
        variants.add(f"{val_dot}{unit}")
        variants.add(f"{val_dot} {unit}")
        variants.add(f"{val_comma}{unit}")
        variants.add(f"{val_comma} {unit}")

    return sorted(list(variants))



def parse_price(price_text: str) -> float | None:
    """ ormatuje string ceny zapisany w różnych formach """

    if not price_text:
        return None
        
    
    clean = re.sub(r'[^\d.,]', '', price_text)
    
    clean = clean.rstrip('.,')
    
    if not clean:
        return None
        
    last_dot = clean.rfind('.')
    last_comma = clean.rfind(',')
    
    if last_dot == -1 and last_comma == -1:
        try:
            return float(clean)
        except ValueError:
            return None
            
    if last_dot > last_comma:
        clean = clean.replace(',', '')
    else:
        clean = clean.replace('.', '').replace(',', '.')
        
    try:
        return float(clean)
    except ValueError:
        return None



async def fake_scroll(page: Page, max_scrolls: int = 10, delay_between: float = 0.5):
    """wykonuje falszywy scroll na stronie Page"""
    for _ in range(max_scrolls):
        #scroll distance
        scroll_distance = random.randint(100, 400)
        scroll_distance2 = random.randint(100, 800)
        
        await asyncio.sleep(delay_between + random.uniform(0.2, 1.2))
        
        await page.evaluate(f"window.scrollBy(0, {scroll_distance2})")
        
        
        
        await asyncio.sleep(delay_between + random.uniform(0.1, 0.7))
        # losuje kierunek
        if random.random() > 0.1:
            await page.evaluate(f"window.scrollBy(0, {scroll_distance})")
        else:
            await page.evaluate(f"window.scrollBy(0, -{scroll_distance})")
        
        # falszywe czekanie
        await asyncio.sleep(delay_between + random.uniform(0.2, 1.1))
        
        
async def fake_hover(page: Page, selector: str = None, duration: float = None):
    """ najezdza myszka na stronie Page na element selector lub na losowe miejsce"""

    if selector:
        # znajdz selektor
        element = await page.query_selector(selector)
        
        await asyncio.sleep(duration or random.uniform(0.2, 0.5))
        if element:
            box = await element.bounding_box()
            if box:
                # najedz na losowe miejsce 
                x = box['x'] + random.uniform(10, box['width'] - 10)
                y = box['y'] + random.uniform(10, box['height'] - 10)
                await page.mouse.move(x, y)
                
                # pozostan
                hover_time = duration or random.uniform(0.5, 2.5)
                await asyncio.sleep(hover_time)
                return True
    else:
        # najedz na losowe miejsce
        viewport = await page.evaluate("({width: window.innerWidth, height: window.innerHeight})")
        x = random.randint(50, viewport['width'] - 50)
        y = random.randint(50, viewport['height'] - 50)
        await page.mouse.move(x, y)
        return True
    return False
