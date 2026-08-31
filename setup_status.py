"""Report local GarminCoach readiness without reading secrets back to stdout."""

from garmin_coach.readiness import main


if __name__ == "__main__":
    raise SystemExit(main())
