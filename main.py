from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI()

@app.get("/question")
def get_dummy_question():
    return JSONResponse(content={"question": "What is the capital of France?"})
