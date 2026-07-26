import pytest
from bs4 import BeautifulSoup

# Mock parser
class HTMLParser:
    @staticmethod
    def parse_search_results(html: str) -> list:
        soup = BeautifulSoup(html, 'html.parser')
        results = []
        for li in soup.select("li.result-row"):
            title_elem = li.select_one(".result-title")
            price_elem = li.select_one(".result-price")
            
            if title_elem:
                results.append({
                    "title": title_elem.text.strip(),
                    "price": price_elem.text.strip() if price_elem else None,
                    "url": title_elem.get("href")
                })
        return results

    @staticmethod
    def parse_detail_page(html: str) -> dict:
        soup = BeautifulSoup(html, 'html.parser')
        desc_elem = soup.select_one("#postingbody")
        attrs = {}
        for attr in soup.select(".attrgroup span"):
            text = attr.text.strip()
            if ":" in text:
                k, v = text.split(":", 1)
                attrs[k.strip()] = v.strip()
                
        return {
            "description": desc_elem.text.replace("QR Code Link to This Post", "").strip() if desc_elem else None,
            "attributes": attrs
        }


@pytest.fixture
def sample_search_html():
    return """
    <html>
        <body>
            <ul class="rows">
                <li class="result-row">
                    <a href="https://example.com/1" class="result-title">Beautiful 2BR Apartment</a>
                    <span class="result-meta">
                        <span class="result-price">$2,500</span>
                    </span>
                </li>
                <li class="result-row">
                    <a href="https://example.com/2" class="result-title">Studio in Downtown</a>
                    <!-- Missing price -->
                </li>
            </ul>
        </body>
    </html>
    """


@pytest.fixture
def sample_detail_html():
    return """
    <html>
        <body>
            <div class="mapAndAttrs">
                <p class="attrgroup">
                    <span>cats are OK - purrr</span>
                    <span>dogs are OK - wooof</span>
                    <span>application fee details: $50</span>
                    <span>broker fee details: None</span>
                </p>
            </div>
            <section id="postingbody">
                QR Code Link to This Post
                This is a wonderful apartment in a great location.
                Available immediately.
            </section>
        </body>
    </html>
    """


def test_parse_search_results(sample_search_html):
    parser = HTMLParser()
    results = parser.parse_search_results(sample_search_html)
    
    assert len(results) == 2
    assert results[0]["title"] == "Beautiful 2BR Apartment"
    assert results[0]["price"] == "$2,500"
    assert results[0]["url"] == "https://example.com/1"
    
    assert results[1]["title"] == "Studio in Downtown"
    assert results[1]["price"] is None


def test_parse_detail_page(sample_detail_html):
    parser = HTMLParser()
    result = parser.parse_detail_page(sample_detail_html)
    
    assert "This is a wonderful apartment" in result["description"]
    assert "QR Code Link" not in result["description"]
    assert result["attributes"].get("application fee details") == "$50"


def test_parse_missing_fields():
    parser = HTMLParser()
    empty_html = "<html><body><div>Nothing here</div></body></html>"
    
    results = parser.parse_search_results(empty_html)
    assert len(results) == 0
    
    detail = parser.parse_detail_page(empty_html)
    assert detail["description"] is None
    assert detail["attributes"] == {}
