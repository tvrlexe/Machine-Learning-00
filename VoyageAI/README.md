## VoyageAI – Smart Travel Data Collection Pipeline

This project is part of VoyageAI, an intelligent touristic activties recommendation system that combines weather, seasonal trends, and activity popularity across 15 countries.

I built this pipeline to automatically collect and merge different types of data, from climate (temperature, daylight, wind, precipitation) to Google Trends activity data like hiking, museum, beach, and more for the sake of training a model which finetuned parameters would be used to assign a score for a group of activities.

🧩 What This Pipeline Does

Pulls city coordinates(latitude and longitude) from a large open-source CSV (states.csv on GitHub)

Fetches historical weather data from the Open-Meteo API

Gets country-regions trend scores for 11 activity types using SerpAPI(Google Trend)

Get country-regions average rating of 15 activities using SerpAPI(Google Map)

Processes everything into a clean dataset (scoring_dataset.csv)

⚙️ How It Works

I wrote the code myself and used AI to improve the debugging and handle repetitive error cases.
All the logic, API setup, and data strategy decisions were made by me.

Taking into account the constraints:
I selected 15 countries based on hemisphere and season types.
I chose 11 activity types such as hiking, museum, cultural, shopping, and natural.
I used seasonal data averages instead of daily data because daily calls would make too many API requests.
I found a public GitHub CSV with coordinates for thousands of cities and adjusted names like Kyoto (which had an accent) so it would match correctly.
I used my own API keys and designed all request parameters.
Each data point combines trend score and average climate metrics to make the dataset more useful for model training.

🧠 Design Choices

Season-based sampling:
Instead of fetching weather data day by day, I collected by season. It’s faster, cheaper, and still gives meaningful averages.

Flexible structure:
It’s easy to add more activities, countries, or seasons without changing the core logic.

Readable and transparent:
All errors and logs show what’s happening at each step, making debugging simple.

🔑 APIs and Resources Used

Open-Meteo Archive API for historical weather data

SerpAPI (Google Trends) for activity popularity

Countries–States–Cities CSV for latitude and longitude(https://github.com/dr5hn/countries-states-cities-database/blob/master/csv/states.csv
  Github Countries-States-Cities dataset: https://lnkd.in/eRJG2iYz)

🚀 Why I Built It This Way

I wanted a clean, realistic dataset for training VoyageAI’s travel activity recommender.
Instead of relying on pre-made datasets, I built a custom pipeline that adapts to real seasonal and geographic conditions.

