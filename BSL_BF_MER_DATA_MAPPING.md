# BSL Blast Furnace Month-End Report (MER) - Data Field Mapping

**Report:** BSL_BlastFurnace_30042026.pdf  
**Report Date:** 30/04/2026  
**Report Type:** BF PERFORMANCE & ANALYSIS REPORT

---

## SECTION 1: FURNACE TARGETS & OVERVIEW

| Field | Handle Name | Unit | Data Type | Example Value |
|-------|------------|------|-----------|----------------|
| Furnace Target BF-1 | `furnace_target_bf1` | tonnes | numeric | 108000 |
| Furnace Target BF-2 | `furnace_target_bf2` | tonnes | numeric | 141000 |
| Furnace Target BF-3 | `furnace_target_bf3` | tonnes | numeric | 0 |
| Furnace Target BF-4 | `furnace_target_bf4` | tonnes | numeric | 106000 |
| Furnace Target BF-5 | `furnace_target_bf5` | tonnes | numeric | 106000 |
| Best April Production | `best_april_production` | tonnes | numeric | 407514 |
| Last April Production | `last_april_production` | tonnes | numeric | 348271 |
| Production 25-26 | `production_fy2526` | tonnes | numeric | 4851283 |
| Coke Rate 25-26 | `coke_rate_fy2526` | kg/thm | numeric | 446 |
| Carbon Rate 25-26 | `carbon_rate_fy2526` | kg/thm | numeric | 454 |

---

## SECTION 2: PRODUCTION PERFORMANCE

### Production (All furnaces + Shop aggregate)

| Field | Handle Name | Unit | Furnaces |
|-------|------------|------|----------|
| Production - Monthly | `production_monthly_bf{1-5}` | tonnes | BF-1,2,4,5 |
| Production - Till Month | `production_till_month_bf{1-5}` | tonnes | BF-1,2,4,5 |
| Daily Rate | `daily_rate_bf{1-5}` | tonnes/day | BF-1,2,4,5 |
| Monthly Rate | `monthly_rate_bf{1-5}` | tonnes/month | BF-1,2,4,5 |
| Number of Charges | `num_charges_bf{1-5}` | count | BF-1,2,4,5 |
| Tuyer | `tuyer_bf{1-5}` | count | BF-1,2,4,5 |
| Flue Dust | `flue_dust_bf{1-5}` | tonnes | BF-1,2,4,5 |
| Total Off Blast (hours:minutes) | `total_off_blast_bf{1-5}` | hours | BF-1,2,4,5 |
| Off Blast - Less Offtake | `off_blast_less_offtake_bf{1-5}` | hours | BF-1,2,4,5 |
| Low Blast - Less Offtake | `low_blast_less_offtake_bf{1-5}` | hours | BF-1,2,4,5 |
| Low Blast Hours | `low_blast_hours_bf{1-5}` | hours | BF-1,2,4,5 |
| Hot Blast 950-1000°C | `hot_blast_950_1000_bf{1-5}` | °C | BF-1,2,4,5 |
| Record Production Daily | `record_production_daily_bf{1-5}` | tonnes | BF-1,2,4,5 |
| Record Production Monthly | `record_production_monthly_bf{1-5}` | tonnes | BF-1,2,4,5 |
| BF Productivity (W.V./24h) | `bf_productivity_bf{1-5}` | t/m³/day | BF-1,2,4,5 |

### Production Restriction
| Field | Handle Name | Unit |
|-------|------------|------|
| Furnace Target for Month | `furnace_target_month` | tonnes | 461000 |
| Target Rate | `target_rate` | - | 929 |
| Fulfillment | `fulfillment_pct` | % | 93.75 |

### SMS Production
| Field | Handle Name | Unit |
|-------|------------|------|
| SMS I - Monthly | `sms1_monthly` | tonnes | 4813.00 |
| SMS I - Till Month | `sms1_till_month` | tonnes | 109823.00 |
| SMS II - Monthly | `sms2_monthly` | tonnes | 11263.00 |
| SMS II - Till Month | `sms2_till_month` | tonnes | 306899.00 |
| Total - Monthly | `sms_total_monthly` | tonnes | 16076.00 |
| Total - Till Month | `sms_total_till_month` | tonnes | 416722.00 |

### Hot Metal Per Charge (HM/CHG)
| Field | Handle Name | Unit | Furnaces |
|-------|------------|------|----------|
| HM per Charge | `hm_per_charge_bf{1-5}` | tonnes | BF-1,2,4,5 |

---

## SECTION 3: QUALITY PARAMETERS

### Slag Analysis
| Field | Handle Name | Unit | Furnaces |
|-------|------------|------|----------|
| Slag per Charge (SLG/CHG) | `slag_per_charge_bf{1-5}` | tonnes | BF-1,2,4,5 |

### Quality Parameters Data
| Field | Handle Name | Unit | Target | Furnaces |
|-------|------------|------|--------|----------|
| Si ≤ 0.90 (%) | `si_content_pct_bf{1-5}` | % | 80% | BF-1,2,4,5 |
| S ≤ 0.045 (%) | `s_content_pct_bf{1-5}` | % | 70% | BF-1,2,4,5 |
| Slag Al2O3 | `slag_al2o3_bf{1-5}` | - | - | BF-1,2,4,5 |
| Slag MgO | `slag_mgo_bf{1-5}` | - | - | BF-1,2,4,5 |
| Slag Basicity | `slag_basicity_bf{1-5}` | - | - | BF-1,2,4,5 |
| Hot Metal Temperature ≥1450°C | `hot_metal_temp_bf{1-5}` | °C | ≥1450 | BF-1,2,4,5 |
| Coke Rate | `coke_rate_bf{1-5}` | kg/thm | 420 | BF-1,2,4,5 |
| Nut Coke Rate (N/C RT) | `nut_coke_rate_bf{1-5}` | kg/thm | - | BF-1,2,4,5 |
| CDI Rate | `cdi_rate_bf{1-5}` | kg/thm | 105 | BF-1,2,4,5 |
| Fuel Rate | `fuel_rate_bf{1-5}` | kg/thm | - | BF-1,2,4,5 |
| Carbon Rate | `carbon_rate_bf{1-5}` | kg/thm | - | BF-1,2,4,5 |
| Flue Dust Rate | `flue_dust_rate_bf{1-5}` | kg/thm | - | BF-1,2,4,5 |
| Cumulative Production | `cum_production_bf{1-5}` | tonnes | - | BF-1,2,4,5 |
| Yearly Production | `yearly_production_bf{1-5}` | tonnes | - | BF-1,2,4,5 |
| Coke Rate Fin.Yr | `coke_rate_fin_yr_bf{1-5}` | kg/thm | - | BF-1,2,4,5 |
| Coke Rate Prod.Rt | `coke_rate_prod_rate_bf{1-5}` | kg/thm | - | BF-1,2,4,5 |
| CO/CO2 Ratio | `co_co2_ratio_bf{1-5}` | - | - | BF-1,2,4,5 |

---

## SECTION 4: RAW MATERIAL CONSUMPTION

### Consumption Data (Monthly / Till Month)
| Field | Handle Name | Unit | Furnaces |
|-------|------------|------|----------|
| Coke Consumption | `coke_consumption_bf{1-5}` | tonnes | BF-1,2,4,5 |
| Iron Ore Consumption | `iron_ore_consumption_bf{1-5}` | tonnes | BF-1,2,4,5 |
| Sinter Consumption | `sinter_consumption_bf{1-5}` | tonnes | BF-1,2,4,5 |
| Scrap Consumption | `scrap_consumption_bf{1-5}` | tonnes | BF-1,2,4,5 |
| Nut Coke Consumption | `nut_coke_consumption_bf{1-5}` | tonnes | BF-1,2,4,5 |
| CDI Consumption | `cdi_consumption_bf{1-5}` | tonnes | BF-1,2,4,5 |
| Pellet Consumption | `pellet_consumption_bf{1-5}` | tonnes | BF-1,2,4,5 |
| Coke Economy | `coke_economy_bf{1-5}` | kg/thm | BF-1,2,4,5 |
| O2 Enrichment | `o2_enrichment_pct_bf{1-5}` | % | BF-1,2,4,5 |
| Slag Rate | `slag_rate_bf{1-5}` | kg/thm | BF-1,2,4,5 |

### Burden % (Calculated)
| Field | Handle Name | Unit | Furnaces |
|-------|------------|------|----------|
| Sinter % in Burden | `sinter_pct_in_burden_bf{1-5}` | % | BF-1,2,4,5 |
| Pellet % in Burden | `pellet_pct_in_burden_bf{1-5}` | % | BF-1,2,4,5 |
| Sinter Rate | `sinter_rate_bf{1-5}` | kg/thm | BF-1,2,4,5 |
| Ore Rate | `ore_rate_bf{1-5}` | kg/thm | BF-1,2,4,5 |
| C/H SGP Pou | `ch_sgp_pou_bf{1-5}` | - | BF-1,2,4,5 |

---

## SECTION 5: CAST DETAILS

### Cast Information
| Field | Handle Name | Unit | Furnaces |
|-------|------------|------|----------|
| Number of Casts | `num_casts_bf{1-5}` | count | BF-1,2,4,5 |
| N/Dry No. | `n_dry_num_bf{1-5}` | count | BF-1,2,4,5 |
| N/Dry Due To M/L | `n_dry_m_l_bf{1-5}` | count | BF-1,2,4,5 |
| N/Dry Due To Other | `n_dry_other_bf{1-5}` | count | BF-1,2,4,5 |
| TLC No. | `tlc_num_bf{1-5}` | count | BF-1,2,4,5 |
| TLC AVG | `tlc_avg_bf{1-5}` | - | BF-1,2,4,5 |
| Cast on Schedule No. | `cast_on_schedule_num_bf{1-5}` | count | BF-1,2,4,5 |
| Cast on Schedule % | `cast_on_schedule_pct_bf{1-5}` | % | BF-1,2,4,5 |
| Average Tapping Filling | `avg_tapping_filling_bf{1-5}` | - | BF-1,2,4,5 |
| Tapping Speed | `tapping_speed_bf{1-5}` | - | BF-1,2,4,5 |
| Cast Duration % | `cast_duration_pct_bf{1-5}` | % | BF-1,2,4,5 |

### Hot Metal Distribution
| Field | Handle Name | Unit | Furnaces |
|-------|------------|------|----------|
| P.C.M. Hot Metal Distribution | `pcm_hot_metal_dist_bf{1-5}` | tonnes | BF-1,2,4,5 |
| Production on Hot Metal | `production_on_hm_bf{1-5}` | - | BF-1,2,4,5 |
| Blow-in Lining After C/R | `blow_in_after_cr_bf{1-5}` | - | BF-1,2,4,5 |

### Cast House Details
| Field | Handle Name | Unit |
|-------|------------|------|
| Mixer Cast Distribution | `mixer_cast_dist_bf{1-5}` | tonnes |
| Sand Pit | `sand_pit_bf{1-5}` | - |
| Commissioned Date | `furnace_commissioned_date_bf{1-5}` | date | Stored as strings like "08/01/2020" |

---

## SECTION 6: CAST HOUSE THROUGHPUT

| Field | Handle Name | Unit |
|-------|------------|------|
| Cast House 1 - Monthly | `cast_house_1_monthly` | tonnes |
| Cast House 1 - Till Month | `cast_house_1_till_month` | tonnes |
| Cast House 2 - Monthly | `cast_house_2_monthly` | tonnes |
| Cast House 2 - Till Month | `cast_house_2_till_month` | tonnes |
| Cast House 3 - Monthly | `cast_house_3_monthly` | tonnes |
| Cast House 3 - Till Month | `cast_house_3_till_month` | tonnes |
| Cast House 4 - Monthly | `cast_house_4_monthly` | tonnes |
| Cast House 4 - Till Month | `cast_house_4_till_month` | tonnes |
| Cast House 5 - Monthly | `cast_house_5_monthly` | tonnes |
| Cast House 5 - Till Month | `cast_house_5_till_month` | tonnes |
| Cast House 6 - Monthly | `cast_house_6_monthly` | tonnes |
| Cast House 6 - Till Month | `cast_house_6_till_month` | tonnes |
| Cast House 7 - Monthly | `cast_house_7_monthly` | tonnes |
| Cast House 7 - Till Month | `cast_house_7_till_month` | tonnes |
| Cast House 8 - Monthly | `cast_house_8_monthly` | tonnes |
| Cast House 8 - Till Month | `cast_house_8_till_month` | tonnes |
| Cast House 9 - Monthly | `cast_house_9_monthly` | tonnes |
| Cast House 9 - Till Month | `cast_house_9_till_month` | tonnes |
| Cast House 10 - Monthly | `cast_house_10_monthly` | tonnes |
| Cast House 10 - Till Month | `cast_house_10_till_month` | tonnes |

---

## SECTION 7: SLAG DETAILS

### Actual Slag
| Field | Handle Name | Unit | Furnaces |
|-------|------------|------|----------|
| Actual Slag - Monthly | `actual_slag_monthly_bf{1-5}` | tonnes | BF-1,2,4,5 |
| Actual Slag - Till Month | `actual_slag_till_month_bf{1-5}` | tonnes | BF-1,2,4,5 |

### Calculated Slag
| Field | Handle Name | Unit | Furnaces |
|-------|------------|------|----------|
| Cal Slag - Monthly | `cal_slag_monthly_bf{1-5}` | tonnes | BF-1,2,4,5 |
| Cal Slag - Till Month | `cal_slag_till_month_bf{1-5}` | tonnes | BF-1,2,4,5 |

---

## SECTION 8: MATERIAL STOCK & INVENTORY

### Iron Ore
| Field | Handle Name | Unit |
|-------|------------|------|
| Iron Ore Total | `iron_ore_total` | tonnes |
| Iron Ore Screen | `iron_ore_screen` | tonnes |

### Coke Yard
| Field | Handle Name | Unit |
|-------|------------|------|
| Coke - Receipt | `coke_receipt` | tonnes |
| Coke - Consumption | `coke_consumption_total` | tonnes |
| Coke - Stock | `coke_stock` | tonnes |

### CDI Yard
| Field | Handle Name | Unit |
|-------|------------|------|
| CDI - Receipt | `cdi_receipt` | tonnes |
| CDI - Consumption | `cdi_consumption_total` | tonnes |
| CDI - Stock | `cdi_stock` | tonnes |

### Pellet Yard
| Field | Handle Name | Unit |
|-------|------------|------|
| Pellet - Receipt | `pellet_receipt` | tonnes |
| Pellet - Consumption | `pellet_consumption_total` | tonnes |
| Pellet - Stock | `pellet_stock` | tonnes |

---

## SECTION 9: PCM DETAILS & SGP DETAILS

| Field | Handle Name | Unit |
|-------|------------|------|
| PCM - Pour | `pcm_pour` | - |
| PCM - Despatch | `pcm_despatch` | - |
| PCM - Stock | `pcm_stock` | tonnes |
| SGP - Receipt | `sgp_receipt` | - |
| SGP - Consumption | `sgp_consumption` | - |
| SGP - Stock | `sgp_stock` | tonnes |

---

## NAMING CONVENTIONS

### Pattern Rules:
1. **Furnace-specific:** `{field}_bf{1-5}` (e.g., `production_monthly_bf1`)
2. **Aggregates:** `{field}_shop` (e.g., `slag_per_charge_shop`)
3. **Monthly/Till Month:** `{field}_monthly` and `{field}_till_month`
4. **Numbers:** Concatenated as `{current}/{till_month}` (e.g., "3678/100056")

### Data Format:
- Values typically stored as pairs: `monthly/till_month`
- Percentages end with `_pct` 
- Rates end with `_rate`
- Consumption ends with `_consumption`
- Temperatures end with `_temp`

---

## TOTAL FIELDS EXTRACTED: ~150+ data points

