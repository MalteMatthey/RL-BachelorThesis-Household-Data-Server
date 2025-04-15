from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi.responses import JSONResponse
import os

API_KEY = os.getenv("API_KEY")

app = FastAPI()

def verify_api_key(x_api_key: str = Header(...)):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API Key")

@app.get("/question")
def get_dummy_question(api_key: str = Depends(verify_api_key)):
    return JSONResponse(content={"question": "What is the capital of France?"})