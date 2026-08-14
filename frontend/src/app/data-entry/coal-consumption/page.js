'use client';

import TechnoExtractedParams from '@/components/TechnoExtractedParams';

const PARAM_ROWS = [
  { key: 'indigenous_pcc', label: 'Indigenous PCC', unit: "'000 T" },
  { key: 'indigenous_mcc', label: 'Indigenous MCC', unit: "'000 T" },
  { key: 'imported_hard_coal', label: 'Imported Hard Coal', unit: "'000 T" },
  { key: 'imported_soft_coal', label: 'Imported Soft Coal', unit: "'000 T" },
];

export default function CoalConsumptionPage() {
  return (
    <TechnoExtractedParams
      title="Coal Consumption"
      description="Indigenous and imported coal consumption across all 5 plants."
      paramRows={PARAM_ROWS}
    />
  );
}
