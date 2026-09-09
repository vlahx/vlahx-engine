from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.utils.db import get_db

router = APIRouter()


@router.get("/")
def api_root():
    return {
        "service": "vlahx-core",
        "health": "/api/status",
    }


@router.get("/status")
def api_status(response: Response, db: Session = Depends(get_db)):
    """Răspuns pentru monitorizare: verificare conexiune SQLite."""
    db_ok = False
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False

    payload = {
        "status": "healthy" if db_ok else "unhealthy",
        "service": "vlahx-core",
        "checks": {"database": "ok" if db_ok else "error"},
    }
    if not db_ok:
        response.status_code = 503
    return payload


WEATHER_API_KEY = "a64230bd5eeac293c6064da395daefaf"


@router.get("/weather")
async def get_weather(city: str | None = None, lat: float | None = None, lon: float | None = None):
    """
    Real-time global weather endpoint.
    Prefers browser geolocation (lat/lon). Falls back to global city lookup (no hardcoded country code).
    """
    import httpx
    import logging
    logger = logging.getLogger(__name__)

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            target_lat, target_lon = lat, lon
            city_name = city

            # If city is given without lat/lon, geocode globally (worldwide)
            if (target_lat is None or target_lon is None) and city:
                geo_url = "http://api.openweathermap.org/geo/1.0/direct"
                geo_params = {"q": city.strip(), "limit": 1, "appid": WEATHER_API_KEY}
                geo_resp = await client.get(geo_url, params=geo_params)
                geo_data = geo_resp.json()
                if geo_data:
                    target_lat = geo_data[0]["lat"]
                    target_lon = geo_data[0]["lon"]
                    city_name = geo_data[0].get("name", city)

            if target_lat is None or target_lon is None:
                target_lat, target_lon = 44.4323, 26.1063
                city_name = "București"

            weather_url = "https://api.openweathermap.org/data/2.5/weather"
            weather_params = {
                "lat": target_lat,
                "lon": target_lon,
                "appid": WEATHER_API_KEY,
                "units": "metric",
                "lang": "ro"
            }
            w_resp = await client.get(weather_url, params=weather_params)
            w_data = w_resp.json()

            if w_resp.status_code != 200:
                return {"status": "error", "message": w_data.get("message", "Weather API error")}

            main_data = w_data.get("main", {})
            weather_info = w_data.get("weather", [{}])[0]
            resolved_city = w_data.get("name") or city_name or "București"

            return {
                "status": "success",
                "city": resolved_city,
                "temp": round(main_data.get("temp", 0), 1),
                "feels_like": round(main_data.get("feels_like", 0), 1),
                "description": weather_info.get("description", "").title(),
                "icon": weather_info.get("icon", "01d"),
                "humidity": main_data.get("humidity")
            }
    except Exception as e:
        logger.error(f"Weather API error: {e}")
        return {"status": "error", "message": str(e)}

