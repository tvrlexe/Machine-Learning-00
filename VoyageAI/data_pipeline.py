import requests
import pandas as pd
import numpy as np
import openmeteo_requests
import requests_cache
from retry_requests import retry
from typing import Dict, List, Optional, Tuple
import time
import unicodedata

class Dataset():
    def __init__(self, file: str, countries_details: Dict, open_meteo_url: str, api_key: str):
        self.file = file
        self.countries_details = countries_details
        self.api_key = api_key
        self.open_meteo_url = open_meteo_url
    
    def serpapi_search(self, params) -> Optional[Dict]:
        """Direct SerpAPI call - returns None on failure"""
        time.sleep(1.5)
        try:
            response = requests.get(
                "https://serpapi.com/search",
                params=params,
                timeout=60,
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('error'):
                    print(f"SerpAPI returned error: {data.get('error')}")
                    return None
                return data
            else:
                print(f"SerpAPI HTTP Error {response.status_code}")
                return None
                
        except requests.exceptions.Timeout:
            print("SerpAPI timeout after 60 seconds")
            return None
        except Exception as e:
            print(f"SerpAPI Request Failed: {e}")
            return None
    
    def collect_coordinates(self, city: str) -> Tuple[float, float]:
        try:
            df = pd.read_csv(self.file)
            city_lower = city.lower()
            row = df[df['name'].str.lower().str.contains(city_lower, na=False)]
            if row.empty:
                row = df[df['name'].str.lower() == city_lower]
                if row.empty:
                    raise ValueError(f"No coordinates found for '{city}'")
            lat, lon = row[['latitude', 'longitude']].iloc[0]
            return float(lat), float(lon)
        except Exception as e:
            raise Exception(f"Coordinate error for {city}: {e}")
    
    def collect_weather_data(self, lat: float, lon: float, start_date: str, end_date: str, duration: int):
        try:
            cache_session = requests_cache.CachedSession('.cache', expire_after=3600)
            retry_session = retry(cache_session, retries=5, backoff_factor=0.2)
            openmeteo = openmeteo_requests.Client(session=retry_session)
          
            params = {
                "latitude": lat,
                "longitude": lon,
                "start_date": start_date,
                "end_date": end_date,
                "daily": ["precipitation_sum", "temperature_2m_mean", "daylight_duration", "wind_speed_10m_max"],
            }
            
            responses = openmeteo.weather_api(self.open_meteo_url, params=params)
            response = responses[0]
            daily = response.Daily()
            return self.process_weather_data(daily, duration)
        except Exception as e:
            raise Exception(f"Weather data error for {lat},{lon}: {e}")
    
    def process_weather_data(self, daily, duration):
        try:
            precipitation_values = daily.Variables(0).ValuesAsNumpy()
            temperature_values = daily.Variables(1).ValuesAsNumpy()
            daylight_values = daily.Variables(2).ValuesAsNumpy()
            wind_speed_values = daily.Variables(3).ValuesAsNumpy()
            
            daily_precipitation_avg = np.mean(precipitation_values)
            daily_temperature_avg = np.mean(temperature_values)
            daily_daylight_avg = np.mean(daylight_values)
            daily_wind_speed_avg = np.mean(wind_speed_values)
            
            print(f"Weather: {daily_temperature_avg:.1f}°C, {daily_precipitation_avg:.1f}mm rain")
            
            return daily_precipitation_avg, daily_temperature_avg, daily_daylight_avg, daily_wind_speed_avg
            
        except Exception as e:
            raise Exception(f"Weather data processing error: {e}")
    
    def normalize_name(self, name: str) -> str:
        """Normalize names by removing accents and special characters"""
        normalized = unicodedata.normalize('NFKD', name)
        normalized = ''.join(c for c in normalized if not unicodedata.combining(c))
        return normalized.lower().strip()
    
    def get_country_trends(self, activity: str, country: str, season: str) -> Optional[float]:
        """Get country-level trends and extract regional averages"""
        try:
            country_code = Geo.get(country)
            if not country_code:
                raise Exception(f"No country code found for {country}")
            
            seasonal_range = self.get_seasonal_ranges(self.countries_details[country])
            season_dates = seasonal_range.get(season, {})
            
            if not season_dates:
                raise Exception(f"No season dates found for {season} in {country}")
            
            # Use previous year for historical data
            start_date = season_dates['start'].replace('2024', '2023')
            end_date = season_dates['end'].replace('2024', '2023')
            
            print(f"Getting country trends for '{activity}' in {country} ({season})...")
            
            params = {
                "engine": "google_trends",
                "q": activity,
                "geo": country_code,
                "date": f"{start_date} {end_date}",
                "regions": "CITY",
                "data_type": "GEO_MAP_0",
                "api_key": self.api_key
            }
            
            results = self.serpapi_search(params)
            if not results:
                raise Exception(f"Country trend API failed for {activity} in {country}")
            
            return self.process_regional_trend(results, country, activity)
            
        except Exception as e:
            print(f"Country trend error for {activity} in {country}: {e}")
            return None

    def process_regional_trend(self, trend_data: Dict, country: str, activity: str) -> Optional[float]:
        """Process regional data and return average score for the country"""
        try:
            if not trend_data:
                raise Exception("No trend data provided")
                
            interest_data = trend_data.get("interest_by_region", [])
            if not interest_data:
                print(f"  No regional data found for {activity} in {country}")
                return 0.1  # Minimal baseline
            
            print(f"  Found {len(interest_data)} regions in trend data")
            
            # Get all regional scores
            region_scores = []
            for region in interest_data:
                location = region.get("location", "")
                extracted_value = region.get("extracted_value", 0)
                if extracted_value > 0:  # Only include regions with actual data
                    region_scores.append(extracted_value)
                    print(f"  Region {location}: {extracted_value}")
            
            if not region_scores:
                print(f"  No valid trend scores found for {activity}")
                return 0.1
            
            # Calculate average of all regions
            avg_score = np.mean(region_scores)
            normalized_score = min(1.0, avg_score / 100)
            print(f"  Country average trend score: {normalized_score:.3f} (from {len(region_scores)} regions)")
            return normalized_score
            
        except Exception as e:
            print(f"Regional trend processing error: {e}")
            return 0.1

    def get_seasonal_ranges(self, country_seasons):
        seasons = list(country_seasons.items())
        seasonal_ranges = {}
        
        for i in range(len(seasons)):
            season_name, start_date = seasons[i]
            
            if i < len(seasons) - 1:
                _, end_date = seasons[i + 1]
            else:
                _, end_date = seasons[0]
                end_date = end_date.replace("2024", "2025")
            
            seasonal_ranges[season_name] = {
                'start': start_date,
                'end': end_date
            }
        
        return seasonal_ranges

    def run_optimized_data_collection(self):
        """Optimized data collection targeting ~1000 rows"""
        all_data = []
        failed_attempts = 0
        max_failures = 50
        
        # Process all countries with original regions
        for country in list(self.countries_details.keys()):
            print(f"\n{'='*50}")
            print(f"PROCESSING: {country.upper()}")
            print(f"{'='*50}")
            
            # Use ALL regions for each country
            cities = Regions.get(country, [])
            print(f"Processing {len(cities)} regions...")
            
            for city_idx, city in enumerate(cities):
                print(f"\n REGION {city_idx+1}/{len(cities)}: {city}")
                
                try:
                    lat, lon = self.collect_coordinates(city)
                    print(f"   Coordinates: {lat:.4f}, {lon:.4f}")
                    
                    # Process ALL seasons for each region
                    seasons_to_process = list(self.countries_details[country].keys())
                    print(f"   Processing {len(seasons_to_process)} seasons...")
                    
                    for season_idx, season in enumerate(seasons_to_process):
                        print(f"   SEASON {season_idx+1}/{len(seasons_to_process)}: {season}")
                        
                        duration = SEASON_DURATIONS.get(country, {}).get(season, 90)
                        seasonal_range = self.get_seasonal_ranges(self.countries_details[country])
                        season_dates = seasonal_range.get(season, {})
                        
                        if not season_dates:
                            print(f"   No dates for {season}")
                            continue
                        
                        # Get weather data for this region/season
                        print(f"   Getting weather data...")
                        weather_data = self.collect_weather_data(
                            lat, lon, 
                            season_dates['start'], 
                            season_dates['end'], 
                            duration
                        )
                        
                        # Process ALL activities for this region/season
                        successful_activities = 0
                        for activity_idx, activity in enumerate(activities):
                            if failed_attempts >= max_failures:
                                print(f"   Too many failures - stopping")
                                return pd.DataFrame(all_data)
                            
                            # Use country-level trends (smarter approach)
                            trend_score = self.get_country_trends(activity, country, season)
                            
                            if trend_score is not None:
                                data_point = {
                                    'country': country,
                                    'city': city,
                                    'activity': activity,
                                    'season': season,
                                    'trend_score': trend_score,
                                    'avg_daily_precipitation': weather_data[0],
                                    'avg_daily_temperature': weather_data[1],
                                    'avg_daily_daylight': weather_data[2],
                                    'avg_daily_wind_speed': weather_data[3],
                                    'season_duration': duration
                                }
                                
                                all_data.append(data_point)
                                successful_activities += 1
                                print(f"   {activity}: {trend_score:.3f}")
                            else:
                                failed_attempts += 1
                                print(f"   {activity}: failed")
                        
                        print(f"   Success: {successful_activities}/{len(activities)} activities")
                        
                        # Early stopping if we reach target
                        if len(all_data) >= 1000:
                            print(f"   🎯 Reached target of 1000 data points!")
                            return pd.DataFrame(all_data)
                            
                except Exception as e:
                    print(f"   Failed to process {city}: {e}")
                    failed_attempts += 1
                    if failed_attempts >= max_failures:
                        print("   Too many failures - stopping")
                        return pd.DataFrame(all_data)
        
        return pd.DataFrame(all_data)


# ORIGINAL REGIONS (SMARTER APPROACH)
Regions = { 
    "France": ["Île-de-France", "Provence-Alpes-Côte-d'Azur", "Auvergne-Rhône-Alpes", "Occitanie"],
    "Spain": ["Catalonia", "Community of Madrid", "Andalusia", "Valencian Community"],
    "Italy": ["Lazio", "Tuscany", "Veneto", "Lombardy"],
    "United Kingdom": ["England", "Scotland", "Wales", "Northern Ireland"],
    "Japan": ["Tokyo", "Kyōto", "Ōsaka", "Hokkaidō"],
    "United States": ["California", "New York", "Texas", "Florida"],
    "Canada": ["Ontario", "Quebec", "British Columbia", "Alberta"],
    "Turkey": ["İstanbul", "Ankara", "İzmir", "Antalya"],
    "Australia": ["New South Wales", "Victoria", "Queensland", "Western Australia"],
    "Thailand": ["Bangkok", "Phuket", "Chiang Mai"],
    "Brazil": ["Rio de Janeiro", "São Paulo", "Bahia", "Minas Gerais"],
    "Mexico": ["Ciudad de México", "Jalisco", "Nuevo León", "Baja California"],
    "Egypt": ["Cairo", "Alexandria", "Giza", "Luxor"],
    "Kenya": ["Nairobi", "Mombasa", "Kisumu", "Nakuru"],
    "Malaysia": ["Kuala Lumpur", "Selangor", "Johor", "Penang"]
}

# Rest of configuration remains the same...
Country_details = {
    "France": {"spring": "2024-03-01", "summer": "2024-06-01", "fall": "2024-09-01", "winter": "2024-12-01"},
    "Spain": {"spring": "2024-03-01", "summer": "2024-06-01", "fall": "2024-09-01", "winter": "2024-12-01"},
    "Italy": {"spring": "2024-03-01", "summer": "2024-06-01", "fall": "2024-09-01", "winter": "2024-12-01"},
    "United Kingdom": {"spring": "2024-03-01", "summer": "2024-06-01", "fall": "2024-09-01", "winter": "2024-12-01"},
    "Japan": {"spring": "2024-03-01", "summer": "2024-06-01", "fall": "2024-09-01", "winter": "2024-12-01"},
    "United States": {"spring": "2024-03-01", "summer": "2024-06-01", "fall": "2024-09-01", "winter": "2024-12-01"},
    "Canada": {"spring": "2024-03-01", "summer": "2024-06-01", "fall": "2024-09-01", "winter": "2024-12-01"},
    "Turkey": {"spring": "2024-03-01", "summer": "2024-06-01", "fall": "2024-09-01", "winter": "2024-12-01"},
    "Australia": {"spring": "2024-09-01", "summer": "2024-12-01", "fall": "2024-03-01", "winter": "2024-06-01"},
    "Thailand": {"dry": "2024-11-01", "hot": "2024-03-01", "wet": "2024-06-01"},
    "Brazil": {"dry": "2024-05-01", "wet": "2024-10-01"},
    "Mexico": {"dry": "2024-11-01", "wet": "2024-05-01"},
    "Egypt": {"winter": "2024-12-01", "summer": "2024-06-01"},
    "Kenya": {"dry": "2024-06-01", "wet": "2024-03-01"},
    "Malaysia": {"dry": "2024-05-01", "wet": "2024-11-01"}
}

Geo = {
    "France": "FR", "Spain": "ES", "Italy": "IT", "United Kingdom": "GB",
    "Japan": "JP", "United States": "US", "Canada": "CA", "Australia": "AU",
    "Thailand": "TH", "Brazil": "BR", "Mexico": "MX", "Egypt": "EG",
    "Kenya": "KE", "Turkey": "TR", "Malaysia": "MY"
}

activities = [
    "hiking", "museum", "beach", "park", "religious", 
    "architecture", "historic", "amusement", "cultural", "shopping", "natural"
]

SEASON_DURATIONS = {
    "France": {"spring": 92, "summer": 92, "fall": 91, "winter": 90},
    "Spain": {"spring": 92, "summer": 92, "fall": 91, "winter": 90},
    "Italy": {"spring": 92, "summer": 92, "fall": 91, "winter": 90},
    "United Kingdom": {"spring": 92, "summer": 92, "fall": 91, "winter": 90},
    "Japan": {"spring": 92, "summer": 92, "fall": 91, "winter": 90},
    "United States": {"spring": 92, "summer": 92, "fall": 91, "winter": 90},
    "Canada": {"spring": 92, "summer": 92, "fall": 91, "winter": 90},
    "Turkey": {"spring": 92, "summer": 92, "fall": 91, "winter": 90},
    "Australia": {"spring": 92, "summer": 92, "fall": 91, "winter": 90},
    "Thailand": {"dry": 182, "hot": 91, "wet": 92},
    "Brazil": {"dry": 153, "wet": 212},
    "Mexico": {"dry": 182, "wet": 183},
    "Egypt": {"winter": 182, "summer": 183},
    "Kenya": {"dry": 182, "wet": 183},
    "Malaysia": {"dry": 183, "wet": 182}
}

#######################################################
#####REPLACE api_key WITH YOUR SERPAPI PRIVATE KEY#####
#######################################################

api_key = "REPLACE WITH YOUR SERPAPI PRIVATE KEY"
github = "https://raw.githubusercontent.com/dr5hn/countries-states-cities-database/master/csv/states.csv"

# Execute
dataset = Dataset(
    file=github, 
    countries_details=Country_details,
    open_meteo_url="https://archive-api.open-meteo.com/v1/archive",
    api_key=api_key
)

print("STARTING OPTIMIZED DATA COLLECTION")
print("Using original regions with country-level trend averages")
print("Target: ~1000 data points")
print("Strategy: All regions × All seasons × All activities")

complete_data = dataset.run_optimized_data_collection()

if len(complete_data) > 0:
    print(f"\nSUCCESS! Collected {len(complete_data)} data points")
    complete_data.to_csv("regional_travel_dataset.csv", index=False)
    print("Dataset saved as 'regional_travel_dataset.csv'")
    
    print(f"\nDATA ANALYTICS:")
    print(f"   Total data points: {len(complete_data)}")
    print(f"   Countries: {complete_data['country'].nunique()}")
    print(f"   Regions: {complete_data['city'].nunique()}")
    print(f"   Activities: {complete_data['activity'].nunique()}")
    print(f"   Seasons: {complete_data['season'].nunique()}")
    
    print(f"\nData distribution by country:")
    for country, count in complete_data['country'].value_counts().items():
        print(f"   {country}: {count} points")
    
    print(f"\nSample data:")
    print(complete_data.head())
    
else:
    print("COLLECTION FAILED - No data collected")