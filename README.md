# CS2 Weapons Data API

This is a simple FastAPI-based API for fetching Counter-Strike 2 (CS2) skin data (including images, rarities, collections, and wears) and fetching live prices from the Steam Community Market.

It utilizes the [CSGO-API by ByMykel](https://github.com/ByMykel/CSGO-API) for skin and image data, and the official Steam Community Market API for pricing.

## Features

- Fast, in-memory caching of over 1000+ CS2 skins and items.
- Search and pagination for skins.
- Real-time Steam Community Market prices (lowest price, median price, volume).

## Setup & Run

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Run the server:**
   ```bash
   uvicorn main:app --reload
   ```

   The server will start at `http://localhost:8000`.

## API Endpoints

### 1. `GET /`
Returns a simple welcome message.

### 2. `GET /skins`
Returns a list of CS2 skins. Supports pagination and searching.

**Query Parameters:**
- `limit` (int, default: 50): Number of items to return (max 1000).
- `offset` (int, default: 0): Offset for pagination.
- `search` (str, optional): A search string to filter skins by name.

**Example:**
```bash
curl "http://localhost:8000/skins?limit=5&search=Asiimov"
```

### 3. `GET /skins/{skin_id}`
Returns details for a specific skin ID (e.g., `skin-e757fd7191f9`).

**Example:**
```bash
curl "http://localhost:8000/skins/skin-e757fd7191f9"
```

### 4. `GET /price`
Fetches the current price and volume for an item directly from the Steam Market.

**Query Parameters:**
- `market_hash_name` (str, required): The exact name of the item on the Steam Market (e.g., `AK-47 | Redline (Field-Tested)`). Be sure to URL-encode the string if you use it in code.

**Example:**
```bash
curl "http://localhost:8000/price?market_hash_name=AK-47%20%7C%20Redline%20%28Field-Tested%29"
```

*Note: The Steam API has strict rate limits. If you request prices too quickly, you may receive a 429 Too Many Requests or 404 response.*

## Swagger Documentation
Interactive API documentation is available at `http://localhost:8000/docs` while the server is running.
