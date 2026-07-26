from typing import Optional
from pydantic import BaseModel

class PropertyListing(BaseModel):
    title: str
    price: Optional[float] = None
    address: Optional[str] = None
    bedrooms: Optional[int] = None
    bathrooms: Optional[float] = None
    sqft: Optional[int] = None
    url: str
    description: Optional[str] = None
    posted_date: Optional[str] = None
    source: str = "craigslist"
    location: str
    property_type: Optional[str] = None
