# Air-Pollutant-Training-Exposure-MLS-Next-Pro

## Overview
This project investigates the relationship between air pollutants during the days leading up to a soccer match and team performance during the match. Below is an explanation of the data located in analysis_dataset.csv

## Data
The project uses data from the:
- **Analytics Data:** 2025 MLS NEXT Pro season, American Soccer Analysis, Open-Meteo AQI
- **Air Quality Data:** Open-Meteo, Weather Underground, Elevation Finder

## Match and Performance Data
Performance variables includes:
- Match date
- Home team
- Away team
- Match location/stadium
- Passes
- Passing accuracy
- Fouls
- Yellow cards
- Red cards
- Shots
- Shots on target
- xG
- Possession, where available

## Air Quality Data
Environmental variables includes:
- US AQI
- European AQI
- PM2.5
- PM10
- O₃ (ozone)
- NO₂ (nitrogen dioxide)

## Weather & Elevation Data
Weather Variables includes:
- Temperature
- Relative humidity
- Temperature × humidity
- Heat index
- Wet-bulb temperature

Elevation Variables includes:
- Home-team elevation
- Away-team elevation
- Elevation difference
- Elevation gain/difference associated with travel

## Exposure Methodology

Environmental exposure is calculated over multiple pre-match windows to test whether results are sensitive to the definition of "pre-match exposure."

The analysis considers:
- 3-day exposure window
- 5-day exposure window
- 7-day exposure window

For away teams, different travel assumptions are also evaluated, including:
- 1 day in the match region
- 2 days in the match region
- 3 days in the match region
- Home-region exposure assumptions

This allows the analysis to test whether relationships remain consistent when reasonable assumptions about team travel and pre-match exposure are changed.
