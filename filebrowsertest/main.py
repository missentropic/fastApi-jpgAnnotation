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
import math
sys.path.append('./dewarp/page_dewarp/')
#sys.path.append('/Users/entropic/Desktop/vanessa/dewarp/page_dewarp/')
from random import randint
from PIL import Image, ImageTk, ImageOps
from hough_line_corner_detector import HoughLineCornerDetector
from processors import Resizer, OtsuThresholder, FastDenoiser, Colorpicker, Closer,Brightness_enhancer, PointDto, Rectpicker, blur
from page_decoder import extract_text, extract_OCR, debug_show,showrect,box
import tkinter as tk
from tkinter import filedialog

from page_dewarp import get_contours,resize_to_screen,get_page_extents,assemble_spans, merge_span_rect, merge_span,visualize_spans, ContourInfo, make_tight_mask


from typing import List
from pathlib import Path

app = FastAPI()
borderType = cv2.BORDER_REPLICATE
border_rel=0.2
maxWidth=1000 # was 2000
DEBUG_LEVEL=1
outWidth=int(2200) # single border wordt gebruikt na de picker , dus in corner detector?
outHeight=int(1400)
rectpicker = Rectpicker(DEBUG_LEVEL=DEBUG_LEVEL)

#BASE_DIR = Path("/data/files").resolve()   # root directory you allow browsing
#BASE_DIR = Path("/Users/entropic/Pictures").resolve()
#BASE_DIR = Path("/Users/entropic/Library/CloudStorage/OneDrive-Office365GPI/PAMOS - Photos passeport & CI").resolve()
BASE_DIR = Path("/Users/entropic/Desktop/Vanessa/demo_augmented").resolve()

def safe_path(relative_path: str) -> Path:
    """Prevent path traversal attacks"""
    target_path = (BASE_DIR / relative_path).resolve()
    if not target_path.is_relative_to(BASE_DIR):
        raise HTTPException(status_code=403, detail="Invalid path")
    return target_path


def img_add_border(image, borderType,border_rel ):
     top = round(border_rel * image.shape[0])  # shape[0] = rows
     bottom = top
     left = round(border_rel * image.shape[1])  # shape[1] = cols
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

    def __toint__(self, dim: PointDto):
        return Point(x=self.x*dim.x,y=self.y*dim.y)

    def __tofrac__(self, dim: PointDto):
        return Point(x=self.x/dim.x,y=self.y/dim.y)



class Polygon(BaseModel):
    image_path: str
    closed: bool
    points: List[Point]
    dim: Point

def sanitize(obj):
    if isinstance(obj, float):
        return None if math.isnan(obj) or math.isinf(obj) else obj
    elif isinstance(obj, dict):
        return {k: sanitize(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [sanitize(v) for v in obj]
    elif isinstance(obj, tuple):
        return tuple(sanitize(v) for v in obj)
    return obj



@app.get("/browse")
def browse(path: str = Query("", description="Relative directory path")):
    directory = safe_path(path)
    #print("directory=", directory)

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
    #print('input image before border shape', img.shape)
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
        ##
        #image = ImageOps.exif_transpose(image)
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

def crop_relative(image: Image.Image, rect):
        """
        rect = (x, y, width, height), all relative (0.0 - 1.0)
        """
        img_w, img_h = image.size

        rx, ry, rw, rh = rect

        left = round(rx * img_w)
        top = round(ry * img_h)
        right = round((rx + rw) * img_w)
        bottom = round((ry + rh) * img_h)

        return image.crop((left, top, right, bottom))

@app.post("/annotations")
async def get_polygon(request: Polygon):
# deze beter om te vormen naar alle fractions
     #def get_crop_rect(points,dim):



     def get_crop_rect(points):
                ## alles in fractions, dit is tov gehele imagebordered, see origin ook in fractions
                # om origin offset te berekenen moet vermenigvuldigd worden met bordered (eventueel rescaled) dim, niet met cropped dim. bv request.dim
                top = np.min([p.y for p in points]) # dit zijn selected points
                bot = np.max([p.y for p in points])
                left= np.min([p.x for p in points])
                right = np.max([p.x for p in points])
                #print('top,bot, left,right selected on bordered', top, bot, left,right)
                #print('points',points)

                border_width=(bot-top)/10
                #b#order_height=(bot-top)/10
                top_hough=np.maximum(0,(top-border_width)) # selected + small border
                bottom_hough=np.minimum(1,(bot+border_width))
                left_hough=np.maximum(0,left-border_width)
                right_hough=np.minimum(1,right+border_width) # nog alles in fractions
                #print('top,bot, left,right selected + 0.1  on bordered', top_hough, bottom_hough, left_hough,right_hough, "dim", request.dim)
                rect_hough=(left_hough,top_hough,right_hough,bottom_hough) #in fractions for selection of cropped bordered iage

                new_origin = Point(x=left_hough, y=top_hough) #in points fractions
                #new origin is in fractions
                #print('new origin before hough and relative to bordered and rect hough', new_origin, rect_hough)
                return(new_origin, rect_hough) # alles in points dus.

     pointsarr= (np.array(request.points))
     print('received point fractions', request.points)
     #print(np.array(request.dim))
          # self.rect_hough =(left_hough,top_hough,self.pil_img.size[0]-right_hough,self.pil_img.size[1]-bottom_houg
     # imagesh=ImageOps.crop(self.pil_img, self.rect_hough)
     corner_detector = HoughLineCornerDetector(
                 rho_acc = 2,
                 #rho_acc = maxWidth/50,
                 theta_acc = 180,
                 minthresh = 150,
                 #maxlines=20,
                 maxlines=7,
                 colorpicker=None,
                 shapepicker=None,
                 DEBUG_LEVEL=DEBUG_LEVEL
             )

     '''quadripoints_cornerdetector=corner_detector(resizedcropped, nearpoints=nearpoints)[0]'''
     #quadripoints_cornerdetector=corner_detector(resizedbordered, nearpoints=nearpoints)[0]
     #quadripoints_cornerdetector=corner_detector(resizedbordered, nearpoints=nearpoints)[0]
     nearpoints = np.array([
                 ((p.x )*request.dim.x, (p.y )*request.dim.y)
                              for p in request.points])
     nearpointsf = np.array([
                  ((p.x ), (p.y ))
                              for p in request.points])
    ## in hough ... X = np.array([[((point[0][0])+neworigin.x)/self.resize_hough, ((point[0][1])+neworigin.y)/self.resize_hough] for point in self._intersections])
     quadripoints_cornerdetector=corner_detector(imgbordered, nearpointsf=nearpointsf)[0]
     print('size imgborderd input to hough',imgbordered.shape)
     print('intersection quadri', quadripoints_cornerdetector)
     # this only relates to the rescaled cropped image
     # why rescale before hough?


     quadripoints=[p for p in quadripoints_cornerdetector]

     #print('quadrpoints', quadripoints, 'new origin', new_origin_crop_from_bordered)
     #quadripointsf=[(((p[0]/resize_ratio)+new_origin_crop_from_bordered.x)/np.array(imgbordered).shape[1], ((p[1]/resize_ratio)+new_origin_crop_from_bordered.y)/np.array(imgbordered).shape[0]) for p in quadripoints_cornerdetector]
     # volgende fout
     quadripointsf=[((p[0])/np.array(imgbordered).shape[1], (p[1])/np.array(imgbordered).shape[0]) for p in quadripoints_cornerdetector]
     #hier tov resized bordered
     print ('intersections bordered ',[intersection for intersection in quadripoints])
     #print('quadri type', [(i , i[0]) for i in quadripoints])



     quadrilistfull = [PointDto(x,y)  for (x,y) in quadripoints]
     #quadrilistfull = [PointDto(x,y) + new_origin_crop_from_bordered for (x,y) in quadripoints]
     #print("quadrilistfull", quadrilistfull)
     quadrilist = [PointDto(x,y) for (x,y) in quadripointsf]
     # print("quadrilist", quadrilist)
     quadrifullarray=[[p.x,p.y] for p in quadrilistfull]
     #print("quadrifullarray", quadrifullarray)

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
     #pts= np.array(list(dict_quadripoints.values()))
     pts = np.array(quadrifullarray)
     #pts = np.array(nearpoints)
     #pts=pts_near_rescaled
     print('pints for dewarping', pts)



     np_rect=np.float32([pts[0,:], pts[1,:],pts[2,:], pts[3,:]])
     aspect=np.linalg.norm(pts[1,:]-pts[0,:]+pts[2,:]-pts[3,:])/np.linalg.norm(pts[2,:]-pts[1,:]+pts[3,:]-pts[0,:])
     print('aspect ratio', aspect)
     ## new aspect ratio in output
     outHeight=round(outWidth/aspect)
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
     imgborderedsmall, resize_scl=resize_to_screen(imgbordered)
     #resizedborderedrgb= cv2.cvtColor(resizedbordered, cv2.COLOR_BGR2RGB)

     #warped = cv2.warpPerspective(imgborderedrgb, M, (outWidth, outHeight))
     #warped = cv2.warpPerspective(imgborderedrgb, M, (outWidth, outHeight))
     warped = cv2.warpPerspective(imgborderedrgb, M, (outWidth, outHeight))
     print('m',M, warped.shape, 'imageinput.shape', imgbordered.shape,imgborderedsmall.shape)
     #extract_OCR(warped)
     print('selected_points:', request.points,'x_border:', border_rel, 'y_border:', border_rel,'quadripoints:', quadrilist, 'warped size', warped.shape)
     df_rect1,extract_annotated=extract_OCR(warped)
     print('dfrect1', df_rect1)
     #rectpicker = Rectpicker(DEBUG_LEVEL=DEBUG_LEVEL)
     root=None
     rectpicker(np.array(df_rect1)[0:],root)







     return ({
     #return({

           "selected_points": request.points,
           "x_border": border_rel,
           "y_border": border_rel,
           "quadripoints": quadrilist,
           "deskewed_image": image_to_base64(Image.fromarray(warped)),
           "deskewed_annotated_image": image_to_base64(Image.fromarray(extract_annotated)),
           "bordered_image": image_to_base64(Image.fromarray(imgborderedsmall)),
            })

 #save_polygon()
class ClickRequest(BaseModel):
    x: float
    y: float

@app.post("/click")
def click(req: ClickRequest):

    print(req.x, req.y)
    clickresult=rectpicker.get_rect_on_mouse_clickf(req.x, req.y)
    clickresult=sanitize(clickresult)


    return {
        "status": "ok",
        #"message": f"Clicked at ({req.x}, {req.y})",
        "message": clickresult[0],
        "x": req.x,
        "y": req.y
    }

