import psycopg
import json

def get_schema():
    try:
        # Connect to the target database
        conn = psycopg.connect(
            host="localhost",
            port=5432,
            dbname="postgres",
            user="postgres",
            password="root"
        )
        cur = conn.cursor()
        
        # Query to get all tables in the 'public' schema
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' AND table_type = 'BASE TABLE';
        """)
        tables = [row[0] for row in cur.fetchall()]
        
        schema = {}
        for table in tables:
            cur.execute(f"""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_schema = 'public' AND table_name = '{table}';
            """)
            columns = cur.fetchall()
            schema[table] = [{"column": col[0], "type": col[1]} for col in columns]
            
        print(json.dumps(schema, indent=2))
        
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    get_schema()
