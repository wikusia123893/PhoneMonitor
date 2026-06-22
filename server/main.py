from fastapi import FastAPI

app = FastAPI(title="Phone Monitor API")


@app.get("/")
def root():
    return {
        "status": "OK",
        "message": "Phone Monitor działa 🚀"
    }
