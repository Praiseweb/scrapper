from bs4 import BeautifulSoup
from typing import List, Dict
import re
from .utils import logger

def parse_search_results(html: str) -> List[Dict]:
    soup = BeautifulSoup(html, 'lxml')
    listings = []
    
    # Modern Craigslist uses ol.cl-search-results and li.cl-search-result
    results = soup.find_all('li', class_='cl-search-result')
    if not results:
        # Fallback to old structure if needed
        results = soup.find_all('li', class_='result-row')
        
    for result in results:
        try:
            link = result.find('a', class_='cl-app-anchor') or result.find('a', class_='result-title')
            if not link:
                continue
            url = link.get('href')
            title = link.text.strip()
            
            price_el = result.find('span', class_='priceinfo') or result.find('span', class_='result-price')
            price = price_el.text.strip() if price_el else None
            
            listings.append({
                "url": url,
                "title": title,
                "raw_price": price
            })
        except Exception as e:
            logger.debug(f"Error parsing a search result row: {e}")
            
    return listings

def parse_listing_detail(html: str) -> Dict:
    soup = BeautifulSoup(html, 'lxml')
    details = {}
    
    try:
        title_el = soup.find('span', id='titletextonly')
        if title_el:
            details["title"] = title_el.text.strip()
            
        price_el = soup.find('span', class_='price')
        if price_el:
            details["raw_price"] = price_el.text.strip()
            
        mapaddress = soup.find('div', class_='mapaddress')
        if mapaddress:
            details["raw_address"] = mapaddress.text.strip()
            
        attr_groups = soup.find_all('p', class_='attrgroup')
        housing_info = ""
        for group in attr_groups:
            housing_info += " " + group.text.strip()
            
        details["raw_housing_info"] = housing_info
        
        body = soup.find('section', id='postingbody')
        if body:
            # Remove the "QR Code Link to This Post" text
            qr_text = body.find('div', class_='print-information')
            if qr_text:
                qr_text.decompose()
            details["description"] = body.text.strip().replace('\n', ' ')
            
        date_el = soup.find('time', class_='date timeago')
        if date_el and date_el.has_attr('datetime'):
            details["posted_date"] = date_el['datetime']
            
    except Exception as e:
        logger.debug(f"Error parsing detail page: {e}")
        
    return details
