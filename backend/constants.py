ALL_PLANTS = ['BSP', 'DSP', 'RSP', 'BSL', 'ISP', 'ASP', 'SSP', 'VISL']
FIVE_PLANTS = ['BSP', 'DSP', 'RSP', 'BSL', 'ISP']
FIVE_PLANTS_VISL = ['BSP', 'DSP', 'RSP', 'BSL', 'ISP', 'VISL']

# Each gated write route (see main.py's EditorAdminGateMiddleware) belongs to
# exactly one "module" — the unit an admin restricts an editor to via
# /admin/users. `is_delete` routes are additionally gated by the user's
# global can_delete flag, independent of module access. Entries are
# (method, path_template, is_delete). Lives here (not in main.py) so
# api_admin.py can import it without a circular import.
PAGE_MODULES = {
    "techno": {
        "label": "Techno Data Entry",
        "routes": [
            ("POST", "/api/bsp-techno/insert", False),
            ("POST", "/api/bsp-techno/extract/techno", False),
            ("POST", "/api/bsp-techno/extract/oisco", False),
            ("POST", "/api/dsp-techno/extract", False),
            ("POST", "/api/isp-techno/extract", False),
            ("POST", "/api/mcr-techno/cumulative-all", False),
            ("POST", "/api/mcr-techno/insert", False),
            ("POST", "/api/rsp-techno/insert", False),
            ("POST", "/api/rsp-techno/extract", False),
            ("POST", "/api/coal-co2/insert", False),
            ("POST", "/api/techno/manual/save", False),
            ("POST", "/api/techno/manual/sail/calculate", False),
            ("POST", "/api/techno/extract", False),
            ("POST", "/api/techno/insert", False),
            ("POST", "/api/techno/insert-months", False),
            ("POST", "/api/bsl-bf-techno/save", False),
            ("POST", "/api/techno-entries", False),
            ("POST", "/api/techno-targets", False),
            ("POST", "/api/techno-manual-save", False),
            ("POST", "/api/techno-plan", False),
            ("POST", "/api/techno-plant-plan", False),
            ("POST", "/api/sail-techno-plan", False),
            ("POST", "/api/techno-calculate-sail-actuals", False),
            ("POST", "/api/techno-sail-targets", False),
            ("POST", "/api/techno-recalculate-sail", False),
            ("POST", "/api/techno-plant-targets", False),
            ("POST", "/api/techno-page-targets", False),
            ("POST", "/api/techno-sms-targets", False),
            ("POST", "/api/techno-recalculate-sail-weighted", False),
        ],
    },
    "production": {
        "label": "Production Reports",
        "routes": [
            ("POST", "/api/data", False),
            ("POST", "/api/upload-excel", False),
            ("POST", "/api/upload-excel-plan", False),
            ("POST", "/api/confirm-plan", False),
            ("POST", "/api/confirm-extraction", False),
            ("POST", "/api/save-item-alias", False),
            ("POST", "/api/production-entry", False),
            ("POST", "/api/legacy-sms-crude/confirm", False),
        ],
    },
    "special_steel": {
        "label": "Special Steel",
        "routes": [
            ("POST", "/api/special-steel-manual/save", False),
            ("POST", "/api/special-steel-abp", False),
            ("POST", "/api/special-steel/grade-clubs", False),
            ("DELETE", "/api/special-steel/grade-clubs", True),
        ],
    },
    "ipt": {
        "label": "IPT",
        "routes": [
            ("POST", "/api/ipt-entry", False),
            ("POST", "/api/ipt-delete", True),
        ],
    },
    "capital_repair": {
        "label": "Capital Repair",
        "routes": [
            ("POST", "/api/capital-repair-entry", False),
        ],
    },
    "conversion_stock": {
        "label": "Conversion & Stock",
        "routes": [
            ("POST", "/api/conversion-entry", False),
            ("POST", "/api/stock-entry", False),
        ],
    },
    "todo": {
        "label": "To-Do",
        "routes": [
            ("POST", "/api/todo/add", False),
            ("POST", "/api/todo/{job_id}/update", False),
            ("POST", "/api/todo/{job_id}/complete", False),
            ("POST", "/api/todo/{job_id}/reopen", False),
            ("POST", "/api/todo/{job_id}/delete", True),
        ],
    },
    "worklog": {
        "label": "Worklog",
        "routes": [
            ("POST", "/api/worklog/add", False),
            ("POST", "/api/worklog/{entry_id}/update", False),
            ("POST", "/api/worklog/{entry_id}/delete", True),
        ],
    },
    "bf_benchmark": {
        "label": "BF Benchmarking",
        "routes": [
            ("POST", "/api/bf-benchmark/external-bfs", False),
            ("PATCH", "/api/bf-benchmark/external-bfs/{bf_id}", False),
            ("POST", "/api/bf-benchmark/external-bfs/{bf_id}/entry", False),
            ("PATCH", "/api/bf-benchmark/sail-meta", False),
        ],
    },
}
