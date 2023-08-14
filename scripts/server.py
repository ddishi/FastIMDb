import base64
from fastapi import FastAPI, HTTPException, UploadFile, File
import os
from starlette.responses import FileResponse
from db_manager import DBManager
from image_processor import ImageProcessor
from main import handle_image_upload

db_pass = os.environ.get("DB_PASSWORD")
db_user = os.environ.get("DB_USER")

db_manager = DBManager(
    host="celebs-database-1.c4duzx241qat.eu-north-1.rds.amazonaws.com",
    user=db_user,
    password=db_pass,
    database="celebs_database",
    table='Celebs2')

image_processor = ImageProcessor(bucket_name='celebs-images-bucket-2')
image_processor.load_annoy_index_and_mapping(128, "../data/new_annoy.ann", '../data/new_idx_map.pkl')

app = FastAPI()


@app.get("/")
def read_root():
    return FileResponse('../static/index.html')


@app.get("/script.js")
async def serve_script():
    return FileResponse('../static/script.js')


@app.get("/style.css")
async def serve_script():
    return FileResponse('../static/style.css')


@app.get("uploads")
async def serve_script():
    return FileResponse('uploads')


def process_uploaded_image(image_path, image_processor, db_manager):
    try:
        matched_celeb_info = handle_image_upload(image_path, image_processor, db_manager, from_server=True)
        filename = os.path.basename(image_path)
        os.remove(image_path)
        return {"filename": filename, "celebrity_info": matched_celeb_info}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/uploadImage/")
async def upload_image(image_data: dict):
    image_base64 = image_data.get('image')
    os.makedirs('uploads', exist_ok=True)
    image_data = base64.b64decode(image_base64)
    filename = "captured_image.jpg"
    image_path = os.path.join("uploads", filename)
    with open(image_path, "wb") as fh:
        fh.write(image_data)
    return process_uploaded_image(image_path, image_processor, db_manager)


@app.post("/uploadFile/")
async def upload_file(file: UploadFile = File(...)):
    os.makedirs('uploads', exist_ok=True)
    filename = file.filename
    image_path = os.path.join("uploads", filename)
    with open(image_path, "wb") as f:
        f.write(file.file.read())
    return process_uploaded_image(image_path, image_processor, db_manager)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
