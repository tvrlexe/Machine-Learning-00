## VoyageAI Weather-Trend Dataset Builder
This script collects activity trend and weather data across 15 countries using SerpAPI (Google Trends) and Open Meteo APIs. 
I built it as part of my VoyageAI recommendation system project to analyze how weather and seasonality influence tourism activities.

To diversify efficiently the dataset, the Countries-States-Cities dataset from GitHub was used to extract the latitude and longitude of selected locations. Given the limited API resources, the pipeline focuses on four strategic regions for each of the fifteen most visited countries across five continents.

Using these coordinates, the system integrates SERP API and Open-Meteo API to gather regional data such as average trends, ratings, daily temperature, daily precipitation, maximum wind speed, and average daylight duration for every season. The processed results are then stored in a CSV file, creating a solid foundation for model training.

Although the SERP API free plan limits the number of requests, the current setup provides enough data to build an MVP. The modular design also makes the pipeline adaptable according to the user's needs (updating the API plan or increasing the scope of the data sampling can be achieved with minimal changes).

Summary:
  FULL ETL PIPELINE AND DATASET(CSV FORMAT)
  FULL ETL PIPELINE FROM SCRATCH
  Full data pipeline to train an ML Model. The parameters of the ml model will be used as metrics to assign a score for touristic activities in a larger recommendation system i am working on.
  Tools used:
  - SERP API(Google Trends and Google Map)
  - Open meteo API
  - GitHub csv (to get latitude and longitude): https://github.com/dr5hn/countries-states-cities-database/blob/master/csv/states.csv
  Github Countries-States-Cities dataset: https://lnkd.in/eRJG2iYz 
