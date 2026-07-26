import csv
import json
import os
from typing import List
from .models import PropertyListing
from .utils import logger

def export_csv(listings: List[PropertyListing], path: str) -> None:
    if not listings:
        logger.warning("No listings to export to CSV")
        return
        
    try:
        dirpath = os.path.dirname(path)
        if dirpath:
            os.makedirs(dirpath, exist_ok=True)
        headers = list(listings[0].model_dump().keys())
        
        with open(path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            for listing in listings:
                writer.writerow(listing.model_dump())
        logger.info(f"Successfully exported {len(listings)} listings to {path}")
    except Exception as e:
        logger.error(f"Failed to export CSV to {path}: {e}")

def export_json(listings: List[PropertyListing], path: str) -> None:
    if not listings:
        logger.warning("No listings to export to JSON")
        return
        
    try:
        dirpath = os.path.dirname(path)
        if dirpath:
            os.makedirs(dirpath, exist_ok=True)
        data = [listing.model_dump() for listing in listings]
        
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        logger.info(f"Successfully exported {len(listings)} listings to {path}")
    except Exception as e:
        logger.error(f"Failed to export JSON to {path}: {e}")

def export_all(listings: List[PropertyListing], output_dir: str) -> None:
    os.makedirs(output_dir, exist_ok=True)
    export_csv(listings, os.path.join(output_dir, "listings.csv"))
    export_json(listings, os.path.join(output_dir, "listings.json"))
