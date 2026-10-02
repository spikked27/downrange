# Automatic source inputs — alpha 1

The evaluator has no launch-provider whitelist. Every cached launch with usable pad coordinates receives a source-backed or explicitly assumed model. This does not establish complete upstream schedule coverage or equal trajectory accuracy for every vehicle.

## Inputs and priority

A manual import overrides automatic paths. A compatible optional Flight Club API key enables the documented mission-simulation reader; exact launch UUID, coordinate frame, units and thrust state are checked, and separate stages are not joined. Authenticated retrieval remains unverified without a key.

Otherwise the worker matches available Next Spaceflight mission direction facts, Space Jellyfish Predictor heading metadata, and explicitly stated azimuth/direction from linked recognized agency/operator pages. Names, date and available pad position constrain matching. Conflicting headings remain alternatives instead of being averaged. Third-party times do not overwrite the launch schedule. The Jellyfish metadata endpoint is undocumented and may change; its prediction images/output and private model are not copied.

Historical altitude, derived downrange and event timings come from the public shahar603/Telemetry-Data archive. Falcon 9 mission-class selection now distinguishes station/crew/CRS, transfer-orbit and general flights. Falcon Heavy has a separate historical analogue. Catalogue candidates are not assumed usable: files, units, monotonic time and stage events must validate before a profile is applied. A rotated prior ascent remains a historical analogue, not the current flight's telemetry.

The October 2 audit found that the archive's CRS-8 catalogue entry points to `analysed2.json`, while the directory contains `analysed.json`. Downrange corrects only that exact verified link. The directory also contains DM-1 data, but that entry is absent from the catalogue and its event file lacks first upper-stage cutoff. It is not silently promoted into a complete operational profile. The archive fix does not alter the upstream repository.

Source catalogue: https://github.com/shahar603/Telemetry-Data/blob/master/Laucnhes.json
CRS-8 directory: https://github.com/shahar603/Telemetry-Data/tree/master/SpaceX%20CRS-8/JSON
DM-1 events: https://github.com/shahar603/Telemetry-Data/blob/master/DM-1/JSON/events.json

## Freshness and errors

Actual HTTP cache fetch timestamps and content digests are stored with acquired direction evidence. A new research attempt is not represented as a new fetch. Directions and mission simulations have independent expiry times; fallback after a source failure does not extend those component deadlines. Schedule changes request another check; large date changes invalidate stale matches. Payload/orbit changes also change the research identity. One malformed record is isolated instead of aborting research for all launches.

Sources & health distinguishes available services from matched per-mission data. Viewing briefs show whether the actual model uses a mission path, published direction plus historical ascent, published direction plus generic ascent, an orbital/site prior, or a broad direction guess. Missing or stale evidence is not proof a launch cannot be seen.

## Bounded network use

Launch Library snapshots follow pagination within the persisted local request budget; incomplete snapshots retain existing records. The acquisition worker handles up to twelve due missions per cycle, uses approved HTTPS hosts, robots checks, response-size limits, caching and persisted backoff. Empty schedules do not trigger research fetches. Source reads are separate from launch-schedule and notification tasks. Observer coordinates are not sent to trajectory sources. Weather and geocoding separately send rounded coordinates or the entered search text to Open-Meteo.

## Limits and terms

Comprehensive aviation/maritime hazard-notice/PDF ingestion, non-Falcon historical coverage, line-of-sight weather, brightness calibration, plume evolution and universal later-burn/daylight coverage remain unfinished. Fallback engineering envelopes can yield false positives and false negatives. Weather is contextual and does not gate notifications. Broad direction estimates require additional opt-in for alerts.

Provider/API terms: https://thespacedevs.com/llapi ; https://nextspaceflight.com/api_access/ ; https://jellyfish.johnkrausphotos.com/ ; https://api.flightclub.io/swagger-ui/index.html . The MIT application license does not replace source-data/API rights. Review provider terms before a public or commercial deployment.
