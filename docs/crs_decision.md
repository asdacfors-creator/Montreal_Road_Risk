# Canonical Working Coordinate Reference System (CRS) Decision

This document details the evaluation, final selection, and implementation parameters for the canonical working coordinate reference system (CRS) used across Phase 3 and all subsequent modeling phases of the Montreal Road Risk project.

---

## 1. Candidate CRSs Evaluated

| CRS Identifier | Name | Projection Type | Units | Advantages | Disadvantages |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **EPSG:4326** | WGS 84 | Geographic (2D) | Degrees | Universal coordinate format; no projection distortion. | Distance calculations (meters) are complex and computationally expensive; inaccurate buffers. |
| **EPSG:2950** | NAD83(CSRS) / MTM zone 8 | Projected | Meters | Highly precise for Quebec/Montreal region. | Some packages/systems have limited support for CSRS datum shifts. |
| **EPSG:32188** | NAD83 / MTM zone 8 | Projected | Meters | Standard Quebec projection; native to Ville de Montréal administrative boundaries; uses meters. | Requires reprojecting WGS84 and custom CRS sources. |

---

## 2. Final Selection and Rationale

The project has established **`EPSG:32188` (NAD83 / MTM zone 8)** as the canonical working coordinate reference system.

### Rationale:

1. **Native Alignment**: The official Ville de Montréal administrative boundaries are published natively in EPSG:32188. Selecting it as the working CRS avoids any reprojection error on boundary shapes.
2. **Measurement Consistency**: All spatial joining, distance calculations, and buffer generation (e.g., segment proximity to pothole repairs or assets) require coordinates in meters. EPSG:32188 uses meters natively.
3. **Regional Standard**: Recommended by the Ville de Montréal open data portal for local GIS operations.

---

## 3. Projection & Datum Parameters

The detailed projection and ellipsoid properties of `EPSG:32188` are:

- **Projection**: Modified Transverse Mercator (MTM) Zone 8
- **Datum**: North American Datum 1983 (NAD83)
- **Ellipsoid**: GRS 1980 (Geodetic Reference System 1980)
- **Prime Meridian**: Greenwich
- **Bounding coordinates for MTM Zone 8**:
  - Latitude bounds: `[45.0, 46.5]`
  - Longitude bounds: `[-74.8, -73.0]`
  - Projected X bounds: `[269000.0, 315000.0]`
  - Projected Y bounds: `[5029000.0, 5064000.0]`

---

## 4. Implementation Details

To prevent coordinate axis swaps (e.g. Latitude/Longitude vs X/Y in different GIS toolchains), all pyproj transformers and GeoPandas operations are configured with:

```python
always_xy=True
```

This guarantees that:
- For geographic coordinate systems, coordinates are always read and written as `(longitude, latitude)`.
- For projected coordinate systems, coordinates are always read and written as `(Easting/X, Northing/Y)`.

---

## 5. Source Overrides and Declarations

The following overrides are declared in `config/spatial_preprocessing.json` to resolve CRS ambiguities:

*   **Montréal Géobase**: Interpreted as `EPSG:4326` (geographic WGS84) from raw representation and reprojected to `EPSG:32188`.
*   **Pothole Repairs 2021**: Declared natively with a custom/unregistered SRS code (`100000`) in WGS84 coordinates. Overridden and interpreted as `EPSG:4326`, then reprojected to `EPSG:32188`.
*   **Pothole Repairs 2022–2025**: Natively declared in `EPSG:2950` (NAD83(CSRS) / MTM zone 8). Reprojected to `EPSG:32188`.
*   **Pavement Condition 2020**: Interpreted as `EPSG:4326` from GeoJSON properties, then reprojected.
*   **Pavement Condition 2022–2024**: Natively declared in `EPSG:2950`. Reprojected to `EPSG:32188`.
