"""
Universal Parameter Naming Convention

Maps various parameter names across different plants/sources to a standard name.
This ensures consistent naming across OISCO, TechnoMay, and other extractors.
"""

# Universal parameter mapping
# Format: {source_name: universal_name}
UNIVERSAL_PARAMETER_NAMES = {
    # Coke & By-products
    "BF Coke": "Coke Rate",
    "Coke Rate": "Coke Rate",
    "BF Coke Rate": "Coke Rate",
    "Crude Tar": "Crude Tar",
    "Ammonium Sulphate": "Ammonium Sulphate",
    "Crude Benzol": "Crude Benzol",

    # Sinter Plants
    "Machine Availability": "Machine Availability",
    "Machine Utilisation": "Machine Utilisation",
    "Productivity": "Productivity",
    "Basicity": "Basicity",

    # Blast Furnace Operations
    "CDI": "CDI",
    "Sinter in Burden": "Sinter in Burden",
    "Coke Screen Loss": "Coke Screen Loss",
    "Slag Rate": "Slag Rate",
    "Nut Coke Rate": "Nut Coke Rate",
    "BF Productivity": "BF Productivity",
    "Pellet in Burden": "Pellet in Burden",
    "LD Slag Usage": "LD Slag Usage",
    "Not Dry Cast": "Not Dry Cast",

    # SMS Data
    "Converter Availability": "Converter Availability",
    "Converter Utilisation": "Converter Utilisation",
    "Tap to Tap Time": "Tap to Tap Time",
    "Average Blows/Day": "Average Blows/Day",
    "Average Heat Weight": "Average Heat Weight",
    "Avg. Lining Life": "Avg. Lining Life",
    "Fe-Mn Consumption": "Fe-Mn Consumption",
    "Fe-Si Consumption": "Fe-Si Consumption",
    "Si-Mn Consumption": "Si-Mn Consumption",

    # Utilities & Energy
    "Fuel Rate": "Fuel Rate",
    "Energy": "Energy",
    "Coal to Hot Metal": "Coal to Hot Metal",

    # Mills
    "Bar & Rod Mill": "Bar & Rod Mill",
    "Merchant Mill": "Merchant Mill",
    "Plate Mill": "Plate Mill",
    "Rail & Structural Mill": "Rail & Structural Mill",
}


def normalize_parameter_name(param_name: str) -> str:
    """
    Convert a parameter name to the universal standard name.

    Args:
        param_name: Parameter name from extractor (may contain furnace info)

    Returns:
        Standardized parameter name
    """

    if not param_name:
        return param_name

    # Remove furnace prefixes (BSP BF-4, etc.)
    clean_name = param_name.replace('BSP BF-1', '').replace('BSP BF-2', '').replace('BSP BF-3', '') \
                            .replace('BSP BF-4', '').replace('BSP BF-5', '').replace('BSP BF-6', '') \
                            .replace('BSP BF-7', '').replace('BSP BF-8', '').replace('BSP ', '')

    # Remove other plant prefixes
    for plant_code in ['DSP', 'RSP', 'BSL', 'ISP']:
        clean_name = clean_name.replace(f'{plant_code} ', '')

    clean_name = clean_name.strip()

    # Look up in mapping, return mapped or original
    return UNIVERSAL_PARAMETER_NAMES.get(clean_name, clean_name)


def denormalize_parameter_for_furnace(param_name: str, furnace: str, plant: str = '') -> str:
    """
    Create a furnace-specific parameter name.

    Args:
        param_name: Universal parameter name
        furnace: Furnace code (e.g., "BF-4")
        plant: Plant code (optional, e.g., "BSP")

    Returns:
        Furnace-specific parameter name
    """

    if not plant:
        plant = 'BSP'

    return f"{plant} {furnace} {param_name}".strip()


# Examples
if __name__ == '__main__':
    print("Parameter Name Normalization Examples:")
    print()

    test_cases = [
        "BSP BF-4",
        "BSP BF-6",
        "CDI",
        "Coke Rate",
        "BF Coke Rate",
        "Fuel Rate",
        "BF Productivity",
    ]

    for test_name in test_cases:
        normalized = normalize_parameter_name(test_name)
        print(f"'{test_name}' → '{normalized}'")

    print()
    print("Furnace-specific examples:")
    furnace_examples = [
        ("Coke Rate", "BF-4", "BSP"),
        ("BF Productivity", "BF-7", "BSP"),
        ("CDI", "BF-6", "DSP"),
    ]

    for param, furnace, plant in furnace_examples:
        denorm = denormalize_parameter_for_furnace(param, furnace, plant)
        print(f"{param} for {plant} {furnace} → '{denorm}'")
