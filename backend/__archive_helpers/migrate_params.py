"""One-time DB migration: param master restructuring per user request 2026-06-21.

Changes:
 1. BF# -> BF- (BSP CDI + DSP CDI per-furnace)
 2. Plant Avg -> Plant Shop in IRON_MAKING (all plants)
    'BSP Avg for CDI Fces' / 'BSP Avg' / etc. -> 'BSP Plant Shop'
    'ISP BF-5' -> 'ISP Plant Shop'
 3. DSP per-furnace params created for BF Coke Rate / Nut Coke / BF Productivity /
    Fuel Rate / Sinter / Pellet / HBT / Si in HM / S in HM / O2 Enrichment
 4. (code-side) Fuel Rate fallback = Coke + Nut Coke + CDI
 5. Blast Temperature -> HBT
 6. Screen Loss -> Coke Screen Loss  |  row_label 'BSP' -> 'BSP Plant Shop'
 7. MAJOR BOF Slag Utilisation -> COKE_SINTER; add for BSP/RSP/BSL/ISP
 8. BOF group_code -> SMS; move MAJOR Hot Metal/Scrap/TMI to SMS
    Add missing SMS params (Converter Yield, Caster, Cast Sequence, Fe-Mn/Si, Lime)
"""

import sqlite3, sys
sys.stdout.reconfigure(encoding='utf-8')

DB = 'mis_reports.db'
conn = sqlite3.connect(DB)
cur = conn.cursor()

print("=== 1. BF# -> BF- ===")
cur.execute("UPDATE techno_param_master SET row_label = REPLACE(row_label,'BF#','BF-') WHERE row_label LIKE '%BF#%'")
print(f"  {cur.rowcount} rows updated")

print("=== 2. Plant Avg -> Plant Shop (IRON_MAKING) ===")
label_map = [
    ('ISP BF-5',             'ISP Plant Shop'),
    ('BSP Avg',              'BSP Plant Shop'),
    ('DSP Avg',              'DSP Plant Shop'),
    ('RSP Avg',              'RSP Plant Shop'),
    ('BSL Avg',              'BSL Plant Shop'),
    ('ISP Avg',              'ISP Plant Shop'),
    ('BSP Avg for CDI Fces', 'BSP Plant Shop'),
    ('DSP Avg for CDI Fces', 'DSP Plant Shop'),
    ('RSP Avg for CDI Fces', 'RSP Plant Shop'),
    ('BSL Avg for CDI Fces', 'BSL Plant Shop'),
]
for old, new in label_map:
    cur.execute("UPDATE techno_param_master SET row_label=? WHERE group_code='IRON_MAKING' AND row_label=?", (new, old))
    if cur.rowcount:
        print(f"  '{old}' -> '{new}': {cur.rowcount} rows")

print("=== 3. DSP per-furnace params ===")
dsp_furnaces = [('DSP BF-2', 58), ('DSP BF-3', 59), ('DSP BF-4', 60)]
dsp_sections = [
    ('BF Coke Rate',   'Kg/THM',    49),
    ('Nut Coke Rate',  'Kg/THM',    59),
    ('BF Productivity','T/m³/day', 69),
    ('Fuel Rate',      'Kg/THM',   109),
    ('Sinter in Burden','%',       119),
    ('Pellet in Burden','%',       129),
    ('HBT',            '°C',   99),
    ('Si in HM',       '%',         79),
    ('S in HM',        '%',         89),
    ('O2 Enrichment',  '%',        149),
]
created = 0
for section, unit, base_so in dsp_sections:
    for furnace, offset in dsp_furnaces:
        cur.execute("SELECT param_id FROM techno_param_master WHERE group_code='IRON_MAKING' AND section=? AND row_label=?", (section, furnace))
        if not cur.fetchone():
            cur.execute("INSERT INTO techno_param_master(group_code,section,row_label,unit,sort_order) VALUES('IRON_MAKING',?,?,?,?)",
                        (section, furnace, unit, base_so + offset))
            created += 1
print(f"  {created} new DSP furnace params created")

print("=== 5. Blast Temperature -> HBT ===")
cur.execute("UPDATE techno_param_master SET section='HBT' WHERE group_code='IRON_MAKING' AND section='Blast Temperature'")
print(f"  {cur.rowcount} rows updated")

print("=== 6. Screen Loss -> Coke Screen Loss + Plant Shop labels ===")
for plant in ['BSP', 'DSP', 'RSP', 'BSL', 'ISP']:
    cur.execute("UPDATE techno_param_master SET section='Coke Screen Loss', row_label=? "
                "WHERE group_code='IRON_MAKING' AND section='Screen Loss' AND row_label=?",
                (f'{plant} Plant Shop', plant))
    if cur.rowcount:
        print(f"  Screen Loss/{plant} -> Coke Screen Loss/{plant} Plant Shop")

print("=== 7. BOF Slag Utilisation MAJOR -> COKE_SINTER ===")
cur.execute("UPDATE techno_param_master SET group_code='COKE_SINTER', sort_order=855 WHERE param_id=735")
print(f"  MAJOR pid=735 (DSP) moved to COKE_SINTER")
for plant, so in [('BSP', 856), ('RSP', 857), ('BSL', 858), ('ISP', 859)]:
    cur.execute("SELECT param_id FROM techno_param_master WHERE group_code='COKE_SINTER' AND section='BOF Slag Utilisation' AND row_label=?", (plant,))
    if not cur.fetchone():
        cur.execute("INSERT INTO techno_param_master(group_code,section,row_label,unit,sort_order) VALUES('COKE_SINTER','BOF Slag Utilisation',?,'%',?)", (plant, so))
        print(f"  Added COKE_SINTER BOF Slag Utilisation/{plant}")

print("=== 8a. BOF -> SMS ===")
cur.execute("UPDATE techno_param_master SET group_code='SMS' WHERE group_code='BOF'")
print(f"  {cur.rowcount} BOF params renamed to SMS")

print("=== 8b. MAJOR Hot Metal / Scrap / TMI -> SMS ===")
# TMI already existed in old BOF (now SMS) for some shops — delete the sparse duplicates
# then move the complete MAJOR set across.
cur.execute("DELETE FROM techno_monthly WHERE param_id IN (SELECT param_id FROM techno_param_master WHERE group_code='SMS' AND section='TMI')")
cur.execute("DELETE FROM techno_param_master WHERE group_code='SMS' AND section='TMI'")
print(f"  Removed old BOF-era SMS/TMI rows")
for sec in ('Hot Metal Consumption', 'Scrap Consumption', 'TMI'):
    cur.execute("UPDATE techno_param_master SET group_code='SMS' WHERE group_code='MAJOR' AND section=?", (sec,))
    print(f"  MAJOR {sec}: {cur.rowcount} rows -> SMS")

print("=== 8c. Add missing SMS params ===")
# Standard SMS shops across plants
sms_shops = [
    ('BSP SMS-2', 10), ('BSP SMS-3', 11),
    ('DSP SMS',   20),
    ('RSP SMS-1', 30), ('RSP SMS-2', 31),
    ('BSL SMS-1', 40), ('BSL SMS-2', 41),
    ('ISP SMS',   50),
]
new_sms_params = [
    # (section, unit, base_sort_order)
    ('Converter Yield',      '%',       200),
    ('Caster Availability',  '%',       210),
    ('Caster Utilisation',   '%',       220),
    ('Caster Yield',         '%',       230),
    ('Avg Cast Sequence',    'Heats',   240),
    ('Fe-Mn Consumption',    'Kg/TCS',  250),
    ('Fe-Si Consumption',    'Kg/TCS',  260),
    ('Si-Mn Consumption',    'Kg/TCS',  270),
    ('Lime Consumption',     'Kg/TCS',  280),
    ('LD Gas Recovery',      'CuM/T',   290),
]
added = 0
for section, unit, base_so in new_sms_params:
    for shop, offset in sms_shops:
        cur.execute("SELECT param_id FROM techno_param_master WHERE group_code='SMS' AND section=? AND row_label=?", (section, shop))
        if not cur.fetchone():
            cur.execute("INSERT INTO techno_param_master(group_code,section,row_label,unit,sort_order) VALUES('SMS',?,?,?,?)",
                        (section, shop, unit, base_so + offset))
            added += 1
print(f"  {added} new SMS params created")

# SAIL aggregate rows for MAJOR retained params
print("=== Verify MAJOR integrity ===")
cur.execute("SELECT COUNT(*) FROM techno_param_master WHERE group_code='MAJOR'")
print(f"  MAJOR params remaining: {cur.fetchone()[0]}")
cur.execute("SELECT COUNT(*) FROM techno_param_master WHERE group_code='SMS'")
print(f"  SMS params total: {cur.fetchone()[0]}")
cur.execute("SELECT COUNT(*) FROM techno_param_master WHERE group_code='IRON_MAKING'")
print(f"  IRON_MAKING params total: {cur.fetchone()[0]}")

conn.commit()
conn.close()
print("\nMigration complete.")
