from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def home():
    return {"system":"C Learning Ecosystem"}
