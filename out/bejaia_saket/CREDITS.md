# Credits and licensing

- Map data © OpenStreetMap contributors, available under the Open Database License (ODbL) 1.0: https://www.openstreetmap.org/copyright . Route data and preview are derived from OSM; preserve attribution and observe ODbL obligations on redistribution.
- Algeria extract supplied by Geofabrik: https://download.geofabrik.de/africa/algeria-latest.osm.pbf (downloaded 2026-11-13 VM date). The large raw extract is intentionally not committed.
- KN5 export uses moppius/blender-assetto-corsa-tools (GPL-3.0), originally based on Thomas Hagnhofer's exporter: https://github.com/moppius/blender-assetto-corsa-tools . Addon is installed externally, not vendored here.
- Blender 3.6.23 official Linux x64 distribution: https://download.blender.org/release/Blender3.6/blender-3.6.23-linux-x64.tar.xz .

No third-party imagery, textures, or raster map tiles were used. Procedural textures are generated locally with seed 24024.

## Copernicus GLO-30 DSM

Tiles: `Copernicus_DSM_COG_10_N36_00_E004_00_DEM` and `Copernicus_DSM_COG_10_N36_00_E005_00_DEM`, from https://copernicus-dem-30m.s3.amazonaws.com/ . Exact URLs and SHA-256 checksums are recorded in `data/dem/sources.json`.

Official licensing/citation page (read 2026-11-13): https://dataspace.copernicus.eu/explore-data/data-collections/copernicus-contributing-missions/collections-description/COP-DEM . Full **Licence for Copernicus DEM instance COP-DEM-GLO-30-F Global 30m Full, Free & Open Licence for the use of the Copernicus WorldDEM-30**, including Article 6 User Obligations: https://documentation.dataspace.copernicus.eu/APIs/SentinelHub/Data/DEM/resources/license/License-COPDEM-30.pdf . The licence is also reproduced in the official [Copernicus DEM licences PDF](https://dataspace.copernicus.eu/sites/default/files/media/files/2025-06/copernicus_contributing_mission_data_access_v2_cop_dem_licenses.pdf), downloaded and read for this build.

Exact source notice from Article 6(a):

> © DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018 provided under COPERNICUS by the European Union and ESA; all rights reserved.

Exact adapted/modified-data notice from Article 6(b), applicable to this smoothed/meshed terrain:

> produced using Copernicus WorldDEM-30 © DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018 provided under COPERNICUS by the European Union and ESA; all rights reserved

Exact liability notice from Article 6(c):

> The organisations in charge of the Copernicus programme by law or by delegation do not incur any liability for any use of the Copernicus WorldDEM-30

The licence grants reproduction, distribution, communication to the general public, adaptation, modification and combination rights free of charge, worldwide without limitation in time (Articles 3–5). Subsequent distributors must preserve Article 6 obligations. This project is not endorsed by the Provider, Licensor, EU or ESA (Article 6(d)). Citation DOI: https://doi.org/10.5270/ESA-c5d3d65 .
