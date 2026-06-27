import json

from extractor import TechnoExtractor

extractor = TechnoExtractor("upload/technoparaMay2026.xlsx")
records = extractor.extract()

print("\n" + "="*90)
print(f"TOTAL RECORDS EXTRACTED : {len(records)}")
print("="*90)

for i, rec in enumerate(records, 1):
    print(f"\n[{i:02d}] PLANT : {rec['plant']}")
    print(f"     UNIT    : {rec['unit']}")
    print(f"     REPORT MONTH : {rec['report_month']}")
    print("-" * 70)

    techno = rec["techno_json"]

    print("MONTH DATA:")
    for param, value in techno["month"].items():
        print(f"   {param:35} : {value}")

    print("\nTILL MONTH (CUMULATIVE) DATA:")
    for param, value in techno["till_month"].items():
        print(f"   {param:35} : {value}")

    if i < len(records):
        print("\n" + "-"*90)