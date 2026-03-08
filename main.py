import httpx
import asyncio
import time
from fastapi import FastAPI, HTTPException, Query, Path
from typing import List, Optional, Dict, Any
from contextlib import asynccontextmanager

# In-memory cache for skins data
skins_data = []
skins_index = {} # Map skin id to skin data

# Simple in-memory cache for prices to avoid rate limiting
price_cache = {} # Map market_hash_name to {"price": float, "timestamp": float}

async def load_skins_data(retries: int = 3, delay: float = 2.0):
    global skins_data, skins_index
    url = "https://raw.githubusercontent.com/ByMykel/CSGO-API/main/public/api/en/skins.json"

    # Use httpx to fetch the data asynchronously
    async with httpx.AsyncClient() as client:
        for attempt in range(retries):
            try:
                response = await client.get(url, timeout=30.0)
                response.raise_for_status()
                data = response.json()

                # Store in global variables
                skins_data = data
                skins_index = {skin['id']: skin for skin in data if 'id' in skin}
                print(f"Loaded {len(skins_data)} skins from {url}")
                return # Success
            except Exception as e:
                print(f"Attempt {attempt + 1} failed to load skins data: {e}")
                if attempt < retries - 1:
                    await asyncio.sleep(delay)
                else:
                    print("All attempts to load skins data failed. The /skins endpoints will be unavailable.")

# Keep a strong reference to background tasks
background_tasks = set()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load data on startup
    print("Starting up and loading CS2 skins data...")
    # Run the background task without blocking startup
    task = asyncio.create_task(load_skins_data())
    background_tasks.add(task)
    task.add_done_callback(background_tasks.discard)
    yield
    # Clean up on shutdown
    print("Shutting down...")

app = FastAPI(
    title="CS2 Weapons Data API",
    description="API for CS2 skin images and prices",
    version="1.0.0",
    lifespan=lifespan
)

@app.get("/")
def read_root():
    return {"message": "Welcome to the CS2 Weapons Data API! See /docs for available endpoints."}

@app.get("/skins", response_model=Dict[str, Any])
async def get_skins(
    limit: int = Query(50, ge=1, le=1000, description="Number of skins to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    search: Optional[str] = Query(None, description="Search query for skin names")
):
    """
    Get a list of CS2 skins. Supports pagination and searching by name.
    """
    global skins_data

    if not skins_data:
        raise HTTPException(status_code=503, detail="Skins data is currently being loaded or failed to load.")

    filtered_skins = skins_data

    # Apply search filter if provided
    if search:
        search_lower = search.lower()
        filtered_skins = [
            skin for skin in skins_data
            if search_lower in skin.get("name", "").lower()
        ]

    # Apply pagination
    paginated_skins = filtered_skins[offset:offset+limit]

    return {
        "total": len(filtered_skins),
        "limit": limit,
        "offset": offset,
        "data": paginated_skins
    }

@app.get("/skins/{skin_id}", response_model=Dict[str, Any])
async def get_skin_by_id(skin_id: str):
    """
    Get details for a specific CS2 skin by its ID.
    Includes the image URL, rarity, collections, etc.
    """
    global skins_index

    if not skins_index:
        raise HTTPException(status_code=503, detail="Skins data is currently being loaded or failed to load.")

    if skin_id not in skins_index:
        raise HTTPException(status_code=404, detail=f"Skin with ID '{skin_id}' not found.")

    return skins_index[skin_id]

@app.get("/price", response_model=Dict[str, Any])
async def get_price(
    market_hash_name: str = Query(..., description="The market hash name of the item (e.g., 'AK-47 | Redline (Field-Tested)')")
):
    """
    Get the current lowest price, median price, and volume for a CS2 item from the Steam Community Market.
    Requires the exact market hash name.
    """
    url = "https://steamcommunity.com/market/priceoverview/"
    params = {
        "appid": 730,
        "currency": 1, # USD
        "market_hash_name": market_hash_name
    }

    # Steam API rate limits quickly, so we handle failures gracefully
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, params=params, timeout=10.0)
            response.raise_for_status()
            data = response.json()

            if not data.get("success"):
                raise HTTPException(status_code=404, detail=f"Item '{market_hash_name}' not found on the Steam Market or rate limited.")

            return {
                "market_hash_name": market_hash_name,
                "lowest_price": data.get("lowest_price"),
                "median_price": data.get("median_price"),
                "volume": data.get("volume")
            }

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                 raise HTTPException(status_code=429, detail="Steam API rate limit exceeded. Please try again later.")
            raise HTTPException(status_code=e.response.status_code, detail=f"Steam API error: {str(e)}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to fetch price from Steam API: {str(e)}")

async def fetch_steam_price(client: httpx.AsyncClient, market_hash_name: str) -> Optional[float]:
    """Helper to fetch a price from Steam and cache it. Returns the numeric price value."""
    # Check cache first (expire after 1 hour)
    if market_hash_name in price_cache:
        cached = price_cache[market_hash_name]
        if time.time() - cached["timestamp"] < 3600:
            return cached["price"]

    url = "https://steamcommunity.com/market/priceoverview/"
    params = {
        "appid": 730,
        "currency": 1,
        "market_hash_name": market_hash_name
    }

    try:
        response = await client.get(url, params=params, timeout=10.0)
        # Handle rate limits gently for background tasks
        if response.status_code == 429:
            return None
        response.raise_for_status()
        data = response.json()

        if data.get("success") and "lowest_price" in data:
            # Parse price like "$48.07" -> 48.07
            price_str = data.get("lowest_price").replace("$", "").replace(",", "")
            try:
                price = float(price_str)
                price_cache[market_hash_name] = {"price": price, "timestamp": time.time()}
                return price
            except ValueError:
                return None
    except Exception:
        return None
    return None

@app.get("/inventory/{steam_id}", response_model=Dict[str, Any])
async def get_inventory(
    steam_id: str = Path(..., description="The Steam ID64 of the player"),
    fetch_prices: bool = Query(True, description="Attempt to fetch current Steam prices for all items. Note: This may be slow and hit rate limits.")
):
    """
    Fetch a player's CS2 inventory, map items to their descriptions, optionally fetch prices,
    sort them highest to lowest, and calculate the total inventory value.
    """
    url = f"https://steamcommunity.com/inventory/{steam_id}/730/2"
    params = {
        "l": "english",
        "count": 5000
    }

    # httpx doesn't always handle Steam's inventory headers properly without an explicit user-agent,
    # and occasionally the count=5000 parameter causes a 400 Bad Request on some accounts. Let's use 2000.
    params["count"] = 2000
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, params=params, headers=headers, timeout=20.0)

            if response.status_code == 403:
                raise HTTPException(status_code=403, detail="Inventory is private.")
            if response.status_code == 429:
                raise HTTPException(status_code=429, detail="Steam API rate limit exceeded.")

            response.raise_for_status()
            data = response.json()

            if "assets" not in data or "descriptions" not in data:
                 return {
                    "total_items": 0,
                    "total_value": 0.0,
                    "inventory": []
                 }

            # Create a lookup for descriptions by classid+instanceid
            desc_lookup = {}
            for desc in data["descriptions"]:
                key = f"{desc['classid']}_{desc['instanceid']}"
                desc_lookup[key] = desc

            # Parse assets and link to descriptions
            inventory_items = []
            for asset in data["assets"]:
                key = f"{asset['classid']}_{asset['instanceid']}"
                desc = desc_lookup.get(key)

                if desc and desc.get("marketable", 0) == 1:
                    item_name = desc.get("market_hash_name", desc.get("name", "Unknown Item"))
                    inventory_items.append({
                        "asset_id": asset["assetid"],
                        "name": item_name,
                        "type": desc.get("type"),
                        "icon_url": f"https://community.akamai.steamstatic.com/economy/image/{desc.get('icon_url')}",
                        "price": 0.0 # Default
                    })

            # Fetch prices if requested
            total_value = 0.0
            if fetch_prices and inventory_items:
                # Deduplicate item names to fetch prices
                unique_names = list(set(item["name"] for item in inventory_items))

                # We fetch prices sequentially with a small delay to avoid instantaneous rate limit
                # (Still likely to hit Steam's limits for large inventories).
                for name in unique_names:
                    price = await fetch_steam_price(client, name)
                    if price is not None:
                        # Update all items with this name
                        for item in inventory_items:
                            if item["name"] == name:
                                item["price"] = price
                                total_value += price
                    # Tiny delay to help prevent rate-limit 429s from Steam
                    await asyncio.sleep(0.5)

            # Sort inventory from highest to lowest price
            inventory_items.sort(key=lambda x: x["price"], reverse=True)

            return {
                "steam_id": steam_id,
                "total_items": len(inventory_items),
                "total_value": round(total_value, 2),
                "inventory": inventory_items
            }

        except httpx.HTTPStatusError as e:
             raise HTTPException(status_code=e.response.status_code, detail=f"Steam API Error: {str(e)}")
        except Exception as e:
             raise HTTPException(status_code=500, detail=f"Failed to fetch inventory: {str(e)}")
