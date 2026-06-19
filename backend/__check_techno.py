import sys; sys.path.insert(0, r'h:\opr-mis1\backend')
from page_techno import generate_techno, generate_summary_te_table

print('=== MAJOR page SAIL rows (2026-05) ===')
result = generate_techno('2026-05', 27)
for sec in result['sections']:
    for row in sec['rows']:
        if row['label'] == 'SAIL':
            print(f"  [{sec['label']}] SAIL: fy2={row['fy2']} fy1={row['fy1']} tgt={row['target']} months={row['months']} cply={row['cply']} cum={row['cum']} cumcply={row['cum_cply']}")

print()
print('=== Summary te_table (2026-05) ===')
for r in generate_summary_te_table('2026-05'):
    print(f"  {r['parameter']:20s} {r['unit']:12s} {r['values']}")

print('Done.')
