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

### 5. `GET /inventory/{steam_id}`
Fetches a specific player's public CS2 inventory and optionally fetches prices for all items to calculate total inventory value. Returns items sorted from highest to lowest price.

**Path Parameters:**
- `steam_id` (str, required): The user's Steam ID64.

**Query Parameters:**
- `fetch_prices` (bool, optional, default: True): Attempt to query Steam for prices. Setting this to false will return the inventory much faster by skipping Steam pricing rate limits.

**Example:**
```bash
curl "http://localhost:8000/inventory/76561198084749846"
```

*Note: Steam's Inventory and Price APIs rate limit very aggressively. Fetching prices for large inventories may fail partially or completely with 429 Too Many Requests.*

## Swagger Documentation
Interactive API documentation is available at `http://localhost:8000/docs` while the server is running.

## Fixing `429: Steam API rate limit exceeded` on Free Hosts (Render, Fly.io)

Steam aggressively bans or rate-limits requests originating from datacenter IPs used by cloud providers like **Render**, **AWS**, **DigitalOcean**, etc.

If you are hosting this API on Render and getting a `429 Steam API rate limit exceeded` error, it is **not** because you are missing an API key (the Steam Community endpoints do not use them). It is because Steam blocked Render's IP address.

**How to fix this:**

1. **Run Locally:** Run the server on your personal computer (`uvicorn main:app`). Your home network IP is highly trusted by Steam.
2. **Use an HTTP Proxy:** The API supports HTTP proxies. Add an environment variable named `HTTP_PROXY` in your Render dashboard pointing to a residential proxy or an unblocked server. Example:
   ```bash
   HTTP_PROXY="http://username:password@proxy-server:port"
   ```
3. **Use a paid CS2 API:** For enterprise production, you will need to swap out the `steamcommunity.com` endpoints in `main.py` with paid community proxies like Steamanalyst, Skinport API, or SteamWebAPI.com.

## Hosting on GitHub

Because this is a **Python backend API** (FastAPI), it cannot be hosted directly on **GitHub Pages**, which only supports static frontend files (HTML/CSS/JS).

To host this API for free and connect it to a GitHub repository, you can use **Render**:

1. Push this repository to GitHub.
2. Go to [Render.com](https://render.com/) and create a free account.
3. Click "New" -> "Web Service".
4. Connect your GitHub account and select your repository.
5. Use the following settings:
   - **Environment:** `Python`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn main:app --host 0.0.0.0 --port 10000`
6. Click "Create Web Service". Render will build and deploy your API automatically whenever you push to GitHub!
