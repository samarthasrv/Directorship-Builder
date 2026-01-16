# Directorship Builder (Companies House)

Paste a Companies House **officer appointments** link and get an output list like:

Company Name - Role (Month YYYY - Month YYYY/Present)

This uses the Companies House Public Data API endpoint:
GET /officers/{officer_id}/appointments

## Environment variable required

Set:

COMPANIES_HOUSE_API_KEY = <your Companies House API key>

Companies House API authentication uses HTTP Basic auth:
- username = API key
- password = blank

## Run locally (optional)

1) Install Python 3
2) Install dependencies:

   pip install -r requirements.txt

3) Set your API key and run:

   COMPANIES_HOUSE_API_KEY=YOUR_KEY python app.py

Then open: http://localhost:5000

## Deploy to Heroku

- Create a Heroku app
- Connect it to your GitHub repo
- In Heroku Settings -> Config Vars, set:
  COMPANIES_HOUSE_API_KEY = your key
- Deploy
