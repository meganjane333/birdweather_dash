# Harper Adams Live Bird Detections

A temporary event dashboard that checks BirdWeather station **12521** every
30 seconds and displays recent detections with confidence and probability of at
least 70%.

## Quick start on Windows

1. Install Python if it is not already installed.
2. Extract this folder and open PowerShell or Command Prompt inside it.
3. Create an isolated environment (recommended):

   ```powershell
   py -m venv .venv
   .venv\Scripts\activate
   ```

4. Install the packages:

   ```powershell
   py -m pip install -r requirements.txt
   ```

5. Run the dashboard:

   ```powershell
   py -m streamlit run app.py
   ```

Streamlit will normally open the dashboard automatically in the default web
browser. Press `F11` to show the browser full-screen at the event. Stop the app
by returning to the terminal and pressing `Ctrl+C`.

## Testing while the station is off

Station 12521 is named `HAU-Transect-2` in BirdWeather. If there are no
qualifying detections in the last 24 hours, the dashboard displays a clearly
labelled archive preview. This allows the layout and internet connection to be
tested before the station is turned on.

Once the station is uploading again, qualifying detections from the last 24
hours replace the archive preview automatically. There may be a short delay
between a bird being detected and BirdWeather making the record available.

## Easy changes

The settings at the top of `app.py` control the station, refresh rate and
filters:

```python
STATION_ID = "12521"
REFRESH_SECONDS = 30
MIN_CONFIDENCE = 0.70
MIN_PROBABILITY = 0.70
```

The page title can be changed in two places by searching `app.py` for:

```text
Harper Adams Live Bird Detections
```

## Event checklist

- Turn the station on early enough to confirm that uploads are reaching
  BirdWeather.
- Connect the event computer to Wi-Fi and run the dashboard.
- Confirm the green status line updates every 30 seconds.
- Disable sleep and screen-lock for the duration of the display.
- Keep the terminal window open in the background.
- Use a modern version of Chrome or Edge and press `F11` for full-screen mode.

## Important limitation

The display is near-live rather than instantaneous. It polls BirdWeather every
30 seconds, and BirdWeather may take additional time to receive and process a
detection. The dashboard also cannot determine definitively whether the
physical station is switched off; it reports when no recent qualifying data is
available.

