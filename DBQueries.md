

PS D:\opr-mis1> sqlite3 D:\opr-mis1\backend\mis_reports.db .tables;


PS D:\opr-mis1> sqlite3 D:\opr-mis1\backend\mis_reports.db ".schema production_table;"




sqlite3 D:\opr-mis1\backend\mis_reports.db "SELECT * FROM production_table WHERE report_month='2026-04' AND plant_name='ASP';"

git rm --cached mis_reports.db
git rm --cached backend/mis_reports.db
git add .gitignore
git commit -m "Remove database files from tracking"


sqlite3 D:\opr-mis1\backend\mis_reports.db "SELECT * FROM production_table WHERE report_month in ('2025-04','2025-05','2026-04','2026-05') AND plant_name='SSP';"


 sqlite3 D:\opr-mis1\backend\mis_reports.db "SELECT * FROM production_plan_table WHERE report_month='2026-04' AND plant_name='SSP';"


 Its an Group of Steel Plants of A company MIS. There are 5 integrated Steel Plant Having One or more blast furnaces, One or more SMS, Mills and other utilities. So BSP have burnaces name as BF-4, BF-6, BF-7, BF-8; SMS as SMS-2 , SMS-3, Mills as RSM, URM, MM, BRM,WRM, Plate Mill. similarly DSP have BF-2,BF-3,BF-4, SMS, WAP,MM,MSM; RSP have BF-1, BF-4,BF-5, SMS-1, SMS-2, PM, NPM, HSM-2; BSL have BF-1, BF-2, BF-3,BF-4,BF-5, SMS-1, SMS-2, HSM, CRM-1&2, CRM-3; ISP have BF-5, SMS, USM, BRM, WRM. some more unit will be added in future; So sctructure the DB and its table in such a way to make it more scalable, uniform across the plant. Blast furnace relate techno parameters are Coke rate, Nut rate, Fuel rate, BF Productivity, Blast Temp, Si in HM, S in HM, Sinter% in Burden, Pellet% In Burden, O2 % enrichment, Slag rate, etc. it will be for all furnaces and for Shop (shop mean average across the plant).In SMS ( Sp. HM consumption, Sp.Scrap Consumption, SP. TMI (addition of hm & scrap ), Nos of blows per day per converter, heat weight, Oxygen blow per t crude steel, Fe-Mn, Si-Mn, Fe-Si, lime consumption, Tap to Tap time, Cast Sequence, Conerter AV%, Converter Ut%, Caster av%, Caster ut%, caster yield, Converter yield, refractory consumption etc), Mills ( Av%, ut%,Rolling Rate,Sp. Power consumption,Heat comsumption, Yield). Coke making (BF Yield, Dry Coal charge per oven, Coke Oven Gas Yield,Crude Benzol Yield,Ammonium Shulphate Yield,Coke Screen Loss, M-10, M-40, CSR etc) Sinter(M/c productivity, Sinter return%, Fe% in sinter). Some more general Techno such as Sp. Water comsumption per ton CS, Sp. Energy Consumption per ton of CS, Sp. CO2 emission per ton of CS,Labour productivity etc are plant specific. 

