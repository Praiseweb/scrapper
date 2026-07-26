import pytest

class DataCleaner:
    @staticmethod
    def clean_price(price_str: str) -> int:
        if not price_str:
            return 0
        cleaned = price_str.lower().replace('$', '').replace(',', '').strip()
        if 'k' in cleaned:
            return int(float(cleaned.replace('k', '')) * 1000)
        try:
            return int(float(cleaned))
        except ValueError:
            return 0

    @staticmethod
    def clean_address(address: str) -> str:
        return address.strip().title() if address else ""

    @staticmethod
    def extract_housing_info(info_str: str) -> dict:
        result = {"bedrooms": None, "sqft": None}
        if not info_str:
            return result
            
        parts = [p.strip() for p in info_str.lower().split('-')]
        for part in parts:
            if 'br' in part:
                try:
                    result['bedrooms'] = int(part.replace('br', '').strip())
                except ValueError:
                    pass
            elif 'ft2' in part or 'ft²' in part or 'sqft' in part:
                try:
                    result['sqft'] = int(part.replace('ft2', '').replace('ft²', '').replace('sqft', '').strip())
                except ValueError:
                    pass
        return result

def test_clean_price():
    cleaner = DataCleaner()
    assert cleaner.clean_price("$150,000") == 150000
    assert cleaner.clean_price("150000") == 150000
    assert cleaner.clean_price("$150K") == 150000
    assert cleaner.clean_price(" $1,234.56 ") == 1234
    assert cleaner.clean_price("Contact for price") == 0

def test_clean_address():
    cleaner = DataCleaner()
    assert cleaner.clean_address(" 123 MAIN ST ") == "123 Main St"
    assert cleaner.clean_address("apt 4b, new york, ny") == "Apt 4B, New York, Ny"
    assert cleaner.clean_address("") == ""

def test_extract_housing_info():
    cleaner = DataCleaner()
    info1 = cleaner.extract_housing_info("3br - 1500ft²")
    assert info1["bedrooms"] == 3
    assert info1["sqft"] == 1500

    info2 = cleaner.extract_housing_info("2br")
    assert info2["bedrooms"] == 2
    assert info2["sqft"] is None

    info3 = cleaner.extract_housing_info("1000sqft")
    assert info3["bedrooms"] is None
    assert info3["sqft"] == 1000

def test_duplicate_detection():
    seen_ids = set()
    def is_duplicate(item_id):
        if item_id in seen_ids:
            return True
        seen_ids.add(item_id)
        return False
        
    assert is_duplicate("id_123") is False
    assert is_duplicate("id_456") is False
    assert is_duplicate("id_123") is True

def test_validation():
    def is_valid_property(price, sqft):
        return 100 <= price <= 100_000_000 and (sqft is None or 50 <= sqft <= 50_000)
        
    assert is_valid_property(150000, 1500) is True
    assert is_valid_property(10, 1500) is False
    assert is_valid_property(150000, 10) is False
