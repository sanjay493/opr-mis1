// Shared parameter/unit/label registry for techno_data manual-entry UIs.
// Single source of truth for techno-manual/page.js and techno-correction/page.js —
// duplicating the label map (~150 lines) across pages would drift silently.

export const PLANTS = ['BSP', 'DSP', 'RSP', 'BSL', 'ISP', 'SAIL'];

// ── Unit → Area grouping ──────────────────────────────────────────────────────
export const AREA_ORDER = ['Blast Furnace', 'SMS', 'Rolling Mills', 'Coke Ovens', 'Sinter Plant', 'General'];

export const BF_UNITS   = new Set(['BF_Shop','BF-1','BF-2','BF-3','BF-4','BF-5','BF-6','BF-7','BF-8']);
export const SMS_UNITS  = new Set(['SMS','SMS-1','SMS-2','SMS-3','SMS-I','SMS-II']);
export const MILL_UNITS = new Set([
  'PM','RSM','MM','URM','WRM','BRM','HSM-2','NPM','CRM 1&2','CRM 3',
  'ERW','SSM','SWP','BM','USM','MSM','Merchant Mill','Wheel Plant','Axle Plant',
]);
export const COKE_UNITS = new Set(['COB','COB-old','COB-new','Coke Ovens']);
export const SINT_UNITS = new Set(['SP','SP-1','SP-2','SP-3','Sinter']);

export function unitArea(u) {
  if (BF_UNITS.has(u))   return 'Blast Furnace';
  if (SMS_UNITS.has(u))  return 'SMS';
  if (MILL_UNITS.has(u)) return 'Rolling Mills';
  if (COKE_UNITS.has(u)) return 'Coke Ovens';
  if (SINT_UNITS.has(u)) return 'Sinter Plant';
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
    'hot_blast_temp','o2_enrichment','blast_moisture','blast_volume',
    // Burden / slag
    'slag_rate','slag_offtake',
    'sinter_in_burden','pellet_in_burden','lump_in_burden',
    'tfe_in_sinter','tfe_in_pellet','tfe_in_lump','fe_in_ore',
    'furnace_availability',
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
    // m10_coke/csr_coke/cri_coke: BSL used to write these as coke_m_10/
    // coke_csr/coke_cri - fixed at the source now (bsl_technopara_extractor.py's
    // _COKE_KEY_NORM plus a one-off migration of existing rows), matching
    // ISP's own spelling for the same concepts (m10 above is DSP's separate
    // legacy spelling for the same M10 concept, left as its own entry).
    'm10_coke','csr_coke','cri_coke',
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
  'Rolling Mills': ['rolling_yield','production'],
  'General': [
    'specific_energy_consumption',
    'bof_slag_utilisation','coke_screen_loss',
    'coal_to_hm',
    'specific_water_consumption','water_consumption',
    'specific_co2_emissions',
    // Key Parameters page (page 5) — no other source yet, filled here
    'hm_to_pcm_sandpit_drypit',
    'capex','labour_productivity','avg_rake_detention_time',
    'cog_recovery','bfg_recovery','ldg_recovery',
  ],
};

// Plant-specific params appended to an area template only for that plant
export const PLANT_PARAM_EXTRAS = {
  DSP: { 'Sinter Plant': ['dsp_sp_1','dsp_sp_2'] },
};

export function templateFor(area, plant) {
  const base   = PARAM_TEMPLATES[area] || [];
  const extras = (PLANT_PARAM_EXTRAS[plant] || {})[area] || [];
  return [...base, ...extras];
}

// ── Known units list for "Add Unit" modal / unit pickers ──────────────────────
export const KNOWN_UNITS = [
  'BF_Shop','BF-1','BF-2','BF-3','BF-4','BF-5','BF-6','BF-7','BF-8',
  'SMS','SMS-1','SMS-2','SMS-3','SMS-I','SMS-II',
  'COB','COB-old','COB-new','Coke Ovens',
  'SP','SP-1','SP-2','SP-3','Sinter',
  'General','PM','RSM','MM','URM','WRM','BRM','CRM 1&2','CRM 3','MSM',
  'Merchant Mill','Wheel Plant','Axle Plant',
];

// ── Label helpers ─────────────────────────────────────────────────────────────
export const _LABEL_MAP = {
  // Coal / energy
  coal_to_hm:                           'Coal to Hot Metal',
  specific_water_consumption:           'Specific Water Consumption',
  water_consumption:                    'Water Consumption',
  specific_co2_emissions:               'Specific CO₂ Emissions',
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
  sinter_in_burden:                     'Sinter in Burden (%)',
  pellet_in_burden:                     'Pellet in Burden (%)',
  furnace_availability:                 'Furnace Availability (%)',
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
  cog_recovery:                         'Recovery of COG (Nm³/T)',
  bfg_recovery:                         'Recovery of BFG (Nm³/THM)',
  ldg_recovery:                         'Recovery of LDG (Nm³/TCS)',
};

export function labelOf(key) {
  if (_LABEL_MAP[key]) return _LABEL_MAP[key];
  return key
    .replace(/_/g, ' ')
    .replace(/\b\w/g, c => c.toUpperCase())
    .replace(/\bBf\b/g, 'BF').replace(/\bHm\b/g, 'HM').replace(/\bCdi\b/g, 'CDI')
    .replace(/\bTmi\b/g, 'TMI').replace(/\bFe\b/g, 'Fe').replace(/\bTfe\b/g, 'TFE')
    .replace(/\bCc\b/g, 'CC').replace(/\bO2\b/g, 'O₂');
}
