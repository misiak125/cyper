import re

#przyjmuje string z pojemnosccią i tworzy wszystkie potencjalne sposoby zapisania tej pojemnosci
def generate_quantity_variants(quantity_str: str) -> list[str]:
    """
    Rozbija string ilościowy (np. '500ml', '0,5ha', '100m2') i generuje listę 
    wszystkich dopuszczalnych zapisów w różnych jednostkach i formatach.
    """
    # 1. Zaktualizowany Regex: Pozwala na jednostki typu 'm2' lub 'm^2'
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
                # Ograniczamy do 4 miejsc po przecinku, żeby uniknąć ułamków typu 0.000100000001
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


#formatuje cenę zapisaną w różnych formatach 
def parse_price(price_text: str) -> float | None:
    """
    Inteligentnie parsuje cenę, ignorując jednostki, skróty i kodowanie HTML.
    Obsługuje: "1 599,99", "3,080.00", "918,00&nbsp;zł/szt.", "1.500,00 zł."
    """
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


