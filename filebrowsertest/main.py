from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse,StreamingResponse
from pydantic import BaseModel
from PIL import Image
import io
import cv2
from random import randint


from typing import List
from pathlib import Path

app = FastAPI()

#BASE_DIR = Path("/data/files").resolve()   # root directory you allow browsing
BASE_DIR = Path("/Users/entropic/Pictures").resolve()

def safe_path(relative_path: str) -> Path:
    """Prevent path traversal attacks"""
    target_path = (BASE_DIR / relative_path).resolve()
    if not target_path.is_relative_to(BASE_DIR):
        raise HTTPException(status_code=403, detail="Invalid path")
    return target_path


def img_add_border(image, borderType,border_rel ):
     top = int(border_rel * image.shape[0])  # shape[0] = rows
     bottom = top
     left = int(border_rel * image.shape[1])  # shape[1] = cols
     right = left
     value = [randint(0, 255), randint(0, 255), randint(0, 255)]
     imagebordered = cv2.copyMakeBorder(image, top, bottom, left, right, borderType, None, value)
     return(imagebordered)

class Point(BaseModel):
    x: float
    y: float

class Polygon(BaseModel):
    image_path: str
    closed: bool
    points: List[Point]




@app.get("/browse")
def browse(path: str = Query("", description="Relative directory path")):
    directory = safe_path(path)
    print("directory=", directory)

    if not directory.exists() or not directory.is_dir():
        raise HTTPException(status_code=404, detail="Directory not found")

    items = []
    for item in sorted(directory.iterdir()):
        items.append({
            "name": item.name,
            "type": "directory" if item.is_dir() else "file",
            "path": str(item.relative_to(BASE_DIR))
        })

    return JSONResponse({
        "current_path": str(directory.relative_to(BASE_DIR)),
        "items": items
    })


@app.get("/download")

def download(path: str = Query(..., description="Relative file path")):
    file_path = safe_path(path)




    if not file_path.exists() or not file_path.is_file():
    #if not (file_path.replace(" ","%20")).exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    '''if str(file_path).lower().endswith(".jp2"):
        print(".jp2 file processing")
        img = Image.open(file_path)
        img.verify()
        img.load()
        buf = io.BytesIO()
        img.convert("RGB").save(buf, format="JPEG")
        buf.seek(0)
        return StreamingResponse(buf, media_type="image/jpeg")'''
    if file_path.suffix.lower() == ".jp2":
        img = cv2.imread(str(file_path), cv2.IMREAD_COLOR)
        #img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

        if img is None:
            raise HTTPException(status_code=500, detail="Failed to read JP2")

        # BGR → RGB
        #img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        print('img size', img.shape)
        # hier moeten we borders toevoegen:
        # beter functie add_borders

        borderType = cv2.BORDER_REPLICATE
        border_rel=0.2
        print("rel border ",border_rel)
        imgbordered=img_add_border(img , borderType, border_rel)
        img=imgbordered

        success, buffer = cv2.imencode(".jpg", img)
        if not success:
            raise HTTPException(status_code=500, detail="Encoding failed")

        return StreamingResponse(
            io.BytesIO(buffer.tobytes()),
            media_type="image/jpeg"
        )
    return FileResponse(file_path,media_type="image/jpeg")



    '''return FileResponse(
        file_path,
        #filename=file_path.name,
        filename=file_path.name.replace(" ","%20"),
        #media_type="application/octet-stream"`
        media_type="image/jpeg"
    )'''

@app.get("/select")
async def download(path: str = Query(..., description="Relative file path")):
    file_path = safe_path(path)

    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    if file_path.is_file():
        buf = await file_path.read()
        image=Image.open(BytesIO(buf))
        return {
            "annotated_image": image_to_base64(image),
            "class_prob": class_prob
        }


    return FileResponse(
        file_path,
        filename=file_path.name,
        #media_type="application/octet-stream"`
        media_type="image/jpeg"
    )

def image_to_base64(image):
    buffered = BytesIO()
    image.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode('utf-8')

@app.post("/annotations")
async def get_polygon(request: Polygon):
     print(request)
     #return {"status": "ok"}
     return {
                "selected_points": request.points
            }


 #save_polygon()



