import psycopg

def grant_select():
    tables = [
        "plot",
        "plot_action_status",
        "plot_dept_mapping",
        "plot_docs",
        "plot_ext_mstr_plan_zone",
        "plot_ext_reservation",
        "plot_fair_mkt_value",
        "plot_letout_mapping",
        "plot_merge_tbl",
        "plot_mstr_plan_zone",
        "plot_proposed_mstr_plan_zone",
        "plot_proposed_reservation",
        "plot_rmk",
        "plot_rr_land_value",
        "plot_sor_market_value",
        "plot_split_merge",
        "plot_test",
        "plot_zone_details",
        "pmemo"
    ]
    
    try:
        # Connect as superuser
        conn = psycopg.connect(
            host="localhost",
            port=5432,
            dbname="postgres",
            user="postgres",
            password="root",
            autocommit=True
        )
        cur = conn.cursor()
        
        # Grant select on the tables
        for table in tables:
            cur.execute(f"GRANT SELECT ON TABLE {table} TO llm_readonly;")
            
        print("SELECT Permissions granted.")
        
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Connection error: {e}")

if __name__ == "__main__":
    grant_select()
