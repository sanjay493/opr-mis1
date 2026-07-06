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


Agent "Catalog BSL cell references" failed: Agent terminated early due to an API error: You've hit your session limit · resets 9:10am (Asia/Calcutta)
Referenced file C:\Users\sanja\.claude\jobs\07a58768\tmp\catalog_bsp_main.json
Referenced file C:\Users\sanja\.claude\jobs\07a58768\tmp\catalog_isp.json
Referenced file C:\Users\sanja\.claude\jobs\07a58768\tmp\catalog_pdf_misc.json
Referenced file C:\Users\sanja\.claude\jobs\07a58768\tmp\catalog_dsp_pdf.json
Referenced file ..\frontend\src\app\data-entry\techno-manual\page.js
You've hit your session limit · resets 9:10am (Asia/Calcutta)
/upgrade to increase your usage limit.

✻ Churned for 13m 10s

  9 tasks (7 done, 1 in progress, 1 open)
  ◼ Catalog BSL cell references
  ◻ Merge all catalogs into single JSON reference file
  ✔ Catalog BSP main cell references
  ✔ Catalog BSP oisco/plan/techno cell references
  ✔ Catalog ISP cell references
   … +4 completed