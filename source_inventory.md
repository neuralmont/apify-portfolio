# Source inventory and runtime verification plan (checked 2026-10-06)

| City | Official dataset | Endpoint | Date field used | Update / scope evidence |
|---|---|---|---|---|
| Chicago | [Building Permits](https://data.cityofchicago.org/Buildings/Building-Permits/ydr8-5enu) (`ydr8-5enu`) | `https://data.cityofchicago.org/resource/ydr8-5enu.json` | `issue_date` | Portal metadata says permits from 2006-present and updated daily. |
| Seattle | [Building Permits](https://data.seattle.gov/d/76t5-zqzr) (`76t5-zqzr`) | `https://data.seattle.gov/resource/76t5-zqzr.json` | `issueddate` | [Data.gov catalog](https://catalog.data.gov/dataset/building-permits) confirms the current official `data.seattle.gov` dataset and says records are issued or in progress. |
| Austin | [Issued Construction Permits](https://data.austintexas.gov/Building-and-Development/Issued-Construction-Permits/3syk-w9eu) (`3syk-w9eu`) | `https://data.austintexas.gov/resource/3syk-w9eu.json` | `issue_date` | Official catalog record identifies this as Issued Construction Permits; the quarterly GIS dataset was not substituted. |

All three are public Socrata resources. Portal metadata exposes schema and row access through the `/api/views/{id}` and `/resource/{id}.json` endpoints. Chicago’s metadata labels the license “See Terms of Use”; Seattle’s Data.gov record labels access public; Austin’s portal provides the public dataset page. The probe does not bypass authentication or use an app token.

The exact schema is fetched by the portal at runtime before any sample query. Required mappings are fatal if absent; optional mappings are reported in the per-city manifest and remain null. The checked-in mapping table is a configuration to validate, not a claim that every optional field was verified in this blocked environment. In particular, Chicago component address and numbered contractor-role fields, Seattle’s `contractorcompanyname`, and Austin’s `permit_location`, `est_project_cost`, `status_current`, and classification field require live metadata confirmation. Raw sampled records are preserved for that audit. A schema mismatch is reported as an extraction error rather than silently guessed.
