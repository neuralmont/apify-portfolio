# Source inventory (verified 2026-10-06)

| City | Official dataset | Endpoint | Date field used | Update / scope evidence |
|---|---|---|---|---|
| Chicago | [Building Permits](https://data.cityofchicago.org/Buildings/Building-Permits/ydr8-5enu) (`ydr8-5enu`) | `https://data.cityofchicago.org/resource/ydr8-5enu.json` | `issue_date` | Portal metadata says permits from 2006-present and updated daily. |
| Seattle | [Building Permits](https://data.seattle.gov/d/76t5-zqzr) (`76t5-zqzr`) | `https://data.seattle.gov/resource/76t5-zqzr.json` | `issueddate` | [Data.gov catalog](https://catalog.data.gov/dataset/building-permits) confirms the current official `data.seattle.gov` dataset and says records are issued or in progress. |
| Austin | [Issued Construction Permits](https://data.austintexas.gov/Building-and-Development/Issued-Construction-Permits/3syk-w9eu) (`3syk-w9eu`) | `https://data.austintexas.gov/resource/3syk-w9eu.json` | `issue_date` | Official catalog record identifies this as Issued Construction Permits; the quarterly GIS dataset was not substituted. |

All three are public Socrata resources. Portal metadata exposes schema and row access through the `/api/views/{id}` and `/resource/{id}.json` endpoints. Chicago’s metadata labels the license “See Terms of Use”; Seattle’s Data.gov record labels access public; Austin’s portal provides the public dataset page. The probe does not bypass authentication or use an app token.

The exact schema is fetched by the portal at runtime where needed; the normalizer preserves raw values and uses explicit aliases for known field-name differences. A schema mismatch is reported as an extraction error rather than silently guessed.
