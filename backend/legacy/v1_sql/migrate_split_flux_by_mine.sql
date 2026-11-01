-- One-time migration (2026-10-17): flux is now entered per mine. The old
-- SAIL-level "Limestone" rows become KTR Limestone (a new "Nandani
-- Limestone" item is entered alongside it) and "Dolomite" becomes Hirri
-- Dolomite, in both flux_prod and flux_despatch, for every month.
-- Mines Production Performance shows the three items separately; SAIL Mines
-- Production & Despatch Performance still shows Limestone (KTR + Nandani)
-- and Dolomite (Hirri) — see page_sail_mines.py's _FLUX_SOURCES.
-- Runs unchanged on MySQL and SQLite.

UPDATE sail_mines_monthly SET item = 'KTR Limestone'
 WHERE section IN ('flux_prod', 'flux_despatch') AND item = 'Limestone';

UPDATE sail_mines_monthly SET item = 'Hirri Dolomite'
 WHERE section IN ('flux_prod', 'flux_despatch') AND item = 'Dolomite';
