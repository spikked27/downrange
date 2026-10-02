# 0.3.2-alpha.1 — observer-local sky perspective

## Implemented

A first-person perspective panel above the existing time chart, viewed from the currently selected saved observer location. It projects the same azimuth/elevation samples onto a rectilinear camera with adjustable bearing, tilt and horizontal field of view (30–120 degrees). Bearing wrap at north and a near-zenith view are handled by unit-vector camera coordinates, not linear azimuth/elevation pixels. Pan/tilt by pointer or arrow keys; zoom via buttons or +/−; reframe the flight or follow the position marker.

The sky slider uses the existing timeline's sample interpolation. Graph taps, first/peak/last buttons, and either slider stay linked. Optional 1×/10×/30× replay stops on closing the brief or hiding the page, and never autoplays. A path guide can be hidden. Frame flight tries to fit the modeled luminous path; very wide/overhead paths can leave the finite field of view and require panning or follow mode.

Below-horizon points and paths are clipped behind a generic 0-degree horizon. A dashed line shows the user's minimum viewing elevation. The marker is enlarged and symbolic; an unassessed above-horizon position is hollow rather than advertised as visible. Path guides, generic sky shading and a flat ground strip are not the real exhaust, local weather, trees, buildings, terrain, stellar field or camera view. Real apparent plume size/brightness and AR are not implemented. The underlying trajectory model and its uncertainty are unchanged.

Assets are served from the same container, with versioned observer script/style URLs and a refreshed service-worker shell cache. No new browser permission, account setting or external service is needed. Existing time graph and source evidence remain available.

## Validation before publication

179 standalone numerical/marker-state assertions and desktop/phone component tests passed in the authoring environment. The complete GitHub suite, actual HTTP browser tests and three predecessor-image upgrade tests are configured as release gates. This record does not claim those gates have completed; check Actions until the publication results are recorded here.

## References and assumptions

Projection uses an observer east/north/up unit vector, an orthonormal camera basis, and perspective division by positive camera depth. Negative-depth rays are not projected. This follows the standard perspective-camera geometry described by the Khronos camera tutorial: https://github.khronos.org/glTF-Tutorials/gltfTutorial/gltfTutorial_016_Cameras.html . Pointer handling and playback visibility follow browser APIs: https://developer.mozilla.org/en-US/docs/Web/API/Pointer_events and https://developer.mozilla.org/en-US/docs/Web/API/Document/visibilitychange_event . These references do not establish forecast accuracy or validate our implementation; the tests check implementation behavior separately.
