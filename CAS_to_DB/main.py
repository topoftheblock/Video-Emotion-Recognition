from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from langchain_community.utilities import SQLDatabase
from langchain_openai import ChatOpenAI
from langchain_community.agent_toolkits import create_sql_agent
from langchain.agents.agent_types import AgentType

# --- 1. FastAPI App initialisieren (Die Middleware) ---
app = FastAPI(title="DUUI Text-to-SQL Agent API")

# --- 2. Datenbank-Verbindung (WICHTIG: Read-Only User!) ---
# Nutze hier zwingend einen User, der NUR SELECT-Rechte hat.
DB_URI = "postgresql+psycopg2://duui_readonly:dein_passwort@localhost:5432/duui_database"
db = SQLDatabase.from_uri(DB_URI)

# --- 3. Das LLM initialisieren ---
# GPT-4o ist für SQL-Generierung aktuell am stärksten. Temperature=0 für deterministische Antworten.
llm = ChatOpenAI(model="gpt-4o", temperature=0, openai_api_key="DEIN_OPENAI_API_KEY")

# --- 4. Den LangChain SQL-Agenten bauen (Der Self-Correction Loop) ---
# Dieser Agent holt sich automatisch das Schema (DDL) der Tabellen und probiert 
# Queries so lange aus, bis sie funktionieren (oder das Limit erreicht ist).
agent_executor = create_sql_agent(
    llm=llm,
    toolkit=db,
    agent_type=AgentType.OPENAI_TOOLS,
    verbose=True, # Setze dies auf True, um in der Konsole zu sehen, wie die KI "denkt"
    handle_parsing_errors=True # Fängt Fehler ab und probiert es erneut
)

# --- 5. API Endpunkt für das Frontend ---
class QueryRequest(BaseModel):
    question: str

class QueryResponse(BaseModel):
    answer: str
    
@app.post("/ask", response_model=QueryResponse)
async def ask_database(request: QueryRequest):
    try:
        # Hier passiert die Magie: Der Agent übersetzt, führt aus und antwortet.
        # Beispiel-Input: "Zeige mir alle Videos, in denen Person A wütend war."
        response = agent_executor.invoke({"input": request.question})
        
        return QueryResponse(answer=response["output"])
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Starten mit: uvicorn main:app --reload