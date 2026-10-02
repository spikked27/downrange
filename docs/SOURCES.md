# Automatic trajectory-source acquisition

All providers in the Launch Library feed are evaluated when pad coordinates are usable. Source coverage and forecast confidence still vary. The runtime acquisition worker is enabled by default and is separate from notification scheduling.

## Source hierarchy

1. A manually imported sourced trajectory overrides automatic inputs.
2. An optional compatible Flight Club API key enables the documented v3 mission simulation reader. Exact Launch Library UUID, coordinate frames, meters-to-kilometers conversion, and thrust state are checked. Booster and upper-stage segments stay separate. Real authenticated retrieval has not been tested without a key.
3. Public departure directions from matched Next Spaceflight mission pages, estimated heading metadata from the Jellyfish site, and explicitly stated directions on linked recognized agency/operator pages constrain a corridor.
4. Available historical Falcon-family webcast ascent profiles provide altitude, derived downrange and staging analogues. The archive is shahar603/Telemetry-Data. A prior mission's profile is never claimed to be the current flight.
5. Without stronger data, orbital-plane/site priors and provider-neutral engineering envelopes produce labeled sensitivity estimates. Unknown rocket names are not rejected by a provider whitelist.

The schedule remains Launch Library's schedule; third-party heading-source times do not silently replace it. Name/date/pad matching and source disagreements are exposed. The Jellyfish heading endpoint is undocumented and may change; the application does not copy its prediction output, images or private model.

## Bounded network behavior

Paginated 90-day launch snapshots are acquired within a persistent 14-request/hour local budget. Incomplete snapshots retain previous records instead of removing unseen launches. Source pages have host allowlists, size limits, robots checks, persisted backoff and caching. Twelve due missions are processed per acquisition cycle. Credentials are sent only to the optional simulation service. No observer location is sent to trajectory sources. Weather/geocoding separately send rounded coordinates/search text to their provider.

## Remaining boundaries

No universal NOTAM/NAVWARN/PDF map parser, comprehensive non-Falcon historical library, calibrated brightness/detectability probability, line-of-sight clouds, plume evolution, or guaranteed later-burn/daylight coverage. A broad estimate is not evidence that a rocket will actually be visible. Estimated-path alerts are opt-in; low-information directions additionally require broad-candidate opt-in. Weather currently remains separate and does not gate alerts.

Sources and terms: https://thespacedevs.com/llapi ; https://nextspaceflight.com/api_access/ ; https://jellyfish.johnkrausphotos.com/ ; https://api.flightclub.io/swagger-ui/index.html ; https://github.com/shahar603/Telemetry-Data . Downrange's MIT source license does not replace third-party data/API terms. Check rights before operating a public/commercial service.
