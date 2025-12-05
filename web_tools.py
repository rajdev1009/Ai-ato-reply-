import requests
from bs4 import BeautifulSoup

def scrape_website(url):
    """
    Website ke URL se text nikalta hai.
    """
    try:
        # Browser ban kar request bhejenge taaki block na hon
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code != 200:
            return None

        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Sirf Paragraphs (p tags) nikalo, ads aur menu hata do
        paragraphs = soup.find_all('p')
        text_content = ' '.join([p.get_text() for p in paragraphs])
        
        # Text agar bahut lamba hai to cut kar do (Gemini limit ke liye)
        return text_content[:8000] 
    except Exception as e:
        print(f"Scraping Error: {e}")
        return None
      
