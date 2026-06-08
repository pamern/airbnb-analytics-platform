# -*- coding: utf-8 -*-
"""Download du lieu Airbnb Bangkok tu Inside Airbnb va giai nen (ASCII logs for Windows compatibility)."""

import gzip
import shutil
import urllib.request
from pathlib import Path

# Cau hinh duong dan va ngay cao du lieu
DATE = "2025-09-26"
BASE_URL = f"http://data.insideairbnb.com/thailand/central-thailand/bangkok/{DATE}"

# File dich
DEST_DIR = Path(__file__).resolve().parents[1] / "data" / "raw" / "bangkok"
DEST_DIR.mkdir(parents=True, exist_ok=True)

# Danh sach files can tai
FILES_TO_DOWNLOAD = {
    "listings.csv.gz": f"{BASE_URL}/data/listings.csv.gz",
    "calendar.csv.gz": f"{BASE_URL}/data/calendar.csv.gz",
    "reviews.csv.gz": f"{BASE_URL}/data/reviews.csv.gz",
    "neighbourhoods.csv": f"{BASE_URL}/visualisations/neighbourhoods.csv",
    "neighbourhoods.geojson": f"{BASE_URL}/visualisations/neighbourhoods.geojson"
}

def download_file(url: str, dest_path: Path):
    print(f"Downloading: {url} -> {dest_path.name}")
    req = urllib.request.Request(
        url, 
        headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    )
    with urllib.request.urlopen(req) as response, open(dest_path, 'wb') as out_file:
        shutil.copyfileobj(response, out_file)

def extract_gzip(gz_path: Path, csv_path: Path):
    print(f"Extracting: {gz_path.name} -> {csv_path.name}")
    with gzip.open(gz_path, 'rb') as f_in, open(csv_path, 'wb') as f_out:
        shutil.copyfileobj(f_in, f_out)

def main():
    print(f"Target Directory: {DEST_DIR}")
    for filename, url in FILES_TO_DOWNLOAD.items():
        dest_path = DEST_DIR / filename
        try:
            download_file(url, dest_path)
            
            # Neu la file .gz, tien hanh giai nen ra file .csv
            if filename.endswith(".gz"):
                csv_filename = filename[:-3] # Bo duoi .gz
                csv_path = DEST_DIR / csv_filename
                extract_gzip(dest_path, csv_path)
                
                # Xoa file .gz sau khi giai nen thanh cong de tiet kiem dung luong
                dest_path.unlink()
                print(f"Removed temporary archive: {filename}")
                
        except Exception as e:
            print(f"Error processing {filename}: {e}")
    print("Download and extraction process finished.")

if __name__ == "__main__":
    main()
