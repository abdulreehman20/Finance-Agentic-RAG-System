from fastapi import APIRouter

router = APIRouter(prefix="/rag", tags=["rag"])


# Add RAG endpoints
@router.get("/rag")
async def get_rag():
    return {"message": "Hello RAG"}


# Add Ingestion &query rouyte with testing data
@router.post("/ingest")
async def ingest_data():
    return {"message": "Hello Ingestion"}


@router.post("/query")
async def query_data():
    return {"message": "Hello Query"}
