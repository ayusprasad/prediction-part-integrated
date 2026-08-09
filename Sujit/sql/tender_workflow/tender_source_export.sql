-- Tender Publication Workflow: public-schema source exports
--
-- PostgreSQL / DBeaver compatible.  These are read-only queries.
-- Run the complete file only through scripts/export_tender_sources.py, or run
-- one named query at a time in DBeaver and export its result to the filename
-- in config/tender_export_manifest.json.
--
-- The queries deliberately export source facts and historic references only.
-- They do not manufacture approval, SoR, FSI, tax, escalation, or tender data.

-- name: tender_plot_master
WITH selected_letout AS (
    SELECT
        p.plot_id,
        lo.let_out_id,
        lo.let_out_name,
        lo.status AS letout_status,
        lo.area AS letout_recorded_area_sqm,
        lo.land_area AS letout_land_area_sqm,
        lo.billable_area AS letout_billable_area_sqm,
        lo.dept_id AS letout_dept_id,
        lo.from_date AS letout_from_date,
        lo.to_date AS letout_to_date
    FROM public.plot AS p
    LEFT JOIN LATERAL (
        SELECT lo_inner.*
        FROM public.let_out AS lo_inner
        WHERE lo_inner.plot_id = p.plot_id
        ORDER BY
            (lo_inner.status = 'A') DESC,
            lo_inner.update_timestamp DESC NULLS LAST,
            lo_inner.let_out_id DESC
        LIMIT 1
    ) AS lo ON TRUE
    WHERE p.is_vacant IS TRUE
), selected_tenancy AS (
    SELECT
        sl.plot_id,
        ltm.tenancy_id,
        ltm.unit_id,
        ltm.is_active AS tenancy_mapping_active,
        ltm.is_alloted AS tenancy_allotted,
        ltm.company_name AS existing_tenant_name,
        ltm.current_rent AS existing_current_rent,
        ltm.current_rent_commercial AS existing_commercial_rent,
        ltm.g_secrate AS existing_g_sec_rate,
        ltm.long_lease_years AS existing_lease_years,
        ltm.agreement_start_date AS existing_agreement_start_date,
        ltm.agreement_end_date AS existing_agreement_end_date,
        ltm.lac_approval_date AS existing_lac_approval_date,
        ltm.chairman_approval_date AS existing_chairman_approval_date,
        ltm.board_approval_date AS existing_board_approval_date,
        ltm.tamps_approval_date AS existing_tamps_approval_date,
        ltm.is_upfront_premimum AS existing_upfront_premium_flag,
        ltm.upfront_premimum_amount AS existing_upfront_premium_amount
    FROM selected_letout AS sl
    LEFT JOIN LATERAL (
        SELECT ltm_inner.*
        FROM public.letout_tenancy_unit_mapping AS ltm_inner
        WHERE ltm_inner.letout_id = sl.let_out_id
          AND NULLIF(BTRIM(ltm_inner.tenancy_id), '') IS NOT NULL
        ORDER BY
            ltm_inner.is_active DESC NULLS LAST,
            ltm_inner.update_timestamp DESC NULLS LAST,
            ltm_inner.sr_no DESC
        LIMIT 1
    ) AS ltm ON TRUE
), selected_area AS (
    SELECT
        sl.plot_id,
        lba.area AS tenancy_area_sqm,
        lba.consumed_fsi AS tenancy_consumed_fsi,
        lba.built_up_area_rec AS tenancy_recorded_built_up_area_sqm,
        lba.built_up_area_commercial AS tenancy_commercial_built_up_area_sqm,
        lba.is_active AS tenancy_area_active,
        lba.from_date AS tenancy_area_from_date,
        lba.to_date AS tenancy_area_to_date
    FROM selected_letout AS sl
    LEFT JOIN selected_tenancy AS st ON st.plot_id = sl.plot_id
    LEFT JOIN LATERAL (
        SELECT lba_inner.*
        FROM public.letout_b_area AS lba_inner
        WHERE lba_inner.let_out_id = sl.let_out_id
          AND (
                st.tenancy_id IS NULL
                OR BTRIM(lba_inner.tenancy_id) = BTRIM(st.tenancy_id)
              )
        ORDER BY
            (st.tenancy_id IS NOT NULL AND BTRIM(lba_inner.tenancy_id) = BTRIM(st.tenancy_id)) DESC,
            lba_inner.is_active DESC NULLS LAST,
            lba_inner.update_timestamp DESC NULLS LAST,
            lba_inner.letout_b_area_id DESC
        LIMIT 1
    ) AS lba ON TRUE
), selected_planning AS (
    SELECT
        p.plot_id,
        pmpz.fsi AS recorded_planning_fsi,
        pmpz.additional_fsi AS recorded_additional_fsi,
        pmpz.fsi_addition AS recorded_fsi_addition,
        pmpz.built_up_area AS recorded_planning_built_up_area_sqm,
        pmpz.crz_applicable,
        pmpz.re_develop_applicable
    FROM public.plot AS p
    LEFT JOIN LATERAL (
        SELECT pmpz_inner.*
        FROM public.plot_mstr_plan_zone AS pmpz_inner
        WHERE pmpz_inner.plot_id = p.plot_id
        ORDER BY
            pmpz_inner.is_active DESC NULLS LAST,
            pmpz_inner.update_timestamp DESC NULLS LAST,
            pmpz_inner.plot_mstr_plan_zone_id DESC
        LIMIT 1
    ) AS pmpz ON TRUE
    WHERE p.is_vacant IS TRUE
), selected_application AS (
    SELECT
        st.plot_id,
        apm.tenancy_id AS application_tenancy_id,
        apm.status AS application_status,
        apm.is_alloted AS application_allotted,
        apm.purpose AS existing_application_purpose,
        apm.allotment_basis AS existing_allotment_basis,
        apm.duration_from AS existing_application_lease_start_date,
        apm.duration_to AS existing_application_lease_end_date,
        apm.tender_number AS existing_tender_number,
        apm.tender_id AS existing_tender_id,
        apm.tender_description AS existing_tender_description,
        apm.rate AS existing_application_rate,
        apm.percent_rate_revision AS existing_rate_revision_percent,
        apm.amount_rate_revision AS existing_rate_revision_amount,
        apm.upfront_premium_amt AS existing_application_upfront_premium,
        apm.security_deposit_amt AS existing_security_deposit,
        apm.date_of_agreement AS existing_application_agreement_date,
        apm.sor_applicable_date AS existing_sor_applicable_date
    FROM selected_tenancy AS st
    LEFT JOIN LATERAL (
        SELECT apm_inner.*
        FROM public.applicant_property_mapping AS apm_inner
        WHERE BTRIM(apm_inner.tenancy_id) = BTRIM(st.tenancy_id)
        ORDER BY
            (UPPER(BTRIM(apm_inner.status)) = 'APPROVED') DESC,
            apm_inner.update_timestamp DESC NULLS LAST
        LIMIT 1
    ) AS apm ON TRUE
), selected_rates AS (
    SELECT
        p.plot_id,
        rrlv.rr_land_value AS recorded_rr_land_value,
        rrlv.from_date AS rr_land_value_from_date,
        rrlv.to_date AS rr_land_value_to_date,
        psmv.sor_mkt_value AS recorded_sor_market_value,
        psmv.from_date AS sor_market_value_from_date,
        psmv.to_date AS sor_market_value_to_date,
        zr.home_rate AS zone_home_rate,
        zr.non_home_rate AS zone_non_home_rate,
        zr.annual_increment AS zone_annual_increment,
        zr.rate_applicable_from AS zone_rate_from_date,
        zr.rate_applicable_upto AS zone_rate_to_date
    FROM public.plot AS p
    LEFT JOIN LATERAL (
        SELECT rrlv_inner.*
        FROM public.plot_rr_land_value AS rrlv_inner
        WHERE rrlv_inner.plot_id = p.plot_id
        ORDER BY
            (rrlv_inner.from_date <= CURRENT_DATE AND (rrlv_inner.to_date IS NULL OR rrlv_inner.to_date >= CURRENT_DATE)) DESC,
            rrlv_inner.from_date DESC NULLS LAST,
            rrlv_inner.plot_rr_land_value_id DESC
        LIMIT 1
    ) AS rrlv ON TRUE
    LEFT JOIN LATERAL (
        SELECT psmv_inner.*
        FROM public.plot_sor_market_value AS psmv_inner
        WHERE psmv_inner.plot_id = p.plot_id
        ORDER BY
            (psmv_inner.from_date <= CURRENT_DATE AND (psmv_inner.to_date IS NULL OR psmv_inner.to_date >= CURRENT_DATE)) DESC,
            psmv_inner.from_date DESC NULLS LAST,
            psmv_inner.plot_sor_market_value_id DESC
        LIMIT 1
    ) AS psmv ON TRUE
    LEFT JOIN LATERAL (
        SELECT zr_inner.*
        FROM public.zone_rate AS zr_inner
        WHERE zr_inner.zone_id = p.zone_id
          AND zr_inner.zone_detail_id IS NOT DISTINCT FROM p.zone_detail_id
        ORDER BY
            (zr_inner.rate_applicable_from <= CURRENT_DATE AND (zr_inner.rate_applicable_upto IS NULL OR zr_inner.rate_applicable_upto >= CURRENT_DATE)) DESC,
            zr_inner.rate_applicable_from DESC NULLS LAST,
            zr_inner.zone_rate_id DESC
        LIMIT 1
    ) AS zr ON TRUE
    WHERE p.is_vacant IS TRUE
)
SELECT
    p.plot_id AS source_plot_id,
    p.plot_code,
    p.rr_no,
    p.street_no,
    p.main_structure_name,
    p.location,
    p.city_survey_no,
    p.city_survey_div,
    p.area AS plot_area_sqm,
    p.plot_desc,
    p.status AS plot_status,
    p.is_active AS plot_active,
    p.is_vacant,
    p.owner,
    p.owner_name,
    p.owner_contactno,
    p.dept_name,
    p.estate_id,
    p.div_id,
    p.unit_id AS plot_unit_id,
    p.ward_id,
    p.zone_id,
    p.zone_detail_id,
    p.customer_code AS plot_customer_code,
    p.mcgm_allotted_no,
    p.mcgm_plot_no,
    p.existing_plot_no,
    p.reservation,
    p.rrzone2017,
    p.mbpt_road_connectivity,
    p.schedule_east,
    p.schedule_west,
    p.schedule_north,
    p.schedule_south,
    p.pincode,
    p.remarks AS plot_remarks,
    sl.let_out_id,
    sl.let_out_name,
    sl.letout_status,
    sl.letout_recorded_area_sqm,
    sl.letout_land_area_sqm,
    sl.letout_billable_area_sqm,
    sl.letout_dept_id,
    sl.letout_from_date,
    sl.letout_to_date,
    st.tenancy_id AS existing_tenancy_id,
    st.unit_id AS existing_tenancy_unit_id,
    st.tenancy_mapping_active,
    st.tenancy_allotted,
    st.existing_tenant_name,
    st.existing_current_rent,
    st.existing_commercial_rent,
    st.existing_g_sec_rate,
    st.existing_lease_years,
    st.existing_agreement_start_date,
    st.existing_agreement_end_date,
    st.existing_lac_approval_date,
    st.existing_chairman_approval_date,
    st.existing_board_approval_date,
    st.existing_tamps_approval_date,
    st.existing_upfront_premium_flag,
    st.existing_upfront_premium_amount,
    sa.tenancy_area_sqm,
    sa.tenancy_consumed_fsi,
    sa.tenancy_recorded_built_up_area_sqm,
    sa.tenancy_commercial_built_up_area_sqm,
    sa.tenancy_area_active,
    sa.tenancy_area_from_date,
    sa.tenancy_area_to_date,
    sp.recorded_planning_fsi,
    sp.recorded_additional_fsi,
    sp.recorded_fsi_addition,
    sp.recorded_planning_built_up_area_sqm,
    sp.crz_applicable,
    sp.re_develop_applicable,
    sapp.application_tenancy_id,
    sapp.application_status,
    sapp.application_allotted,
    sapp.existing_application_purpose,
    sapp.existing_allotment_basis,
    sapp.existing_application_lease_start_date,
    sapp.existing_application_lease_end_date,
    sapp.existing_tender_number,
    sapp.existing_tender_id,
    sapp.existing_tender_description,
    sapp.existing_application_rate,
    sapp.existing_rate_revision_percent,
    sapp.existing_rate_revision_amount,
    sapp.existing_application_upfront_premium,
    sapp.existing_security_deposit,
    sapp.existing_application_agreement_date,
    sapp.existing_sor_applicable_date,
    sr.recorded_rr_land_value,
    sr.rr_land_value_from_date,
    sr.rr_land_value_to_date,
    sr.recorded_sor_market_value,
    sr.sor_market_value_from_date,
    sr.sor_market_value_to_date,
    sr.zone_home_rate,
    sr.zone_non_home_rate,
    sr.zone_annual_increment,
    sr.zone_rate_from_date,
    sr.zone_rate_to_date
FROM public.plot AS p
LEFT JOIN selected_letout AS sl ON sl.plot_id = p.plot_id
LEFT JOIN selected_tenancy AS st ON st.plot_id = p.plot_id
LEFT JOIN selected_area AS sa ON sa.plot_id = p.plot_id
LEFT JOIN selected_planning AS sp ON sp.plot_id = p.plot_id
LEFT JOIN selected_application AS sapp ON sapp.plot_id = p.plot_id
LEFT JOIN selected_rates AS sr ON sr.plot_id = p.plot_id
WHERE p.is_vacant IS TRUE
ORDER BY p.plot_code NULLS LAST, p.plot_id;

-- name: tender_plot_area_history
SELECT
    p.plot_id AS source_plot_id,
    p.plot_code,
    lo.let_out_id,
    lo.let_out_name,
    lba.letout_b_area_id,
    lba.tenancy_id,
    lba.area AS tenancy_area_sqm,
    lba.consumed_fsi,
    lba.built_up_area_rec,
    lba.built_up_area_commercial,
    lba.is_active,
    lba.status,
    lba.from_date,
    lba.to_date,
    lba.update_timestamp
FROM public.plot AS p
JOIN public.let_out AS lo ON lo.plot_id = p.plot_id
JOIN public.letout_b_area AS lba ON lba.let_out_id = lo.let_out_id
WHERE p.is_vacant IS TRUE
ORDER BY p.plot_code NULLS LAST, lo.let_out_id, lba.tenancy_id, lba.update_timestamp DESC NULLS LAST, lba.letout_b_area_id DESC;

-- name: tender_tenancy_reference
SELECT
    p.plot_id AS source_plot_id,
    p.plot_code,
    lo.let_out_id,
    lo.let_out_name,
    lo.status AS letout_status,
    ltm.sr_no AS tenancy_mapping_id,
    ltm.tenancy_id,
    ltm.unit_id,
    ltm.company_name,
    ltm.is_active,
    ltm.is_alloted,
    ltm.current_rent,
    ltm.current_rent_commercial,
    ltm.home_rate,
    ltm.non_home_rate,
    ltm.g_secrate,
    ltm.long_lease_years,
    ltm.agreement_start_date,
    ltm.agreement_end_date,
    ltm.lac_approval_date,
    ltm.chairman_approval_date,
    ltm.board_approval_date,
    ltm.tamps_approval_date,
    ltm.commencement_date,
    ltm.termination_date,
    ltm.is_upfront_premimum,
    ltm.upfront_premimum_amount,
    ltm.is_service_charge_applicable,
    ltm.percent_rate_revision,
    ltm.amount_rate_revision,
    ltm.update_timestamp
FROM public.plot AS p
JOIN public.let_out AS lo ON lo.plot_id = p.plot_id
JOIN public.letout_tenancy_unit_mapping AS ltm ON ltm.letout_id = lo.let_out_id
WHERE p.is_vacant IS TRUE
ORDER BY p.plot_code NULLS LAST, lo.let_out_id, ltm.tenancy_id, ltm.update_timestamp DESC NULLS LAST, ltm.sr_no DESC;

-- name: tender_application_reference
SELECT
    apm.tenancy_id,
    apm.tenant_id,
    apm.customer_code,
    apm.unit_id,
    apm.status,
    apm.is_alloted,
    apm.purpose,
    apm.allotment_basis,
    apm.tender_number,
    apm.tender_id,
    apm.tender_description,
    apm.duration_from,
    apm.duration_to,
    apm.rate,
    apm.is_sor_applicable,
    apm.sor_applicable_date,
    apm.percent_rate_revision,
    apm.amount_rate_revision,
    apm.upfront_premium_amt,
    apm.security_deposit_amt,
    apm.total_security_deposit,
    apm.date_of_agreement,
    apm.remarks,
    apm.justification,
    apm.terms_and_condition,
    apm.update_timestamp
FROM public.applicant_property_mapping AS apm
WHERE EXISTS (
    SELECT 1
    FROM public.plot AS p
    JOIN public.let_out AS lo ON lo.plot_id = p.plot_id
    JOIN public.letout_tenancy_unit_mapping AS ltm ON ltm.letout_id = lo.let_out_id
    WHERE p.is_vacant IS TRUE
      AND BTRIM(ltm.tenancy_id) = BTRIM(apm.tenancy_id)
)
ORDER BY apm.tenancy_id, apm.update_timestamp DESC NULLS LAST;

-- name: tender_rate_reference
SELECT
    'zone_rate' AS source_table,
    zr.zone_rate_id::text AS source_record_id,
    zr.zone_id::text AS zone_id,
    zr.zone_detail_id::text AS zone_detail_id,
    zr.home_rate::text AS home_rate,
    zr.non_home_rate::text AS non_home_rate,
    zr.annual_increment::text AS annual_increment,
    zr.rate_applicable_from::text AS effective_from,
    zr.rate_applicable_upto::text AS effective_to,
    zr.status::text AS status,
    NULL::text AS service_rate,
    NULL::text AS interest_rate
FROM public.zone_rate AS zr
UNION ALL
SELECT
    'm_service_charge_rates',
    mscr.service_charge_id::text,
    NULL::text,
    NULL::text,
    NULL::text,
    NULL::text,
    NULL::text,
    mscr.period_from::text,
    mscr.period_to::text,
    NULL::text,
    mscr.service_rate::text,
    NULL::text
FROM public.m_service_charge_rates AS mscr
UNION ALL
SELECT
    'm_interest_rates',
    mir.interest_charge_id::text,
    NULL::text,
    NULL::text,
    NULL::text,
    NULL::text,
    NULL::text,
    mir.period_from::text,
    mir.period_to::text,
    NULL::text,
    NULL::text,
    mir.interest_rate::text
FROM public.m_interest_rates AS mir
ORDER BY source_table, source_record_id;

-- name: tender_source_coverage
SELECT 'eligible_vacant_plots' AS source_metric, COUNT(*)::text AS source_value
FROM public.plot
WHERE is_vacant IS TRUE
UNION ALL
SELECT 'eligible_plots_with_recorded_planning_fsi', COUNT(*)::text
FROM public.plot AS p
WHERE p.is_vacant IS TRUE
  AND EXISTS (
      SELECT 1
      FROM public.plot_mstr_plan_zone AS pmpz
      WHERE pmpz.plot_id = p.plot_id
        AND pmpz.fsi IS NOT NULL
  )
UNION ALL
SELECT 'eligible_plots_with_recorded_sor_market_value', COUNT(*)::text
FROM public.plot AS p
WHERE p.is_vacant IS TRUE
  AND EXISTS (
      SELECT 1
      FROM public.plot_sor_market_value AS psmv
      WHERE psmv.plot_id = p.plot_id
        AND psmv.sor_mkt_value IS NOT NULL
  )
UNION ALL
SELECT 'active_zone_rate_rows', COUNT(*)::text
FROM public.zone_rate
WHERE rate_applicable_from <= CURRENT_DATE
  AND (rate_applicable_upto IS NULL OR rate_applicable_upto >= CURRENT_DATE)
UNION ALL
SELECT 'service_charge_rate_rows', COUNT(*)::text
FROM public.m_service_charge_rates
UNION ALL
SELECT 'interest_rate_rows', COUNT(*)::text
FROM public.m_interest_rates
ORDER BY source_metric;
