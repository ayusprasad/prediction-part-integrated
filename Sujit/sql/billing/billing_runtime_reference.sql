-- Billing Forecast: PostgreSQL runtime reference queries
--
-- Used by app/services/billing_prediction_service.py.
-- The application binds every %s parameter through psycopg; these are not
-- DBeaver literals. For manual investigation, replace each %s with a reviewed
-- value in a copy of the query.
--
-- All statements are read-only. Billing rules such as valid charge IDs and
-- configured tax columns are loaded from config/billing_formula_rules.json.

-- name: tenancy_customer_options
-- Parameter 1: text[] tenancy IDs read from the configured tax-mapping CSV.
SELECT DISTINCT
    BTRIM(customercode) AS tenancy_id,
    customerid::text AS customer_id
FROM public.mcustomer
WHERE BTRIM(customercode) = ANY(%s);

-- name: customer_id_for_tenancy
-- Parameter 1: tenancy ID.
SELECT DISTINCT mc.customerid::text AS customer_id
FROM public.mcustomer AS mc
WHERE BTRIM(mc.customercode) = %s
ORDER BY mc.customerid::text;

-- name: customer_bill_history
-- Parameter 1: customer ID. Parameter 2: integer[] charge IDs selected by the
-- configured billing category. This yields one aggregated source row per bill period.
SELECT
    BTRIM(tg.billyearmonth::text) AS bill_period,
    SUM(COALESCE(tg.amount, 0))::double precision AS amount,
    SUM(COALESCE(tg.cgst, 0))::double precision AS cgst,
    SUM(COALESCE(tg.sgst, 0))::double precision AS sgst
FROM public.tgeneralbill AS tg
WHERE BTRIM(tg.customerid) = %s
  AND tg.billchargeid = ANY(%s)
  AND BTRIM(tg.billyearmonth::text) ~ '^20[0-9]{4}$'
  AND COALESCE(tg.amount, 0) > 0
GROUP BY BTRIM(tg.billyearmonth::text)
ORDER BY BTRIM(tg.billyearmonth::text);

-- name: customer_profile_with_plot
-- Parameter 1: numeric customer ID. The lateral join chooses one current plot
-- reference and never changes source data.
SELECT
    mc.billperiodicity,
    mc.rrplotno,
    mc.customercode,
    mc.typeofconstructionid,
    mc.isadditionalrent,
    p.area,
    p.main_structure_name
FROM public.mcustomer AS mc
LEFT JOIN LATERAL (
    SELECT area, main_structure_name
    FROM public.plot
    WHERE plot.customer_code = mc.customercode
       OR plot.rr_no = mc.rrplotno
    ORDER BY is_active DESC NULLS LAST, plot_id DESC
    LIMIT 1
) AS p ON TRUE
WHERE mc.customerid = %s
ORDER BY mc.modifieddate DESC NULLS LAST
LIMIT 1;

-- name: tenancy_structure
-- Parameter 1: tenancy ID.
SELECT
    BTRIM(apm."Structure_type_id") AS structure_type_id,
    st.structure_type
FROM public.applicant_property_mapping AS apm
LEFT JOIN public.m_structure_type AS st
    ON st.structure_type_id = CASE
        WHEN BTRIM(apm."Structure_type_id") ~ '^[0-9]+$'
        THEN BTRIM(apm."Structure_type_id")::integer
    END
WHERE BTRIM(apm.tenancy_id) = %s
ORDER BY apm.update_timestamp DESC NULLS LAST
LIMIT 1;

-- name: master_tax_rates
-- Parameter 1: target month as a date. Parameter 2: same target month.
-- `{configured_tax_columns}` is built only from validated identifiers in
-- config/billing_formula_rules.json; it is never supplied by a browser user.
SELECT {configured_tax_columns}
FROM public.m_tax_rates
WHERE tax_period_from <= %s
  AND (tax_period_to IS NULL OR tax_period_to >= %s)
ORDER BY tax_period_from DESC
LIMIT 1;

-- name: scheduled_tax_rates
-- Parameter 1: target month as a date. Parameter 2: same target month.
SELECT
    LOWER(tax_name) AS tax_name,
    tax_percentage
FROM public.m_tax_for_treecess_street_edu
WHERE period_from <= %s
  AND (period_to IS NULL OR period_to >= %s)
ORDER BY period_from DESC;
