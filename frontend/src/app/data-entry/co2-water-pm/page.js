'use client';

import TechnoExtractedParams from '@/components/TechnoExtractedParams';

const PARAM_ROWS = [
  { key: 'sp_co2_emission', label: 'Sp. CO2 Emission', unit: 'T/tcs' },
  { key: 'sp_water_consumption', label: 'Sp. Water Consumption', unit: 'm³/tcs' },
  { key: 'sp_pm_emission', label: 'Sp. PM Emission', unit: 'kg/tcs' },
];

export default function Co2WaterPmPage() {
  return (
    <TechnoExtractedParams
      title="CO2 / Water / PM"
      description="Specific CO2 emission, water consumption and PM emission across all 5 plants."
      paramRows={PARAM_ROWS}
    />
  );
}
