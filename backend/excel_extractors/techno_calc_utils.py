"""
Shared utility functions for techno parameter calculations.
Used by all plant extractors to calculate derived parameters.
"""


def calculate_burden_percentages(rows_out: list, report_month: str, plant_name: str = ""):
    """
    Calculate Sinter % in Burden and Pellet % in Burden from consumption values.

    ONLY calculates if these percentages aren't already extracted.
    (PDF extraction has columns 12-13 for these percentages, so skip calculation for PDFs)

    For each furnace/shop:
      - Find Iron Ore Consumption (T)
      - Find Sinter Consumption (T)
      - Find Pellet Consumption (T)
      - Find Scrap Consumption (T)
      - Total Burden = Iron Ore + Sinter + Pellet + Scrap
      - Sinter % = (Sinter / Total Burden) × 100
      - Pellet % = (Pellet / Total Burden) × 100

    Args:
        rows_out: List of extracted rows (modified in place)
        report_month: Report month in YYYY-MM format
        plant_name: Plant name (BSL, BSP, DSP, RSP, ISP) for logging

    Returns:
        Number of calculated burden percentage rows added
    """
    # Check if Sinter/Pellet % in Burden are already extracted (from PDF)
    # If they exist, don't calculate - they're already authoritative
    existing_params = {row.get('section') for row in rows_out if row.get('status') == 'ok'}

    if 'Sinter in Burden' in existing_params or 'Pellet in Burden' in existing_params:
        # Percentages already extracted from PDF, skip calculation
        return 0

    # Group consumption data by furnace/plant label
    furnace_data = {}

    for row in rows_out:
        if row.get('status') != 'ok' or row.get('actual') is None:
            continue

        plant_label = row.get('parameter', '')  # e.g., "BSL BF-1", "BSP", "RSP BF-2"
        if not plant_label:
            continue

        # Extract consumption values (looking for specific section names)
        section = row.get('section', '')
        unit = row.get('unit', '')
        value = row['actual']

        # Only process consumption data in tonnes (T)
        if unit != 'T':
            continue

        if plant_label not in furnace_data:
            furnace_data[plant_label] = {}

        if 'Iron Ore' in section or 'Ore Consum' in section:
            furnace_data[plant_label]['iron_ore'] = value
        elif 'Sinter' in section and 'Consumption' in section:
            furnace_data[plant_label]['sinter'] = value
        elif 'Pellet' in section and 'Consumption' in section:
            furnace_data[plant_label]['pellet'] = value
        elif 'Scrap' in section or 'BF Scrap' in section:
            furnace_data[plant_label]['scrap'] = value

    # Calculate and add percentage rows
    added_count = 0
    sort_idx = 200  # Use high sort order for calculated items

    for plant_label, data in furnace_data.items():
        # Only calculate if we have sinter and pellet values
        if 'sinter' not in data or 'pellet' not in data:
            continue

        # Calculate total burden (all materials)
        iron_ore = data.get('iron_ore', 0)
        sinter = data.get('sinter', 0)
        pellet = data.get('pellet', 0)
        scrap = data.get('scrap', 0)

        total_burden = iron_ore + sinter + pellet + scrap

        if total_burden <= 0:
            print(f"DEBUG: {plant_name} {plant_label} - Invalid total burden: {total_burden}")
            continue  # Cannot calculate percentages if total is zero or negative

        # Calculate percentages
        sinter_pct = round((sinter / total_burden) * 100, 2)
        pellet_pct = round((pellet / total_burden) * 100, 2)

        # Validate calculated percentages (should be 0-100)
        if sinter_pct < 0 or sinter_pct > 100 or pellet_pct < 0 or pellet_pct > 100:
            print(f"DEBUG: {plant_name} {plant_label} - Invalid percentages calculated:")
            print(f"  Iron Ore: {iron_ore}, Sinter: {sinter}, Pellet: {pellet}, Scrap: {scrap}")
            print(f"  Total Burden: {total_burden}")
            print(f"  Sinter %: {sinter_pct}, Pellet %: {pellet_pct}")
            # Still add them but with a note
            pass

        # Add Sinter % in Burden row
        rows_out.append({
            'group_code': 'IRON_MAKING',
            'section': 'Sinter in Burden',
            'parameter': plant_label,
            'unit': '%',
            'actual': sinter_pct,
            'cum_actual': sinter_pct,  # Percentage is same for month and cumulative
            'sort_order': sort_idx,
            'source_priority': 4,  # Calculated value (lower priority than extracted)
            'cell': f'Calculated: Sinter / (Iron Ore + Sinter + Pellet + Scrap) × 100',
            'file_label': f'Sinter % in Burden ({plant_label})',
            'plant': plant_name,
            'month': report_month,
            'found_via': f'{plant_name} {plant_label} Burden calculation',
            'status': 'ok',
        })
        added_count += 1

        # Add Pellet % in Burden row
        rows_out.append({
            'group_code': 'IRON_MAKING',
            'section': 'Pellet in Burden',
            'parameter': plant_label,
            'unit': '%',
            'actual': pellet_pct,
            'cum_actual': pellet_pct,
            'sort_order': sort_idx + 10,
            'source_priority': 4,  # Calculated value (lower priority than extracted)
            'cell': f'Calculated: Pellet / (Iron Ore + Sinter + Pellet + Scrap) × 100',
            'file_label': f'Pellet % in Burden ({plant_label})',
            'plant': plant_name,
            'month': report_month,
            'found_via': f'{plant_name} {plant_label} Burden calculation',
            'status': 'ok',
        })
        added_count += 1

        sort_idx += 20

    return added_count
