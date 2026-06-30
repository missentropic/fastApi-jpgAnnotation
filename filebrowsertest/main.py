from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse,StreamingResponse
from pydantic import BaseModel
from PIL import Image
import io
import cv2
import numpy as np
import sys
import json
import base64
#sys.path.append('../dewarp/page_dewarp/')
sys.path.append('/Users/entropic/Desktop/vanessa/dewarp/page_dewarp/')
from random import randint
from PIL import Image, ImageTk, ImageOps
from hough_line_corner_detector import HoughLineCornerDetector
from processors import Resizer, OtsuThresholder, FastDenoiser, Colorpicker, Closer,Brightness_enhancer, PointDto
import tkinter as tk
from tkinter import filedialog

from page_dewarp import get_contours,resize_to_screen,get_page_extents,assemble_spans, merge_span_rect, merge_span,visualize_spans, ContourInfo, make_tight_mask


from typing import List
from pathlib import Path

app = FastAPI()
borderType = cv2.BORDER_REPLICATE
border_rel=0.2
maxWidth=2000
DEBUG_LEVEL=2
outWidth=int(2200) # single border wordt gebruikt na de picker , dus in corner detector?
outHeight=int(1400)


#BASE_DIR = Path("/data/files").resolve()   # root directory you allow browsing
#BASE_DIR = Path("/Users/entropic/Pictures").resolve()
BASE_DIR = Path("/Users/entropic/Library/CloudStorage/OneDrive-Office365GPI/PAMOS - Photos passeport & CI").resolve()

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
     print('shape imagebordered',imagebordered.shape)

     return(imagebordered)

class Point(BaseModel):
    x: float
    y: float
    def __add__(self, other: "Point") -> "Point":
        return Point(
                x=self.x + other.x,
                y=self.y + other.y
        )

    def __sub__(self, other: "Point") -> "Point":
            return Point(
                x=self.x - other.x,
                y=self.y - other.y
            )

    def __mul__(self, s: float) -> "Point":
           return Point(x=self.x * s, y=self.y * s)

    def scaloffset(self, s: float, other:"Point") -> "Point":
               return Point(x=self.x * s+offset.x, y=self.y * s+offset.y)
    def offsetscale(self, s: float, other:"Point") -> "Point":
                   return Point(x=(self.x +offset.x)*s, y=(self.y+offset.y)*s)


class Polygon(BaseModel):
    image_path: str
    closed: bool
    points: List[Point]
    dim: Point


            #self.rect_hough_fractions= [left_hough/self.pil_img.size[0],top_hough/self.pil_img.size[1],right_hough/self.pil_img.size[0],bottom_hough/self.pil_img.size[1] ]


            #nearpoints= [p - new_origin for p in points]
            #print("nearpoints", nearpoints)


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
    global img, imgbordered



    if not file_path.exists() or not file_path.is_file():
    #if not (file_path.replace(" ","%20")).exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")


    img = cv2.imread(str(file_path), cv2.IMREAD_COLOR)
    if img is None:
            raise HTTPException(status_code=500, detail="Failed to read JP2")

    #print("rel border ",border_rel)
    imgbordered=img_add_border(img , borderType, border_rel)
    img=imgbordered
    success, buffer = cv2.imencode(".jpg", img)
    if not success:
                raise HTTPException(status_code=500, detail="Encoding failed")

    return StreamingResponse(
                io.BytesIO(buffer.tobytes()),
                media_type="image/jpeg"
            )




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
    buffered = io.BytesIO()
    image.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode('utf-8')

@app.post("/annotations")
async def get_polygon(request: Polygon):

     def get_crop_rect(points,dim):
                top = np.min([p.y for p in points]) # dit zijn selected points
                bot = np.max([p.y for p in points])
                left= np.min([p.x for p in points])
                right = np.max([p.x for p in points])
                print('top,bot, left,right selected on bordered', top, bot, left,right)

                border_width=(right-left)/10
                border_height=(bot-top)/10
                top_hough=np.maximum(0,(top-border_height)) # selected + small border
                bottom_hough=np.minimum(1,(bot+border_height))
                left_hough=np.maximum(0,left-border_width)
                right_hough=np.minimum(1,right+border_width) # nog alles in fractions
                print('top,bot, left,right selected + 0.1  on bordered', top_hough, bottom_hough, left_hough,right_hough, "dim", request.dim)
                rect_hough=(left_hough*request.dim.x,top_hough*request.dim.y,right_hough*request.dim.x,bottom_hough*request.dim.y) #in fractions for selection of cropped bordered iage
                print("rect for hough selection+ 0.1 border", rect_hough)
                #new_origin = Point(x=left_hough*dim.x, y=top_hough*dim.y) #in points
                new_origin = Point(x=left_hough, y=top_hough) #in points fractions



                #print("new origin:", new_origin, "left", left_hough, "top", top_hough)
                #print('type points received',[p.x for p in points])
                #new origin is in fractions
                print('new origin before hough and relative to bordered', new_origin)
                return(new_origin, rect_hough)

     pointsarr= (np.array(request.points))
     #print(np.array(request.dim))

     first_selected_points=request.points
     print('first selection,', first_selected_points)
     new_origin, rect_hough=get_crop_rect(request.points,request.dim)
     new_origin_crop_from_bordered=Point(x=new_origin.x*np.array(imgbordered).shape[1],y=new_origin.y*np.array(imgbordered).shape[0])
     print('new_origin bordered ', new_origin, new_origin_crop_from_bordered,'bordered dim', np.array(imgbordered).shape)
     # return {"status": "ok"}
     #rect_hough=(left_hough*request.dim.x,top_hough*request.dim.y,(1-right_hough)*request.dim.x,(1-bottom_hough)*request.dim.y) #in fractions for selection of cropped bordered iage
     #imagesh=ImageOps.crop(Image.fromarray(imgbordered), rect_hough) # deze fout
     imagesh=Image.fromarray(imgbordered).crop( rect_hough) # deze fout
     cropshow = np.array(imagesh)[:, :, ::-1].copy()
     # deze naar frontend to show
     print('size pil from cropped popup show for entry hough', imagesh.size)
     resize_ratio=maxWidth/cropshow.shape[1]
          #out_width=int(imagesh.shape[1] * self._ratio)
     out_height=int(cropshow.shape[0] * resize_ratio)
     print('out height ', out_height)

     dim = (2000, int(out_height))


                  #if image.shape[0] <= self._height:
     if resize_ratio >= 1:
                      resizedbordered = cv2.resize(cropshow, dim, interpolation = cv2.INTER_LINEAR)
     else:
                      resizedbordered = cv2.resize(cropshow, dim, interpolation = cv2.INTER_AREA)
     #resizerbordered=Resizer(resizeHeight=False, maxDim = 2000),

     print(' image size entry hough after first resize ',resizedbordered.shape, resize_ratio)
     resizedbordered = cv2.cvtColor(resizedbordered, cv2.COLOR_BGR2RGB)
     nearpoints = np.array([
                 Point(x=(p.x - new_origin.x)*request.dim.x*resize_ratio, y=(p.y - new_origin.y)*request.dim.y*resize_ratio)
                        for p in pointsarr])
     #print('nearpoints of resize main:',nearpoints)
     #nearpoints=np.array([(round(p.x), round(p.y)) for p in nearpoints])
     nearpoints=np.array([(round(p.x), round(p.y)) for p in nearpoints])
     print('nearpoints in hough of resized main:',nearpoints)

     # self.rect_hough =(left_hough,top_hough,self.pil_img.size[0]-right_hough,self.pil_img.size[1]-bottom_houg
     # imagesh=ImageOps.crop(self.pil_img, self.rect_hough)
     corner_detector = HoughLineCornerDetector(
                 rho_acc = 2,
                 theta_acc = 180,
                 minthresh = 150,
                 maxlines=20,
                 colorpicker=None,
                 shapepicker=None,
                 DEBUG_LEVEL=DEBUG_LEVEL
             )

     quadripoints_cornerdetector=corner_detector(resizedbordered, nearpoints=nearpoints)[0]
     print('quadripoints_cornerdetector', [p for p in quadripoints_cornerdetector])
     #quadripoints=[(p[0], p[1]) for p in quadripoints_cornerdetector]
     #print('quadripoints rescaled', quadripoints)
     # quadripoints is absolute value from imgbordered
     quadripoints=[(p[0]/resize_ratio+new_origin_crop_from_bordered.x, p[1]/resize_ratio+new_origin_crop_from_bordered.y) for p in quadripoints_cornerdetector]

     quadripointsf=[((p[0]/resize_ratio+new_origin_crop_from_bordered.x)/np.array(imgbordered).shape[1], (p[1]/resize_ratio+new_origin_crop_from_bordered.y)/np.array(imgbordered).shape[0]) for p in quadripoints_cornerdetector]
     print ('intersections bordered ',[intersection for intersection in quadripoints])
     #print('quadri type', [(i , i[0]) for i in quadripoints])

     #points_quadripoints=[p.model_dump() for p in quadripoints]
     dict_quadripoints = {index: value for index, value in enumerate(quadripoints)}


     quadrilist = [PointDto(x,y) for (x,y) in quadripointsf]
     print("quadrilist", quadrilist)

     '''pts = np.array([
            (x, y)
            #(x+offset[1], y+offset[0])
            for intersection in quadripoints
            for x, y in intersection
            ])
     pts = np.array([
                 (p.x, p.y)
                 #(x+offset[1], y+offset[0])
                 for p in quadripoints
                 ])'''
     pts= np.array(list(dict_quadripoints.values()))



     np_rect=np.float32([pts[0,:], pts[1,:],pts[2,:], pts[3,:]])
     aspect=np.linalg.norm(pts[1,:]-pts[0,:]+pts[2,:]-pts[3,:])/np.linalg.norm(pts[2,:]-pts[1,:]+pts[3,:]-pts[0,:])
     print('aspect ratio', aspect)
     ## new aspect ratio in output
     outHeight=int(outWidth/aspect)
     print('outHeight', outHeight)
     dst = np.array([
                 [0, 0],                         # Top left point
                 [outWidth - 1, 0],              # Top right point
                 [outWidth - 1, outHeight - 1],  # Bottom right point
                 [0, outHeight - 1]],            # Bottom left point
                 dtype = "float32"  )             # Date type
     M = cv2.getPerspectiveTransform(np_rect, dst)
     #warped = cv2.warpPerspective(cropshow, M, (outWidth, outHeight))
     imgborderedrgb = cv2.cvtColor(imgbordered, cv2.COLOR_BGR2RGB)
     warped = cv2.warpPerspective(imgborderedrgb, M, (outWidth, outHeight))
     print('m',M, warped.shape)



     return ({
     #return({
           "selected_points": request.points,
           #"quadripoints": list(dict_quadripoints.values()),
           "quadripoints": quadrilist,
           "deskewed_image": image_to_base64(Image.fromarray(warped)),
           #"deskewed_image": image_to_base64(Image.fromarray(imgbordered)),
            })

 #save_polygon()



