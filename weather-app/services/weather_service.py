import requests
import logging

class WeatherService:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "http://api.weatherapi.com/v1"

    def get_weather_data(self, location):
        try:
            current_weather_url = f"{self.base_url}/current.json?key={self.api_key}&q={location}"
            forecast_url = f"{self.base_url}/forecast.json?key={self.api_key}&q={location}&days=5"
            current_response = requests.get(current_weather_url)
            forecast_response = requests.get(forecast_url)
            
            if current_response.status_code == 200 and forecast_response.status_code == 200:
                current_weather = current_response.json()
                forecast = forecast_response.json()
                return {
                    'location': current_weather['location'],
                    'current': current_weather['current'],
                    'forecast': forecast['forecast']
                }
            else:
                logging.error(f"Error fetching weather data: {current_response.status_code}, {forecast_response.status_code}")
                return None
        except Exception as e:
            logging.error(f"Exception in get_weather_data: {str(e)}")
            return None
