# Fictional Confirmed Plan

This fictional plan shows the exact contract shared by plan compliance and
Garmin workout rendering. The prose explains intent; the single `plan-data`
block is the confirmed machine-readable source.

## Intent and guardrails

- Four running days per week: one quality session, two easy/recovery sessions,
  and one long run.
- Pace targets are controlled ranges. Pain, an athlete limit, or a material
  recovery signal requires a new proposal rather than silent changes.
- The renderer previews a 14-day-or-longer horizon before any remote write.

```plan-data
{
  "version": 1,
  "plan": {
    "id": "fictional-10k-build",
    "status": "active"
  },
  "sessions": [
    {
      "id": "fictional-2026-04-08-intervals",
      "date": "2026-04-08",
      "name": "Controlled intervals",
      "steps": [
        {"kind": "warmup", "distance_m": 1600},
        {"kind": "repeat", "count": 4, "steps": [
          {"kind": "interval", "distance_m": 800, "target": {"kind": "pace", "min": "4:45/km", "max": "5:00/km"}},
          {"kind": "recovery", "time_s": 90}
        ]},
        {"kind": "cooldown", "distance_m": 1600}
      ]
    },
    {
      "id": "fictional-2026-04-10-easy",
      "date": "2026-04-10",
      "name": "Easy reset",
      "steps": [
        {"kind": "warmup", "distance_m": 1000},
        {"kind": "recovery", "distance_m": 5000, "target": {"kind": "heart_rate", "min": 125, "max": 145}},
        {"kind": "cooldown", "distance_m": 1000}
      ]
    },
    {
      "id": "fictional-2026-04-12-long",
      "date": "2026-04-12",
      "name": "Easy long run",
      "steps": [
        {"kind": "warmup", "distance_m": 1000},
        {"kind": "recovery", "distance_m": 12000, "target": {"kind": "heart_rate", "min": 125, "max": 150}},
        {"kind": "cooldown", "distance_m": 1000}
      ]
    },
    {
      "id": "fictional-2026-04-15-threshold",
      "date": "2026-04-15",
      "name": "Threshold rhythm",
      "steps": [
        {"kind": "warmup", "distance_m": 1600},
        {"kind": "repeat", "count": 3, "steps": [
          {"kind": "interval", "time_s": 480, "target": {"kind": "pace", "min": "4:55/km", "max": "5:10/km"}},
          {"kind": "recovery", "time_s": 120}
        ]},
        {"kind": "cooldown", "distance_m": 1600}
      ]
    },
    {
      "id": "fictional-2026-04-17-easy",
      "date": "2026-04-17",
      "name": "Easy aerobic",
      "steps": [
        {"kind": "warmup", "distance_m": 1000},
        {"kind": "recovery", "distance_m": 6000, "target": {"kind": "heart_rate", "min": 125, "max": 145}},
        {"kind": "cooldown", "distance_m": 1000}
      ]
    },
    {
      "id": "fictional-2026-04-19-long",
      "date": "2026-04-19",
      "name": "Steady long run",
      "steps": [
        {"kind": "warmup", "distance_m": 1000},
        {"kind": "recovery", "distance_m": 14000, "target": {"kind": "heart_rate", "min": 125, "max": 150}},
        {"kind": "cooldown", "distance_m": 1000}
      ]
    }
  ]
}
```
