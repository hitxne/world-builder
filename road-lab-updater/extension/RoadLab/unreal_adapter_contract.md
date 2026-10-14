# Engine-neutral adapter contract — design only

The current v2 JSON stores editable fixture/network parameters, stable IDs, meters, ownership modes and revision. Generated meshes are outputs, never the sole source. A production graph must unify these fixture-specific models into reusable road/lane/junction/lot records.

Proposed command envelope:

    {"protocol_version":1,"request_id":"uuid","expected_revision":7,"operation":"set_endpoint","entity_id":"endpoint-N-A","payload":{"station_m":28}}

Operations: get_graph, replace_graph, set_road_profile, set_approach, set_corner_radius, set_endpoint, set_median_end, set_lane_connection, set_parking_outline, add_planter, validate, regenerate, export_geometry. Commands must reject stale expected revisions and preserve manual fields. Return new revision, affected entity IDs and structured diagnostics. Do not auto-connect different elevation levels.

Exchange: versioned JSON plus separate mesh buffers (positions/normals/UV/material IDs), editable alignment curves and lane guides. Coordinates need an explicit Blender-to-Unreal axis/unit transform: meters to centimeters plus documented handedness conversion. Assetto Corsa conversion remains separate from the master. No live Unreal adapter, Unreal HUD, KN5 exporter, GTA V exporter or CarX Street exporter exists in this package.
