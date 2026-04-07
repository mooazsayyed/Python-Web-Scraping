# Submission Notes

This submission includes:

1. `Scraping.py`
2. `React-Web-App`

## What Is Included

### `Scraping.py`

- Scrapes text-only property listings from Property Finder
- Targets the first N results pages
- Saves output to JSON and CSV
- Default assignment run saves files under `outputs/`

Main fields extracted:

- `title`
- `price`
- `location`
- `bedrooms`
- `bathrooms`
- `area`
- `price_per_sqft`
- `property_type`
- `agent`
- `url`
- `raw_text`

### `React-Web-App`

- Page 1: simple form for property details
- Page 2: viewer that shows saved rows in a table
- CSV is stored client-side in browser `localStorage`
- CSV can be downloaded from the UI

## Commands

### Install scraper dependencies

```powershell
pip install -r requirements.txt
playwright install chromium
```

### Run the scraper for the assignment

```powershell
python Scraping.py --pages 2 -f propertyfinder_listings
```

This creates:

- `outputs/propertyfinder_listings.json`
- `outputs/propertyfinder_listings.csv`

### Show scraper help

```powershell
python Scraping.py --help
```

### Run the React app

```powershell
cd React-Web-App
npm install
npm run dev
```

## How To Change Fields

### `Scraping.py`

Update these two places:

1. `extract_card(...)`
2. `save_results(...)`

To add a field:

- add selector logic in function `extract_card(...)`
- add the key to the returned dictionary
- add the field name to the CSV `fieldnames` list

### `React-Web-App`

Update `React-Web-App/src/App.jsx`:

- `emptyForm`
- `headers`
- the matching form input

## Assumptions

- The React task is implemented as client-side CSV storage plus CSV download because there is no backend server in the assignment
- The scraper is the main source for the final Property Finder CSV
- Only text fields are extracted, not images

## Tradeoffs

### Scraper

Pros:

- simple and direct
- deterministic when selectors are stable
- low-cost compared with LLM extraction

Cons:

- selectors may need updates if the site layout changes
- current version extracts from listing cards only, not detail pages

### React app

Pros:

- simple 2-page implementation
- easy to test and modify
- easy to add/remove fields

Cons:

- no backend file write
- CSV lives in browser storage until downloaded

Subject: Submission - Web Scraping and React Task

