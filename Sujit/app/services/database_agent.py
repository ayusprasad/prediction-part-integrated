import os
from urllib.parse import quote_plus

from dotenv import load_dotenv

load_dotenv()


class DatabaseAgent:
    def __init__(self, model_name=None):
        self.model_name = model_name or os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
        self.agent_executor = None
        self.error = None
        self.include_tables = [
            "plot", "plot_action_status", "plot_dept_mapping", "plot_docs", "plot_ext_mstr_plan_zone",
            "plot_ext_reservation", "plot_fair_mkt_value", "plot_letout_mapping", "plot_merge_tbl",
            "plot_mstr_plan_zone", "plot_proposed_mstr_plan_zone", "plot_proposed_reservation", "plot_rmk",
            "plot_rr_land_value", "plot_sor_market_value", "plot_split_merge", "plot_test", "plot_zone_details", "pmemo",
            "mcustomer", "mtenant", "tgeneralbill", "monthly_final_bills", "monthly_heads_bill",
        ]
        try:
            from langchain_community.utilities import SQLDatabase
            from langchain_community.llms import Ollama
            from langchain_community.agent_toolkits import create_sql_agent
            user = quote_plus(os.getenv("POSTGRES_USER", "postgres"))
            password = quote_plus(os.getenv("POSTGRES_PASSWORD", ""))
            host = os.getenv("POSTGRES_HOST", "localhost")
            port = os.getenv("POSTGRES_PORT", "5432")
            dbname = os.getenv("POSTGRES_DB", "postgres")
            self.db_uri = f"postgresql+psycopg://{user}:{password}@{host}:{port}/{dbname}"
            self.db = SQLDatabase.from_uri(self.db_uri, include_tables=self.include_tables)
            self.llm = Ollama(model=self.model_name)
            self.agent_executor = create_sql_agent(
                llm=self.llm, db=self.db, agent_type="zero-shot-react-description", verbose=False,
                handle_parsing_errors=True,
                prefix="You are a read-only SQL assistant. Execute safe SELECT queries only and report exact results.",
            )
        except Exception as error:
            self.error = str(error)

    def query(self, question: str) -> str:
        if self.agent_executor is None:
            return "Structured database agent is unavailable. The billing forecast endpoint remains available; install/configure LangChain and Ollama for natural-language database queries."
        try:
            response = self.agent_executor.invoke({"input": question})
            return response.get("output", "Could not generate an answer.")
        except Exception as error:
            return f"Error executing database query: {error}"
