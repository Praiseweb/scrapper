import re
from typing import Optional, List, Dict
from .models import PropertyListing
from .utils import logger
try:
    from rapidfuzz import fuzz
except ImportError:
    # Basic fallback if rapidfuzz is not installed
    class FuzzFallback:
        @staticmethod
        def ratio(s1, s2):
            return 100.0 if s1 == s2 else 0.0
    fuzz = FuzzFallback()

def clean_price(raw: Optional[str]) -> Optional[float]:
    if not raw:
        return None
    cleaned = re.sub(r'[^\d.]', '', raw)
    try:
        return float(cleaned) if cleaned else None
    except ValueError:
        return None

def clean_address(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    return ' '.join(raw.split())

def extract_housing_info(text: Optional[str]) -> dict:
    info = {"bedrooms": None, "bathrooms": None, "sqft": None, "property_type": None}
    if not text:
        return info
    
    bed_match = re.search(r'(\d+)\s*[bB][rR]', text)
    if bed_match:
        info["bedrooms"] = int(bed_match.group(1))
        
    bath_match = re.search(r'(\d+(?:\.\d+)?)\s*[bB][aA]', text)
    if bath_match:
        info["bathrooms"] = float(bath_match.group(1))
        
    sqft_match = re.search(r'(\d+)\s*(?:ft|ft2|sqft)', text, re.IGNORECASE)
    if sqft_match:
        info["sqft"] = int(sqft_match.group(1))
        
    types = ['house', 'apartment', 'condo', 'duplex', 'townhouse', 'loft', 'land']
    text_lower = text.lower()
    for t in types:
        if t in text_lower:
            info["property_type"] = t
            break
            
    return info

def detect_duplicates(listings: List[Dict]) -> List[Dict]:
    seen_urls = set()
    unique = []
    for l in listings:
        url = l.get("url")
        if url in seen_urls:
            continue
        seen_urls.add(url)
        unique.append(l)
        
    # Optional fuzzy deduplication based on title+price
    final_unique = []
    for l in unique:
        is_dup = False
        for f in final_unique:
            title_score = fuzz.ratio(l.get("title", ""), f.get("title", ""))
            if title_score > 90 and l.get("raw_price") == f.get("raw_price"):
                is_dup = True
                break
        if not is_dup:
            final_unique.append(l)
            
    return final_unique

def validate_listing(listing: Dict) -> bool:
    price = listing.get("price")
    if price is not None and (price <= 0 or price > 100000000):
        return False
    beds = listing.get("bedrooms")
    if beds is not None and beds > 30:
        return False
    return True

def clean_all(raw_listings: List[Dict]) -> List[PropertyListing]:
    cleaned = []
    unique_raw = detect_duplicates(raw_listings)
    
    for raw in unique_raw:
        try:
            price = clean_price(raw.get("raw_price"))
            address = clean_address(raw.get("raw_address"))
            housing = extract_housing_info(raw.get("raw_housing_info", ""))
            
            listing = {
                "title": raw.get("title", "No Title"),
                "price": price,
                "address": address,
                "bedrooms": housing["bedrooms"],
                "bathrooms": housing["bathrooms"],
                "sqft": housing["sqft"],
                "property_type": housing["property_type"],
                "url": raw.get("url", ""),
                "description": raw.get("description"),
                "posted_date": raw.get("posted_date"),
                "location": raw.get("location", "unknown")
            }
            
            if validate_listing(listing):
                cleaned.append(PropertyListing(**listing))
        except Exception as e:
            logger.warning(f"Error cleaning listing {raw.get('url')}: {e}")
            
    return cleaned
