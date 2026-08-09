-- Eligible vacant plot dropdown for the Tender Publication Workflow.
-- PostgreSQL / DBeaver. Read-only. One row per plot.

SELECT
    p.plot_id AS source_plot_id,
    p.plot_code,
    p.rr_no,
    p.main_structure_name,
    p.location,
    p.city_survey_no,
    p.city_survey_div,
    p.area AS plot_area_sqm,
    p.status AS plot_status,
    p.is_active AS plot_active,
    p.is_vacant
FROM public.plot AS p
WHERE p.is_vacant IS TRUE
ORDER BY p.plot_code NULLS LAST, p.plot_id;
