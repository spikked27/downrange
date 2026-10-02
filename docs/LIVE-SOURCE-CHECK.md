# Live source verification — October 2, 2026

The independent public-source adapter workflow passed in Actions run 36968346040, job 110716874453, using commit 06b5f3083a34062939ba91cc7b4fcf3035cb323a. Run: https://github.com/spikked27/downrange/actions/runs/36968346040

At approximately 05:18 UTC the test successfully retrieved and matched these real inputs for the NROL-97 launch record:

- Next Spaceflight mission page 7826: published direction 45 degrees (northeast), source nominal time 2026-10-02T03:54:00Z.
- Space Jellyfish Predictor public heading metadata: estimated direction 40.7 degrees. Its prediction for this mission was marked unsupported, and its nominal time differed from Launch Library/Next Spaceflight. Its time was not used to overwrite the schedule.
- shahar603/Telemetry-Data: Falcon Heavy Demo 1 historical webcast-derived ascent, reduced to 55 samples through first second-stage cutoff at T+512 seconds. Last selected sample altitude 178.811 km, derived downrange 1541.28 km.

The geometry test combined the published northeast direction with this historical ascent analogue and tested nine angular/altitude/time variations for an observer at 40.7 N, 73.35 W with a five-degree minimum elevation. All nine produced above-horizon powered-night geometry; none produced a sunlit-plume interval at the supplied nominal time. This verifies source matching, units, profile conversion and geometric calculation, NOT actual sighting, brightness, weather or forecast accuracy. The profile is from a different mission and remains an estimate when reused.

A separate complete local application working copy passes 131 automated tests. The whole application integration has NOT been committed to this work branch or published as a new container image because a tool upload operation was blocked. This workflow does not change the running Unraid installation, verify authenticated Flight Club access, or establish that 0.3.0-alpha.1 is available in GHCR.
