# TODO

## Techno-economic extraction gaps

- Some params are still not extracted: Nut Coke rate [N/C RT], O2 enrichment,
  Sinter%, Pellet% (to be calculated from Iron Ore, Sinter, and Pellet consumed).
- Extracted values for Coke rate and Fuel rate are incorrect for some plants —
  verify against source sheets.
- Fixing the param key maps touches: `bsl_mer_map.json`, `rsp_technopara_map.json`,
  `isp_technopara_map.json`, `dsp_technopara_map.json`, `page_techno.py` `_KEY_ALIASES`,
  and frontend `page.js` `PARAM_TEMPLATES` + `_LABEL_MAP`. Existing DB rows with old
  keys will need a one-time migration after the map changes.

## Done

- Cell-reference catalog: all extractor cell/row/column references merged into
  `backend/cell_reference_catalog.json` (BSP, ISP, RSP, BSL, DSP/ASP/SSP/VISL).