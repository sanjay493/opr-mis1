// Shared parameter/unit/label registry for techno_data manual-entry UIs.
// Single source of truth for techno-manual/page.js and techno-correction/page.js —
// duplicating the label map (~150 lines) across pages would drift silently.

export const PLANTS = ['BSP', 'DSP', 'RSP', 'BSL', 'ISP', 'SAIL'];

// ── Unit → Area grouping ──────────────────────────────────────────────────────
export const AREA_ORDER = ['Blast Furnace', 'SMS', 'Rolling Mills', 'Coke Ovens', 'Sinter Plant', 'Coal', 'General'];

export const BF_UNITS   = new Set(['BF_Shop','BF-1','BF-2','BF-3','BF-4','BF-5','BF-6','BF-7','BF-8']);
export const SMS_UNITS  = new Set(['SMS','SMS-1','SMS-2','SMS-3','SMS-I','SMS-II']);
export const MILL_UNITS = new Set([
  'PM','RSM','MM','URM','WRM','BRM','HSM','HSM-1','HSM-2','NPM','CRM','CRM 1&2','CRM 3',
  'ERW','SSM','SWP','BM','USM','MSM','Merchant Mill','Wheel Plant','Axle Plant',
]);
export const COKE_UNITS = new Set(['COB','COB-old','COB-new','Coke Ovens']);
export const SINT_UNITS = new Set(['SP','SP-1','SP-2','SP-3','Sinter']);
// Written by the Coal OMI upload (backend/api_coal_omi_techno.py). Their own
// area so they don't fall into General and pick up General's field list.
export const COAL_UNITS = new Set(['Coal_Consumption','Coal_Receipt_Stock']);

export function unitArea(u) {
  if (BF_UNITS.has(u))   return 'Blast Furnace';
  if (SMS_UNITS.has(u))  return 'SMS';
  if (MILL_UNITS.has(u)) return 'Rolling Mills';
  if (COKE_UNITS.has(u)) return 'Coke Ovens';
  if (SINT_UNITS.has(u)) return 'Sinter Plant';
  if (COAL_UNITS.has(u)) return 'Coal';
  return 'General';
}

export const BF_ORDER = ['BF_Shop','BF-1','BF-2','BF-3','BF-4','BF-5','BF-6','BF-7','BF-8'];

export function sortUnitsInArea(area, units) {
  if (area === 'Blast Furnace')
    return [...units].sort((a, b) => {
      const ia = BF_ORDER.indexOf(a), ib = BF_ORDER.indexOf(b);
      return (ia < 0 ? 99 : ia) - (ib < 0 ? 99 : ib);
    });
  return [...units].sort();
}

// ── Parameter templates per area ──────────────────────────────────────────────
export const PARAM_TEMPLATES = {
  'Blast Furnace': [
    // Operating rates
    'coke_rate','nut_coke_rate','cdi','fuel_rate',
    'bf_productivity',
    // HM quality
    'silicon_in_hm','sulphur_in_hm','avg_hot_metal_temperature',
    // Blast
    'hot_blast_temp','o2_enrichment','blast_moisture','blast_volume','top_pressure',
    // Burden / slag
    'slag_rate','slag_offtake','slag_mgo','slag_al2o3','slag_b2',
    'sinter_in_burden','pellet_in_burden','lump_in_burden',
    // These must match bf_benchmark_registry.py's own key names exactly —
    // the "Comparison of Performance of Large BFs of SAIL" report page
    // (page_bf_large_annexure.py) reads every one of them from BF-8/BF-5's
    // own techno_data unit, same as everything else in this template
    // (formerly the dedicated /data-entry/bf-large-manual page's own field
    // list, merged in here so there's exactly one BF entry form).
    'tfe_in_sinter','pellet_fe','lump_ore_fe','fe_in_ore',
    'furnace_availability','utilisation',
    'steam_rate_hr','eta_co','heat_load_flux','tapping_duration',
  ],
  'SMS': [
    'specific_hm_consumption',
    'specific_scrap_consumption',
    'tmi','average_heat_weight','concast_ratio','cc_ratio','yield_sms',
    'average_blows_per_day','average_lining_life','caster_yield',
    'tap_to_tap_time','converter_availability','converter_utilisation',
    'refractory_consumption_sms','refractory_consumption_red',
    'specific_refractory_consumption','specific_lpg_consumption',
    'bof_gas_yield',
    'calcined_lime_consumption','limestone_consumption',
    'si-mn','fe-si','fe-mn','oxygen_blowing',
    'calcined_dolomite_consumption',
  ],
  'Coke Ovens': [
    'gross_coke_yield','bf_coke_yield',
    'gross_coke_rate','net_coke_rate','coke_production','coking_time',
    'specific_heat_coke_ovens','specific_power_coke_ovens',
    'crude_tar_yield','crude_benzol_yield','coke_oven_gas_yield','ammonium_sulphate_yield',
    'dry_coal_charge_oven',
    'm10','m40',
    // csr_coke/cri_coke: BSL used to write these as coke_csr/coke_cri -
    // fixed at the source now (bsl_technopara_extractor.py's _COKE_KEY_NORM
    // plus a one-off migration of existing rows), matching ISP's own
    // spelling for the same concepts. m10_coke (ISP/BSP/BSL's own spelling
    // for M10) was migrated onto DSP's shorter "m10" above instead of kept
    // as its own entry.
    'csr_coke','cri_coke',
    'ash_in_coke','ash_in_coal_blend','vm_in_coal_blend',
  ],
  'Sinter Plant': [
    'sinter_production','productivity','basicity','tfe_in_sinter',
    // machine_availability/machine_utilisation/return_fines: BSL used to
    // write these under its own divergent names (sinter_m_c_availability/
    // sinter_m_c_utilization/sinter_return) - fixed at the source now
    // (bsl_technopara_extractor.py's _SINTER_KEY_NORM plus a one-off
    // migration of existing rows), so these canonical names now cover BSL
    // too instead of needing a separate divergent entry here.
    'machine_availability','machine_utilisation','return_fines',
  ],
  // Fallback only, for a mill not listed in MILL_TEMPLATES below — every
  // known mill has its own list there, since plants name the same concept
  // differently (yield / yield_total, heat_consumption / specific_heat ...).
  'Rolling Mills': ['yield','availability','utilisation','rolling_rate'],
  // Only fields a report page reads. bof_slag_utilisation, water_consumption
  // and cog/bfg/ldg_recovery were dropped (2026-10-02): no report reads
  // them and no upload writes them (BSL's techno upload alone writes
  // water_consumption), so they only ever showed as blank rows. Any stored
  // value still appears below the list as an extra row.
  'General': [
    'specific_energy_consumption','sp_power_consumption',
    'coke_screen_loss',
    'coal_to_hm',
    'sp_co2_emission','sp_water_consumption','sp_pm_emission',
    // Key Parameters page (page 5) — no other source yet, filled here
    'hm_to_pcm_sandpit_drypit',
    'capex','labour_productivity','avg_rake_detention_time','rltifr',
  ],
  // Per-unit, see COAL_TEMPLATES.
  'Coal': [],
};

// Coal units' fields, in the "Consumption of Coking Coal and CDI Coal"
// page's order (backend/page_coal_consumption.py). Coal_Receipt_Stock
// (SAIL only) has no fixed list; it shows whatever the upload stored.
export const COAL_TEMPLATES = {
  Coal_Consumption: [
    'pcc','pcc_pct','mcc','mcc_pct','indigenous_total','indigenous_total_pct',
    'hard','hard_pct','soft','soft_pct','imported_total','imported_total_pct',
    'total_coking_coal','cdi_coal',
  ],
};

// Plant-specific params appended to an area template only for that plant
export const PLANT_PARAM_EXTRAS = {
  DSP: { 'Sinter Plant': ['dsp_sp_1','dsp_sp_2'] },
};

// Rolling-mill parameters per plant and mill, in report order. These are the
// exact keys the mill report pages read — backend page_techno.py
// _TECHNO_DB_SCHEMA pages 31 (BSP), 32 (DSP), 33 (RSP), 34 (BSL), 35 (ISP) —
// so a value entered here lands where the report looks for it. Keep the two
// in sync. RSP HSM-1 / CRM aren't on page 33; their lists are the keys their
// stored data uses.
const _BSP_MILL = ['yield','availability','utilisation','rolling_rate','heat_consumption','power_consumption'];
const _DSP_MILL = ['yield','mill_availability','mill_utilisation','rolling_rate','on_ich','specific_heat','specific_power'];
const _RSP_PLATE = ['yield_prime','yield_total','average_slab_weight','availability','utilisation','rolling_rate','specific_heat_consumption','specific_power_consumption'];
const _RSP_HSM = ['yield_total','average_slab_weight','availability','utilisation','rolling_rate','average_furnace_availability','specific_heat_consumption','specific_power_consumption'];
const _RSP_BASIC = ['yield','availability','utilisation','rolling_rate'];
const _ISP_MILL = ['yield_total','availability','utilisation','rolling_rate','specific_power_consumption','specific_heat_consumption','total_gas_consumption','cbm_gas_consumption'];
export const MILL_TEMPLATES = {
  BSP: {
    PM: _BSP_MILL, RSM: _BSP_MILL, MM: _BSP_MILL, URM: _BSP_MILL, WRM: _BSP_MILL,
    BRM: ['yield','availability','utilisation','rolling_rate'],
  },
  DSP: {
    'Merchant Mill': _DSP_MILL, MSM: _DSP_MILL,
    'Wheel Plant': ['finished_wheel_over_ingot_round','forging_availability','forging_utilisation','rolling_rate','on_ich','specific_heat','specific_power'],
    'Axle Plant': ['yield_over_good_bloom','forging_availability','forging_utilisation','forging_rate','on_ich','specific_heat','specific_power'],
  },
  RSP: {
    PM: _RSP_PLATE, NPM: _RSP_PLATE,
    'HSM-1': _RSP_HSM, 'HSM-2': _RSP_HSM,
    SSM: ['yield','acid_consumption','availability','utilisation','rolling_rate'],
    SWP: _RSP_BASIC, ERW: _RSP_BASIC,
    CRM: ['pickled_coils_yield','galvanised_sheet_yield','acid_consumption','zinc_cons_incl_dross','zinc_cons_excl_dross','specific_energy_consumption'],
  },
  BSL: {
    HSM: _BSP_MILL,
    'CRM 1&2': ['yield_of_hr_coil','tm_1_utilisation','tm_2_utilisation'],
    'CRM 3': ['yield_of_hr_coil','pltcm_yield','pltcm_availability','pltcm_utilisation','spm_yield_of_cr_coil','spm_availability','spm_utilisation','specific_power_consumption'],
  },
  ISP: { BM: _ISP_MILL, USM: _ISP_MILL, WRM: _ISP_MILL },
};

// Parameters to offer for one unit. `unit` is optional — only Rolling Mills
// vary by unit (see MILL_TEMPLATES); every other area is per-area (+ any
// PLANT_PARAM_EXTRAS).
export function templateFor(area, plant, unit) {
  const millList = area === 'Rolling Mills' && unit ? MILL_TEMPLATES[plant]?.[unit] : null;
  const coalList = area === 'Coal' && unit ? (COAL_TEMPLATES[unit] || []) : null;
  const base   = millList || coalList || PARAM_TEMPLATES[area] || [];
  const extras = (PLANT_PARAM_EXTRAS[plant] || {})[area] || [];
  return [...base, ...extras];
}

// ── Known units list for "Add Unit" modal / unit pickers ──────────────────────
export const KNOWN_UNITS = [
  'BF_Shop','BF-1','BF-2','BF-3','BF-4','BF-5','BF-6','BF-7','BF-8',
  'SMS','SMS-1','SMS-2','SMS-3','SMS-I','SMS-II',
  'COB','COB-old','COB-new','Coke Ovens',
  'SP','SP-1','SP-2','SP-3','Sinter',
  'General','PM','RSM','MM','URM','WRM','BRM','HSM','HSM-1','HSM-2','NPM',
  'CRM','CRM 1&2','CRM 3','ERW','SSM','SWP','BM','USM','MSM',
  'Merchant Mill','Wheel Plant','Axle Plant',
  'Coal_Consumption',
];

// ── Label helpers ─────────────────────────────────────────────────────────────
export const _LABEL_MAP = {
  // Coal consumption (unit Coal_Consumption, '000 T and % of total coking coal)
  pcc:                                  "Indigenous PCC ('000 T)",
  pcc_pct:                              'Indigenous PCC (%)',
  mcc:                                  "Indigenous MCC ('000 T)",
  mcc_pct:                              'Indigenous MCC (%)',
  indigenous_total:                     "Indigenous Total ('000 T)",
  indigenous_total_pct:                 'Indigenous Total (%)',
  hard:                                 "Imported Hard Coal ('000 T)",
  hard_pct:                             'Imported Hard Coal (%)',
  soft:                                 "Imported Soft Coal ('000 T)",
  soft_pct:                             'Imported Soft Coal (%)',
  imported_total:                       "Imported Total ('000 T)",
  imported_total_pct:                   'Imported Total (%)',
  total_coking_coal:                    "Total Coking Coal ('000 T)",
  cdi_coal:                             "CDI Coal ('000 T)",
  // Older General copies of the coal tonnages (see FIELD_SOURCES)
  indigenous_pcc:                       "Indigenous PCC ('000 T)",
  indigenous_mcc:                       "Indigenous MCC ('000 T)",
  imported_hard_coal:                   "Imported Hard Coal ('000 T)",
  imported_soft_coal:                   "Imported Soft Coal ('000 T)",
  sp_pm_emission:                       'Sp. PM Emission (kg/tcs)',
  specific_co2_emissions:               'Sp. CO₂ Emission (old field)',
  specific_water_consumption:           'Sp. Water Consumption (old field)',
  // Coal / energy
  coal_to_hm:                           'Coal to Hot Metal',
  sp_water_consumption:                 'Sp. Water Consumption',
  water_consumption:                    'Water Consumption',
  sp_co2_emission:                      'Sp. CO₂ Emission',
  coke_screen_loss:                     'Coke Screen Loss (%)',
  specific_energy_consumption:          'Specific Energy Consumption (GCal/TCS)',
  bof_slag_utilisation:                 'BOF Slag Utilisation (%)',
  // BF quality & operating
  silicon_in_hm:                        'Silicon in HM (%)',
  sulphur_in_hm:                        'Sulphur in HM (%)',
  avg_hot_metal_temperature:            'Avg. Hot Metal Temperature (°C)',
  hot_blast_temp:                       'Hot Blast Temperature (°C)',
  o2_enrichment:                        'O₂ Enrichment (%)',
  slag_offtake:                         'Slag Offtake (%)',
  top_pressure:                         'Top Pressure (kg/cm²)',
  sinter_in_burden:                     'Sinter in Burden (%)',
  pellet_in_burden:                     'Pellet in Burden (%)',
  pellet_fe:                             'Pellet Fe (%)',
  lump_ore_fe:                           'Lump Ore Fe (%)',
  furnace_availability:                 'Furnace Availability (%)',
  // Shared by BF furnaces and rolling mills, so no "Fce" prefix.
  utilisation:                          'Utilisation (%)',
  // Rolling mills — names as on report pages 31-35. Heat/power units are
  // left off: plants report them in different units (kcal/t vs M.Cal/T).
  yield:                                'Yield (%)',
  yield_total:                          'Yield Total (%)',
  yield_prime:                          'Yield Prime (%)',
  availability:                         'Availability (%)',
  rolling_rate:                         'Rolling Rate',
  heat_consumption:                     'Sp. Heat Consumption',
  power_consumption:                    'Sp. Power Consumption (kWh/t)',
  specific_heat:                        'Sp. Heat Consumption',
  specific_power:                       'Sp. Power Consumption (kWh/t)',
  specific_heat_consumption:            'Sp. Heat Consumption',
  specific_power_consumption:           'Sp. Power Consumption (kWh/t)',
  average_slab_weight:                  'Avg Slab Weight (t)',
  average_furnace_availability:         'RH Furnace Availability (Nos/day)',
  mill_availability:                    'Availability (%)',
  mill_utilisation:                     'Utilisation (%)',
  on_ich:                               'On ICH (%)',
  forging_availability:                 'Forging Availability (%)',
  forging_utilisation:                  'Forging Utilisation (%)',
  forging_rate:                         'Forging Rate (Nos/hr)',
  finished_wheel_over_ingot_round:      'Yield — Finished Wheel / Ingot Round (%)',
  yield_over_good_bloom:                'Yield — over Good Bloom (%)',
  total_gas_consumption:                'Gas Consumption (Nm³/t)',
  cbm_gas_consumption:                  'CBM Gas Consumption (Nm³/t)',
  acid_consumption:                     'Acid Consumption (kg/t)',
  yield_of_hr_coil:                     'Yield of HR Coil (%)',
  tm_1_utilisation:                     'TM-1 Utilisation (%)',
  tm_2_utilisation:                     'TM-2 Utilisation (%)',
  pltcm_yield:                          'PLTCM Yield (%)',
  pltcm_availability:                   'PLTCM Availability (%)',
  pltcm_utilisation:                    'PLTCM Utilisation (%)',
  spm_yield_of_cr_coil:                 'SPM Yield of CR Coil (%)',
  spm_availability:                     'SPM Availability (%)',
  spm_utilisation:                      'SPM Utilisation (%)',
  pickled_coils_yield:                  'Pickled Coils Yield (%)',
  galvanised_sheet_yield:               'Galvanised Sheet Yield (%)',
  zinc_cons_incl_dross:                 'Zinc Consumption incl. Dross',
  zinc_cons_excl_dross:                 'Zinc Consumption excl. Dross',
  slag_mgo:                             'Slag MgO (%)',
  slag_al2o3:                           'Slag Al2O3 (%)',
  slag_b2:                              'Slag B2 (Ratio)',
  steam_rate_hr:                        'Steam Rate (T/Hr)',
  eta_co:                               'Eta CO (%)',
  heat_load_flux:                       'Heat Load/Flux (MJ/hr)',
  tapping_duration:                     'Tapping Duration (Hrs)',
  // SMS
  specific_hm_consumption:             'Specific HM Consumption (kg/TCS)',
  specific_scrap_consumption:          'Specific Scrap Consumption (kg/TCS)',
  average_heat_weight:                  'Average Heat Weight (t)',
  average_blows_per_day:                'Average Blows per Day',
  average_lining_life:                  'Average Lining Life (Heats)',
  caster_yield:                         'Caster Yield (%)',
  tap_to_tap_time:                      'Tap-to-Tap Time (min)',
  converter_availability:               'Converter Availability (%)',
  converter_utilisation:                'Converter Utilisation (%)',
  refractory_consumption_sms:           'Refractory Consumption SMS (kg/TCS)',
  refractory_consumption_red:           'Refractory Consumption RED (kg/TCS)',
  specific_refractory_consumption:      'Specific Refractory Consumption (kg/TCS)',
  specific_lpg_consumption:             'Specific LPG Consumption',
  bof_gas_yield:                        'BOF Gas Yield (Nm³/TCS)',
  calcined_lime_consumption:            'Calcined Lime Consumption (kg/TCS)',
  limestone_consumption:                'Limestone Consumption (kg/TCS)',
  'si-mn':                               'Si-Mn Consumption (kg/t)',
  'fe-si':                               'Fe-Si Consumption (kg/t)',
  'fe-mn':                               'Fe-Mn Consumption (kg/t)',
  oxygen_blowing:                        'Oxygen Blowing (Nm³/TCS)',
  calcined_dolomite_consumption:        'Calcined Dolomite Consumption (kg/TCS)',
  // Coke Ovens
  gross_coke_yield:                     'Gross Coke Yield (%)',
  bf_coke_yield:                        'B.F. Coke Yield (%)',
  specific_heat_coke_ovens:             'Specific Heat – Coke Ovens (1000 Kcal/Kg DC)',
  specific_power_coke_ovens:            'Specific Power – Coke Ovens (KWH/T)',
  crude_tar_yield:                       'Crude Tar Yield (kg/TDC)',
  crude_benzol_yield:                    'Crude Benzol Yield (Kg/TDC)',
  coke_oven_gas_yield:                  'Coke Oven Gas Yield (Nm³/T)',
  ammonium_sulphate_yield:               'Ammonium Sulphate Yield (Kg/TDC)',
  dry_coal_charge_oven:                 'Dry Coal Charge / Oven (T)',
  dry_coal_charge_per_oven:             'Dry Coal Charge / Oven (T) — BSL',
  m10:                                  'M10 (%)',
  m40:                                  'M40 (%)',
  ash_in_coke:                          'Ash in Coke (%)',
  ash_in_coal_blend:                    'Ash in Coal Blend (%)',
  vm_in_coal_blend:                     'VM in Coal Blend (%)',
  coking_time:                          'Coking Time (Hrs)',
  // Sinter
  dsp_sp_1:                             'DSP SP-1 Productivity (T/m²/hr)',
  dsp_sp_2:                             'DSP SP-2 Productivity (T/m²/hr)',
  // Key Parameters page (page 5)
  hm_to_pcm_sandpit_drypit:             'HM Sent to PCM/Sand Pit/Dry Pit (\'000 T)',
  capex:                                'CAPEX (Rs Cr)',
  labour_productivity:                  'Labour Productivity (T/Man-yr)',
  avg_rake_detention_time:              'Avg. Rake Detention Time (Hrs)',
  rltifr:                               'RLTIFR',
  cog_recovery:                         'Recovery of COG (Nm³/T)',
  bfg_recovery:                         'Recovery of BFG (Nm³/THM)',
  ldg_recovery:                         'Recovery of LDG (Nm³/TCS)',
};

// Where each General / Coal field's value comes from, shown as a small tag
// in the manual-entry form so a pre-filled value isn't a mystery. kind:
// "upload" = written by a file upload, "manual" = typed in on another
// entry page, "old" = no longer written, kept only for older months.
const _PLANT_TECHNO = { kind: 'upload', text: 'Plant techno upload' };
const _KEY_PARAMS = { kind: 'manual', text: 'Key Parameters entry' };
const _COAL_OMI = { kind: 'upload', text: 'Coal OMI upload' };
const _OLD_COAL = { kind: 'old', text: 'Old copy · now in Coal tab' };
export const FIELD_SOURCES = {
  General: {
    specific_energy_consumption: _PLANT_TECHNO,
    sp_power_consumption:        _PLANT_TECHNO,
    coke_screen_loss:            _PLANT_TECHNO,
    coal_to_hm:                  _PLANT_TECHNO,
    specific_heat_coke_ovens:    _PLANT_TECHNO,
    sp_co2_emission:             { kind: 'upload', text: 'EMD EPI / plant techno upload' },
    sp_water_consumption:        { kind: 'upload', text: 'EMD EPI / plant techno upload' },
    sp_pm_emission:              { kind: 'upload', text: 'EMD EPI upload' },
    water_consumption:           { kind: 'upload', text: 'BSL techno upload · not in any report' },
    hm_to_pcm_sandpit_drypit:    _KEY_PARAMS,
    capex:                       _KEY_PARAMS,
    labour_productivity:         _KEY_PARAMS,
    avg_rake_detention_time:     _KEY_PARAMS,
    demurrage:                   _KEY_PARAMS,
    rltifr:                      _KEY_PARAMS,
    indigenous_pcc:              _OLD_COAL,
    indigenous_mcc:              _OLD_COAL,
    imported_hard_coal:          _OLD_COAL,
    imported_soft_coal:          _OLD_COAL,
    specific_co2_emissions:      { kind: 'old', text: 'Replaced by sp_co2_emission' },
    specific_water_consumption:  { kind: 'old', text: 'Replaced by sp_water_consumption' },
  },
  Coal: { '*': _COAL_OMI },
};
export function sourceOf(unit, key) {
  const area = FIELD_SOURCES[unitArea(unit)];
  return area?.[key] || area?.['*'] || null;
}

export function labelOf(key) {
  if (_LABEL_MAP[key]) return _LABEL_MAP[key];
  return key
    .replace(/_/g, ' ')
    .replace(/\b\w/g, c => c.toUpperCase())
    .replace(/\bBf\b/g, 'BF').replace(/\bHm\b/g, 'HM').replace(/\bCdi\b/g, 'CDI')
    .replace(/\bTmi\b/g, 'TMI').replace(/\bFe\b/g, 'Fe').replace(/\bTfe\b/g, 'TFE')
    .replace(/\bCc\b/g, 'CC').replace(/\bO2\b/g, 'O₂');
}
