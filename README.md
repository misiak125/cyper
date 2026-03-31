A web scraper collecting information about prices and availability of selected products in different online stores.

Run:
1. fill data/products_to_search.json with info about desired products
2. fill config.py with your USER_AGENT and a name, URL and CSS selectors to stores
3. python main.py


 available flags:
 
 -l                         append result to a master file
 
 -s [list of stores]        search only selected stores
