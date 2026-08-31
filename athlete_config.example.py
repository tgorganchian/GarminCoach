"""Generic local configuration for GarminCoach data processing.

Copy this file to athlete_config.py only through guided setup. It is ignored by
Git and must contain your own values. Confirmed sessions belong exclusively in
coaching/training-plan.md, never in this file.
"""

HR_ZONES = []
# Which of those zones count as easy and as hard, as 1-based numbers into
# HR_ZONES. Leave as None to split the list into thirds, which reads a
# five-zone system as easy 1-2 / moderate 3 / hard 4-5, and a three-zone
# LT1-LT2 system as one zone per band.
EASY_ZONE_MAX = None
HARD_ZONE_MIN = None
# Optional manual date for a pre/post-gear HR comparison. Garmin gear tracking
# works without this setting.
GEAR_CHANGE_DATE = None
GEAR_CHANGES_SECTION = ""
RACE_CALENDAR = []
LONG_RUN_KM = None
QUALITY_LAP_PACE_THRESHOLD = None
MIN_QUALITY_LAP_KM = None
QUALITY_KEYWORDS = []
PERSONAL_RECORDS = []
WEATHER_LAT = None
WEATHER_LON = None
WEATHER_TIMEZONE = ""
