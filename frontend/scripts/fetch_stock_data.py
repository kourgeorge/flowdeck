#!/usr/bin/env python3
"""
Script to download NASDAQ/NYSE ticker lists and convert to JSON
"""
import urllib.request
import csv
import json
import os

def download_and_convert():
    nasdaq_url = "https://ftp.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt"
    other_url = "https://ftp.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt"
    
    stocks = []
    
    # Download NASDAQ listed
    try:
        print("Downloading NASDAQ listed stocks...")
        with urllib.request.urlopen(nasdaq_url, timeout=30) as response:
            content = response.read().decode('utf-8')
            reader = csv.DictReader(content.splitlines(), delimiter='|')
            for row in reader:
                if row.get('Symbol') and row.get('Security Name'):
                    stocks.append({
                        'ticker': row['Symbol'].strip(),
                        'name': row['Security Name'].strip()
                    })
        print(f"Downloaded {len(stocks)} NASDAQ stocks")
    except Exception as e:
        print(f"Error downloading NASDAQ: {e}")
    
    # Download other listed (NYSE, AMEX, etc.)
    try:
        print("Downloading other listed stocks...")
        with urllib.request.urlopen(other_url, timeout=30) as response:
            content = response.read().decode('utf-8')
            reader = csv.DictReader(content.splitlines(), delimiter='|')
            for row in reader:
                if row.get('NASDAQ Symbol') and row.get('Security Name'):
                    ticker = row['NASDAQ Symbol'].strip()
                    name = row['Security Name'].strip()
                    # Avoid duplicates
                    if not any(s['ticker'] == ticker for s in stocks):
                        stocks.append({
                            'ticker': ticker,
                            'name': name
                        })
        print(f"Total stocks: {len(stocks)}")
    except Exception as e:
        print(f"Error downloading other listed: {e}")
    
    # Sort by ticker
    stocks.sort(key=lambda x: x['ticker'])
    
    # Save to JSON
    output_path = os.path.join(os.path.dirname(__file__), '..', 'public', 'stocks.json')
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    with open(output_path, 'w') as f:
        json.dump(stocks, f, indent=2)
    
    print(f"Saved {len(stocks)} stocks to {output_path}")
    return stocks

if __name__ == '__main__':
    download_and_convert()

