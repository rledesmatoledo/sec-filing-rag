
import requests

class CIKLookup:
    def __init__(self):
        self.by_name = {}
        self.by_ticker = {}
        
        self.headers = {
            'User-Agent': "Roberto Ledesma robertoledesma015@gmail.com",
            'Accept-Encoding': "gzip, deflate",
            'Host': "www.sec.gov"
        }
        self._load_data()


    def _load_data(self):
        headers = self.headers
        url = "https://www.sec.gov/files/company_tickers_exchange.json"
        response = requests.get(url, headers=headers)

        data = response.json()

        for entry in data["data"]:
           cik = entry[0]
           name = entry[1].lower()
           ticker = entry[2].upper()
           
           self.by_name[name] = (cik, name, ticker)
           self.by_ticker[ticker] = (cik, name, ticker)
    
    def name_to_cik(self, name):
        return self.by_name.get(name.lower())
    
    def ticker_to_cik(self, ticker):
        return self.by_ticker.get(ticker.upper())
    
    def _get_submissions(self, cik):
        padded_cik = str(cik).zfill(10)
        url = f"https://data.sec.gov/submissions/CIK{padded_cik}.json"
        headers = {
            'User-Agent': self.headers['User-Agent'],
            'Accept-Encoding': "gzip, deflate",
            'Host': "data.sec.gov"
        }
        response = requests.get(url, headers=headers)
        return response.json()
    
    def _find_filing(self, submissions, form_type, year):
        filings = submissions["filings"]["recent"]
        forms = filings["form"]
        dates = filings["filingDate"]
        accessions = filings["accessionNumber"]
        documents = filings["primaryDocument"]

        for i,form in enumerate(forms):
            if form == form_type and str(year) in dates[i]:
                clean_accession = accessions[i].replace("-", "")
                return (accessions[i], clean_accession, documents[i], dates[i])
            
        return None
    
    def annual_filing(self, cik, year):
        submissions = self._get_submissions(cik)
        filing = self._find_filing(submissions, "10-K", year)
    
        if filing is None:
            return None
        
        accession, clean_accession, document, date = filing
        url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{clean_accession}/{document}"
        return (cik, accession, document, date, url)
    
    def quarterly_filing(self, cik, year, quarter):
        submissions = self._get_submissions(cik)
        filing = self._find_filing(submissions, "10-Q", year)
    
        if filing is None:
            return None
        
        accession, clean_accession, document, date = filing
        url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{clean_accession}/{document}"
        return (cik, accession, document, date, url)
        

      