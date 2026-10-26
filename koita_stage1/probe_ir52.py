from urllib.request import Request, urlopen
from urllib.error import HTTPError
from ir52_article import fetch_article

if __name__ == '__main__':
    url = 'https://www.mk.co.kr/news/it/12166326'
    try:
        with urlopen(Request(url, headers={'User-Agent': 'Mozilla/5.0'}), timeout=25) as response:
            print('Direct HTTP:', response.status)
    except HTTPError as error:
        print('Direct HTTP:', error.code)
    article = fetch_article(url)
    print('Extracted:', article.title, article.publication_date, len(article.parts))
