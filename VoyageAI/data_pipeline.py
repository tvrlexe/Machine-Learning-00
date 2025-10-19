import requests
import pandas as pd
import numpy as np
import openmeteo_requests
import requests_cache
from retry_requests import retry
from typing import Dict, List, Optional, Tuple
import time

class Dataset():
    def __init__(self, file: str, countries_details: Dict, open_meteo_url: str, api_key: str):
        self.file = file
        self.countries_details = countries_details
        self.api_key = api_key
        self.open_meteo_url = open_meteo_url
    
    def serpapi_search(self, params) -> Optional[Dict]:
        """Direct SerpAPI call - returns None on failure"""
        time.sleep(2)
        try:
            response = requests.get(
                "https://serpapi.com/search",
                params=params,
                timeout= 120,
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
            print("SerpAPI timeout after 120 seconds")
            return None
        except Exception as e:
            print(f"SerpAPI Request Failed: {e}")
            return None
    
    def collect_coordinates(self, city: str) -> Tuple[float, float]:
        try:
            df = pd.read_csv(self.file)
            row = df[df['name'].str.lower() == city.lower()]
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
            daily_precipitation_sum = np.sum(daily.Variables(0).ValuesAsNumpy())/duration
            daily_temperature_2m_mean = np.sum(daily.Variables(1).ValuesAsNumpy())/duration
            daily_daylight_duration = np.sum(daily.Variables(2).ValuesAsNumpy())/duration
            daily_wind_speed_10m_max = np.sum(daily.Variables(3).ValuesAsNumpy())/duration
            return daily_precipitation_sum, daily_temperature_2m_mean, daily_daylight_duration, daily_wind_speed_10m_max
        except Exception as e:
            raise Exception(f"Weather data processing error: {e}")
    
    def get_country_trends(self, activity: str, country: str, season: str) -> Optional[float]:
        """Get country-level trends using GEO_MAP_0 for single activities"""
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
            
            return self.process_geomap_trend(results, country)
            
        except Exception as e:
            print(f"Country trend error for {activity} in {country}: {e}")
            return None

    def process_geomap_trend(self, trend_data: Dict, country: str) -> Optional[float]:
        """Process GEO_MAP_0 data for country-level trends"""
        try:
            if not trend_data:
                raise Exception("No trend data provided")
                
            interest_data = trend_data.get("interest_by_region", [])
            if not interest_data:
                raise Exception("No interest_by_region data found")
            
            print(f"Found {len(interest_data)} regions in trend data")
            
            region_scores = []
            for region in interest_data:
                location = region.get("location", "")
                extracted_value = region.get("extracted_value", 0)
                region_scores.append(extracted_value)
                print(f"Region {location}: {extracted_value}")
            
            if not region_scores:
                raise Exception("No region scores found")
            
            avg_score = np.mean(region_scores)
            normalized_score = min(1.0, avg_score / 100)
            print(f"Country average trend score: {normalized_score:.3f} (from {len(region_scores)} regions)")
            return normalized_score
            
        except Exception as e:
            print(f"GEO_MAP processing error: {e}")
            return None

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

    def run_complete_data_collection(self):
        """Run data collection for all 15 countries with optimized sampling"""
        all_data = []
        failed_attempts = 0
        max_failures = 20
        
        # Process all 15 countries but with optimized sampling
        for country in list(self.countries_details.keys()):
            print(f"Processing {country}...")
            
            # Get 2 cities per country for efficiency
            cities = Regions.get(country, [])[:4]
            
            for city in cities:
                print(f"Processing {city}...")
                
                try:
                    lat, lon = self.collect_coordinates(city)
                    print(f"Coordinates: {lat}, {lon}")
                    
                    # Process 2 main seasons per country
                    seasons_to_process = list(self.countries_details[country].keys())[:2]
                    
                    for season in seasons_to_process:
                        print(f"Processing {season} season...")
                        
                        duration = SEASON_DURATIONS.get(country, {}).get(season, 90)
                        seasonal_range = self.get_seasonal_ranges(self.countries_details[country])
                        season_dates = seasonal_range.get(season, {})
                        
                        if not season_dates:
                            print(f"No season dates for {season}")
                            continue
                        
                        print(f"Collecting weather data...")
                        weather_data = self.collect_weather_data(
                            lat, lon, 
                            season_dates['start'], 
                            season_dates['end'], 
                            duration
                        )
                        print(f"Weather data collected")
                        
                        # Process 3 key activities per city/season
                        
                        for activity in activities:
                            print(f"Getting trends for '{activity}'...")
                            
                            trend_score = self.get_country_trends(activity, country, season)
                            
                            if trend_score is None:
                                failed_attempts += 1
                                print(f"Trend data failed for '{activity}'")
                                if failed_attempts >= max_failures:
                                    print("Too many failures - stopping")
                                    return pd.DataFrame(all_data)
                                continue
                            
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
                            print(f"Added {activity}: score={trend_score:.3f}")
                            
                except Exception as e:
                    print(f"Failed to process {city}: {e}")
                    failed_attempts += 1
                    if failed_attempts >= max_failures:
                        print("Too many failures - stopping")
                        return pd.DataFrame(all_data)
                    continue
        
        print(f"Collection completed:")
        print(f"Successful data points: {len(all_data)}")
        print(f"Failed attempts: {failed_attempts}")
        
        if len(all_data) == 0:
            print("No data collected - all API calls failed")
        else:
            print("Data collection completed successfully")
        
        return pd.DataFrame(all_data)


# Configuration for 15 countries
Country_details = {
    # Northern Hemisphere (Standard 4-season)
    "France": {"spring": "2024-03-01", "summer": "2024-06-01", "fall": "2024-09-01", "winter": "2024-12-01"},
    "Spain": {"spring": "2024-03-01", "summer": "2024-06-01", "fall": "2024-09-01", "winter": "2024-12-01"},
    "Italy": {"spring": "2024-03-01", "summer": "2024-06-01", "fall": "2024-09-01", "winter": "2024-12-01"},
    "United Kingdom": {"spring": "2024-03-01", "summer": "2024-06-01", "fall": "2024-09-01", "winter": "2024-12-01"},
    "Japan": {"spring": "2024-03-01", "summer": "2024-06-01", "fall": "2024-09-01", "winter": "2024-12-01"},
    "United States": {"spring": "2024-03-01", "summer": "2024-06-01", "fall": "2024-09-01", "winter": "2024-12-01"},
    "Canada": {"spring": "2024-03-01", "summer": "2024-06-01", "fall": "2024-09-01", "winter": "2024-12-01"},
    "Turkey": {"spring": "2024-03-01", "summer": "2024-06-01", "fall": "2024-09-01", "winter": "2024-12-01"},
    
    # Southern Hemisphere (Reversed seasons)
    "Australia": {"spring": "2024-09-01", "summer": "2024-12-01", "fall": "2024-03-01", "winter": "2024-06-01"},
    
    # Tropical (Wet/Dry seasons)
    "Thailand": {"dry": "2024-11-01", "hot": "2024-03-01", "wet": "2024-06-01"},
    "Brazil": {"dry": "2024-05-01", "wet": "2024-10-01"},
    "Mexico": {"dry": "2024-11-01", "wet": "2024-05-01"},
    "Egypt": {"winter": "2024-12-01", "summer": "2024-06-01"},
    "Kenya": {"dry": "2024-06-01", "wet": "2024-03-01"},
    "Malaysia": {"dry": "2024-05-01", "wet": "2024-11-01"}
}

Regions = { 
    "France": ["Île-de-France", "Provence-Alpes-Côte-d’Azur", "Auvergne-Rhône-Alpes", "Occitanie"],
    "Spain": ["Catalonia", "Community of Madrid", "Andalusia", "Valencian Community"],
    "Italy": ["Lazio", "Tuscany", "Veneto", "Lombardy"],
    "United Kingdom": ["England", "Scotland", "Wales", "Northern Ireland"],
    "Japan": ["Tokyo", "Kyōto", "Ōsaka", "Hokkaidō"],
    "United States": ["California", "New York", "Texas", "Florida"],
    "Canada": ["Ontario", "Quebec", "British Columbia", "Alberta"],
    "Turkey": ["İstanbul", "Ankara", "İzmir", "Antalya"],
    "Australia": ["New South Wales", "Victoria", "Queensland", "Western Australia"],
    "Thailand": ["Bangkok", "Phuket", "Chiang Mai"],  # Using major provinces
    "Brazil": ["Rio de Janeiro", "São Paulo", "Bahia", "Minas Gerais"],
    "Mexico": ["Ciudad de México", "Jalisco", "Nuevo León", "Baja California"],
    "Egypt": ["Cairo", "Alexandria", "Giza", "Luxor"],
    "Kenya": ["Nairobi", "Mombasa", "Kisumu", "Nakuru"],
    "Malaysia": ["Kuala Lumpur", "Selangor", "Johor", "Penang"]
}

Geo = {
    "France": "FR",
    "Spain": "ES", 
    "Italy": "IT",
    "United Kingdom": "GB",
    "Thailand": "TH",
    "Japan": "JP",
    "United States": "US",
    "Canada": "CA",
    "Australia": "AU",
    "Brazil": "BR", 
    "Mexico": "MX",
    "Egypt": "EG",
    "Kenya": "KE",
    "Turkey": "TR",
    "Malaysia": "MY"
}

activities = [
    "hiking",
    "museum",
    "beach",
    "park",
    "religious",
    "architecture",
    "historic",
    "amusement",
    "cultural",
    "shopping",
    "natural"
]

SEASON_DURATIONS = {
    # Standard 4-season countries (approx 3 months each)
    "France": {"spring": 92, "summer": 92, "fall": 91, "winter": 90},
    "Spain": {"spring": 92, "summer": 92, "fall": 91, "winter": 90},
    "Italy": {"spring": 92, "summer": 92, "fall": 91, "winter": 90},
    "United Kingdom": {"spring": 92, "summer": 92, "fall": 91, "winter": 90},
    "Japan": {"spring": 92, "summer": 92, "fall": 91, "winter": 90},
    "United States": {"spring": 92, "summer": 92, "fall": 91, "winter": 90},
    "Canada": {"spring": 92, "summer": 92, "fall": 91, "winter": 90},
    "Turkey": {"spring": 92, "summer": 92, "fall": 91, "winter": 90},
    
    # Southern Hemisphere (reversed but same durations)
    "Australia": {"spring": 92, "summer": 92, "fall": 91, "winter": 90},
    
    # Tropical countries (different season patterns)
    "Thailand": {"dry": 182, "hot": 91, "wet": 92},
    "Brazil": {"dry": 153, "wet": 212},
    "Mexico": {"dry": 182, "wet": 183},
    "Egypt": {"winter": 182, "summer": 183},
    "Kenya": {"dry": 182, "wet": 183},
    "Malaysia": {"dry": 183, "wet": 182}
}



api_key = "34e143a2f63e04ae6203fb0c5407eb7e1fee583979998d63e34580f50f0485a9"
github = "https://raw.githubusercontent.com/dr5hn/countries-states-cities-database/master/csv/states.csv"

# Usage
dataset = Dataset(
    file=github, 
    countries_details=Country_details,
    open_meteo_url="https://archive-api.open-meteo.com/v1/archive",
    api_key=api_key
)

# Run complete data collection
print("Starting data collection for 15 countries")
print("Optimized sampling: 2 cities/country, 2 seasons/country, 3 activities/city")
complete_data = dataset.run_complete_data_collection()

if len(complete_data) > 0:
    print(f"Success! Collected {len(complete_data)} data points")
    complete_data.to_csv("scoring_dataset.csv", index=False)
    print("Dataset saved as scoring_dataset.csv")
    print("\nSample data:")
    print(complete_data.head(10))
    
    # Show data distribution
    print(f"\nData distribution by country:")
    print(complete_data['country'].value_counts())
else:
    print("Failed! No data collected")