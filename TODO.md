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

## production_table gaps behind Annexure-4 (SAIL 8 Plants Production Trend)

- Annexure-4's FY2007-08..2025-26 figures are hardcoded overrides
  (`page_sail8_trend_annexure.py`'s `_REFERENCE_VALUES`) sourced from SAIL's
  own published PRODUCTION summary, because live `production_table` sums
  disagree on 61 of 114 cells — mostly RSP's missing `'Saleable Semis'`
  item (undercounts Semi Finished Steel almost every year), RSP/BSL's
  `'Finished Steel'` not tracked before FY2021-22, and Pig Iron/Saleable
  Semis missing entirely before FY2012-13. Full cell-by-cell list, root
  causes, and suggested fix order: `backend/docs/SAIL8_TREND_DATA_CORRECTIONS.md`.
  Once a year's DB figures are backfilled/corrected to match, remove that
  year's entry from `_REFERENCE_VALUES`.

## Done

- Cell-reference catalog: all extractor cell/row/column references merged into
  `backend/cell_reference_catalog.json` (BSP, ISP, RSP, BSL, DSP/ASP/SSP/VISL).