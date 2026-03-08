import httpx
import asyncio
from fastapi import FastAPI, HTTPException, Query
from typing import List, Optional, Dict, Any
from contextlib import asynccontextmanager

# In-memory cache for skins data
skins_data = []
skins_index = {} # Map skin id to skin data

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
