#!/usr/bin/env python
######################################################################
# page_extractor.py - Proof-of-concept of id_doc_dewarping.
# Requires OpenCV (version 3 or greater),
#
######################################################################
# Author:  Martine Lapere
# Date:    july 2026
# License:
######################################################################

 #############################################################################################
 # code debug_show  from 'Matt Zucker on MIT licence'
 #############################################################################################



import cv2
import numpy as np
import math
import base64
import json
import pandas as pd
from pandas import json_normalize
from skimage.filters import threshold_otsu, gaussian
from skimage.color import rgb2gray
from skimage import data
from skimage.segmentation import active_contour
from matplotlib import pyplot as plt
from sklearn.cluster import KMeans
from itertools import combinations
from collections import defaultdict
from dataclasses import dataclass, field

from numpy import linalg as LA
from numpy.linalg import norm
from itertools import combinations
from processors import  rholineFromPoints, cart2z,fsigmoid,sigmoid, polar2z,z2polar,pol2cart,Brightness_enhancer,Saturation_enhancer, Rectpicker, contourFromRect,overlappingRelArea,Resizer, OtsuThresholder, FastDenoiser, Closer,Brightness_enhancer
import tkinter as tk
from tkinter import filedialog
from random import randint
import sys
sys.path.append('../dewarp/page_dewarp/')
from pathlib import Path
from pprint import pprint
from io import BytesIO
from datetime import datetime
from PIL import Image, ImageTk






# caution: path[0] is reserved for script path (or '' in REPL)

from page_dewarp import get_contours,resize_to_screen,get_page_extents,assemble_spans, merge_span_rect, merge_span,visualize_spans, ContourInfo, make_tight_mask
#get_contours = importlib.import_module("/Users/entropic/Desktop/vanessa/dewarp/page_dewarp/page_dewarp")
#from page_dewarp import get_contours
#from page_dewarp import resize_to_screen
#from page_dewarp import get_page_extents

import os

import pytesseract
import pandas as pd
import itertools


DEBUG_LEVEL = 1          # 0=none, 1=some, 2=lots, 3=all
DEBUG_OUTPUT = 'file'    # file, screen, both

outfile=''

#TEXT_MIN_WIDTH = 40      # min reduced px width of detected text contour
TEXT_MIN_WIDTH = 25      # min reduced px width of detected text contour, for small

#TEXT_MIN_HEIGHT = 15      # min reduced px height of detected text contour
TEXT_MIN_HEIGHT = 10      # min reduced px height of detected text contour for small
#TEXT_MIN_ASPECT = 1.5    # filter out text contours below this w/h ratio
TEXT_MIN_ASPECT = 1    # filter out text contours below this w/h ratio
#TEXT_MAX_THICKNESS = 10  # max reduced px thickness of detected text contour
TEXT_MAX_THICKNESS = 70  # max reduced px thickness of detected text contour
MAX_SPAN_GAP = 35



# eg
# if DEBUG_LE,EL >= 3:
#            debug_show(name, 0.1, 'thresholded', mask)


        
        
def debug_show(name, step, text, display):
    if DEBUG_OUTPUT != 'screen':
        filetext = text.replace(' ', '_')
        outfile = OUTDIR+ name + '_debug_' + str(step) + '_' + filetext + '.png'
        print('outfile', outfile)
        cv2.imwrite(outfile, display)
    if DEBUG_OUTPUT != 'file':
        image = display.copy()
        height = image.shape[0]
        cv2.putText(image, text, (16, height-16),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0,
                    (0, 0, 0), 3, cv2.LINE_AA)
        cv2.putText(image, text, (16, height-16),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0,
                    (255, 255, 255), 1, cv2.LINE_AA)
        cv2.imshow(WINDOW_NAME, image)
        while cv2.waitKey(5) < 0:
            pass



      
        
def box(width, height):
    return np.ones((height, width), dtype=np.uint8)
    
    
    
    
def showrect(df_rect,display,color, thickn):
    for i, rect in df_rect.iterrows():
        #print(np.array(rect), rect.shape)
        rect_array=np.array(rect)
        start_point=(rect_array[0],rect_array[1])
        end_point=((rect_array[0]+rect_array[2]),(rect_array[1]+rect_array[3]))
         
        #cv2.rectangle(small,start_point,end_point,(127,0,255),2)
        cv2.rectangle(display,start_point,end_point,color,thickn)

    

def extract_and_safe(filename, imageToOcr, reshapedImage, output_dir) :
    extract_OCR(imageToOCR)
    save_OCR_image(filename,reshapedImage,output_dir)


def extract_OCR(imageToOcr):
    extracted=imageToOcr
    root = tk.Tk()
    lang = "eng+nld+fra+spa+grc"
    config = "--psm 11 --oem 3"
    out_rgb = cv2.cvtColor(extracted, cv2.COLOR_BGR2RGB)
    otsu=OtsuThresholder(thresh1=8, DEBUG_LEVEL=DEBUG_LEVEL)
    benv=Brightness_enhancer(target=0.65)
    extractednorm1=benv(extracted)
    bens=Saturation_enhancer(target=0.5)
    extractednorm2=bens(extractednorm1)
    hsv=cv2.cvtColor(extractednorm1,cv2.COLOR_BGR2HSV)
    [H,S,V]=cv2.split(hsv)
    clahe = cv2.createCLAHE(clipLimit=0.5, tileGridSize=(64,64))
    clV = clahe.apply(255-V)
    hsvnormcontourhsv=cv2.merge([H,S,255*(1--clV)])
    hsvnormcontour=cv2.cvtColor(hsvnormcontourhsv, cv2.COLOR_HSV2BGR)
    imageotsu=otsu(hsvnormcontour)
    upper_gray=np.array([120,120,120])
    total_black=np.array([0,0,0])
    mask=cv2.inRange(extractednorm2,total_black,upper_gray)
    bg = cv2.medianBlur(hsvnormcontour, 51) # suitably large kernel to cover all text
    out = 255 - cv2.absdiff(hsvnormcontour, bg)
    small = resize_to_screen(hsvnormcontour)
    confidence_level=30
        #confidence_level_out=60
    confidence_level_out=60

    img_data = pytesseract.image_to_data(mask, lang=lang, config=config, output_type=pytesseract.Output.DATAFRAME)
    df_mask_out=img_data[img_data["conf"].astype(float)> confidence_level_out]
    df_mask_out=df_mask_out[df_mask_out["height"].astype(float)> 20]
    df_mask_out=df_mask_out[df_mask_out["width"].astype(float)> 40]
    print('df from mask, conf 60',df_mask_out)
    df_mask=df_mask_out.loc[:,"left":"text"]
    df_mask= df_mask.sort_values(by='top')
    df_mask.reset_index(drop=True, inplace=True)





    pagemask = cv2.erode(mask, box(4, 4), iterations=1)
    pagemask = cv2.dilate(pagemask, box(30, 12))

        #color = (255, 255, 0)
        #thickness=2
        ## add tessaract rects , NEW!!!!
    for i, rect in df_mask.iterrows():
        rect_array=np.array(rect)
        start_point=(rect_array[0],rect_array[1])
        end_point=(rect_array[0]+rect_array[2],rect_array[1]+rect_array[3])
        pagemask[rect_array[1]:rect_array[1]+rect_array[3],rect_array[0]:rect_array[0]+rect_array[2]]=255

    pagemask = cv2.dilate(pagemask, box(3, 4))
    pagemask = cv2.erode(pagemask, box(3, 3))
    pagemask=resize_to_screen(pagemask) # ?????
    cinfo_list = get_contours('name', small, pagemask, 'text', DEBUG_LEVEL=DEBUG_LEVEL)
    #print('cinfo type good', cinfo_list[0])

    spans = assemble_spans('name', small, pagemask, cinfo_list, DEBUG_LEVEL=DEBUG_LEVEL)
    spansout=[]
    for span in reversed(spans):
            spanmerged=merge_span(span, DEBUG_LEVEL=DEBUG_LEVEL)
            [xmin,ymin,width,height]=spanmerged[0].rect
            start_point=(xmin,ymin)
            end_point=(xmin+width,ymin+height)
            spansout.append(spanmerged)
    df_span = pd.DataFrame(data=None, columns=df_mask.columns)
    df_rect2=df_span.copy(deep=False)

    for span in reversed(spansout):
                cinfo=span[0]

                [xmin,ymin,width,height]=cinfo.rect

                if (width < TEXT_MIN_WIDTH or
                    height < TEXT_MIN_HEIGHT or
                    width < TEXT_MIN_ASPECT*height):
                    continue
                #xmin=np.max([0,xmin-5]) # werkt
                start_point=(xmin,ymin)
                end_point=((xmin+width),(ymin+height))
                #cv2.rectangle(small,start_point,end_point,(127,0,255),2)
                #cv2.rectangle(small,start_point,end_point,(220,250,0),2)
                new_image_small = (small[ymin:(ymin+height), xmin:(xmin+width)])
                start_point=(xmin*2,ymin*2)
                end_point=((xmin+width)*2,(ymin+height)*2)
                new_image = (hsvnormcontour[ymin*2:(ymin+height)*2, xmin*2:(xmin+width)*2])
                #new_image_mask=(maskTess[ymin*2:(ymin+height)*2, xmin*2:(xmin+width)*2])





                data = pytesseract.image_to_string(new_image, lang=lang, config='--psm 6')
                if (data): # if no data,no details

                    if data[0:-1] in df_mask["text"].values:

                        continue # string already found

                    row={"left":cinfo.rect[0]*2,"top":cinfo.rect[1]*2,"width":cinfo.rect[2]*2,"height":cinfo.rect[3]*2  ,"conf":None, "text":data[0:-1]
                    }

                    new_pd = pd.DataFrame([row])



                textbgr = pytesseract.image_to_data(new_image, lang=lang, config=config, output_type=pytesseract.Output.DATAFRAME)

                confidence_level=40
                if textbgr.empty:
                    print('no data parts')
                    continue

                else:
                    df2_select=textbgr[textbgr["conf"].astype(float)> confidence_level]
                    ## ook minimal height en width
                    df2_select=df2_select[df2_select["height"].astype(float)> 20]
                    df2_select=df2_select[df2_select["width"].astype(float)> 40]
                    if df2_select.empty:
                        continue


                    #print('df_rect2 borders',xmin,ymin,)
                    df_temp=df2_select.loc[:,"left":"text"]
                    df_temp["top"]=df_temp["top"]+ymin*2
                    df_temp["left"]=df_temp["left"]+xmin*2
                    # hier stukjes van spam
                    #for index,row in df_temp.iterrows():
                       # print('df details', row[-1])

                    df_list = [df_rect2, df_temp]
                    df_list = filter(lambda x: not x.empty, df_list)

                    df_rect2 = pd.concat(list(df_list), axis=0, ignore_index=True)
                    #df_rect2=pd.concat([df_rect2,df_temp])
                    # only save full span if part with confidence

                    df_span=pd.concat([df_span,new_pd], axis=0, ignore_index=True)
                    if(DEBUG_LEVEL>2):
                        print('spans in df_span:')
                        print(df_span)

                        print('spans parts in df_rect2:')
                        print(df_rect2)

            #########df_rect2=pd.concat([df_rect2,df_mask])

    df_rect2= df_rect2.sort_values(by='top')
    df_span= df_span.sort_values(by='top')
    df_mask.reset_index(drop=True, inplace=True)
    print('from mask', df_mask)
            #cv2.waitKey(0)
    df_rect2.reset_index(drop=True, inplace=True)
            #df_rect2.reset_index(drop=True)
            #df_rect1.reset_index(drop=True)
    df_span.reset_index(drop=True, inplace=True)
    print('from spans details' ,df_rect2)

    if (len(df_mask)>0): # if no data,no details
        for i, row in df_mask.iterrows():
        #print(np.array(rect), rect.shape)
            text=row["text"]
            if text in df_rect2["text"].values:
                print('to drop in mask', row)
                df_mask.drop(index=i, inplace=True)

            elif row["conf"]< 60:
                df_mask.drop(index=i,inplace=True)
            else:
                continue

                #continue # string already found
        #HIER


    print ('restof df_mask', df_mask)



    df_list = [df_rect2, df_mask]
    df_list = filter(lambda x: not x.empty, df_list)

    df_rect2 = pd.concat(list(df_list), axis=0, ignore_index=True)
    #df_rect2 = pd.concat([df for df in df_list if not df.empty])


    #df_rect2=pd.concat([df_rect2,df_mask], axis=0, ignore_index=True)

    showrect(df_rect2,hsvnormcontour,(150,250,100),2)

    #showrect(df_rect1,hsvnormcontour,(150,250,100),2)
    showrect(df_span,hsvnormcontour,(150,250,100),2)
    showrect(df_mask,hsvnormcontour,(150,50,250),2)
    #cv2.waitKey(0)


    df_list = [df_rect2, df_span]
    df_list = filter(lambda x: not x.empty, df_list)

    df_rect1 = pd.concat(list(df_list), axis=0, ignore_index=True)

    #df_rect1=pd.concat([df_span,df_rect2], axis=0, ignore_index=True)
    df_rect1 = df_rect1.drop_duplicates(subset=['text'], keep='first')
    ## annotate extracted image

    #print('df_rect1 results', df_rect1)
    mrzlines=df_rect1.loc[(df_rect1['left'] < 170 ) & (df_rect1['top'] > 1100 )&(df_rect1['width'] >  1000)].sort_values("top")
    print('mrz line?', mrzlines)
    print('extracted size', extracted.shape)
    df_rect1["left"]=df_rect1["left"]/extracted.shape[1]
    df_rect1["width"]=df_rect1["width"]/extracted.shape[1]
    df_rect1["top"]=df_rect1["top"]/extracted.shape[0]
    df_rect1["height"]=df_rect1["height"]/extracted.shape[0]
    rectpicker = Rectpicker(DEBUG_LEVEL=DEBUG_LEVEL)
    rectpicker(np.array(df_rect1)[0:],root)
    #cv2.setMouseCallback("boxed", rectpicker.get_rect_on_mouse_click)
    #cv2.waitKey(500)
    return(df_rect1, hsvnormcontour)


    
def extract_text(filename, imageToExtract, reshapedImage, output_dir):
    extracted=imageToExtract
    root = tk.Tk()
    DEBUG_LEVEL=4
    reshapedImage=reshapedImage
    filename=filename
    current_datetime = datetime.now()
    current_datetime_string = current_datetime.strftime("%Y-%m-%d_%H-%M-%S")
    
    OUTDIR=output_dir
    

   
   
    ''' hier is begin van extracted to decode text'''
    
   
   
   
    if(DEBUG_LEVEL>3):
        cv2.imshow("Extracted page", imageToExtract)
    

    # predict tesseract
    lang = "eng+nld+fra+spa+grc"
    config = "--psm 11 --oem 3"
    out_rgb = cv2.cvtColor(extracted, cv2.COLOR_BGR2RGB)
    
    
    otsu=OtsuThresholder(thresh1=8, DEBUG_LEVEL=DEBUG_LEVEL)
   
  
    benv=Brightness_enhancer(target=0.65)
    extractednorm1=benv(extracted)
    
    bens=Saturation_enhancer(target=0.5)
    
    extractednorm2=bens(extractednorm1)
    
    
    #cv2.imshow('otsu thresholded',imageotsu)
    hsv=cv2.cvtColor(extractednorm1,cv2.COLOR_BGR2HSV)
    [H,S,V]=cv2.split(hsv)
    clahe = cv2.createCLAHE(clipLimit=0.5, tileGridSize=(64,64))
    clV = clahe.apply(255-V)
        
    hsvnormcontourhsv=cv2.merge([H,S,255*(1--clV)])
    hsvnormcontour=cv2.cvtColor(hsvnormcontourhsv, cv2.COLOR_HSV2BGR)
    #cv2.imshow('clahe thresholded normalised',hsvnormcontour)
    if(DEBUG_LEVEL>3):
        cv2.imwrite('output/deskewed_normalised.jpg', hsvnormcontour)
        #image=hsvnormcontour
            # predict tesseract
    imageotsu=otsu(hsvnormcontour)
    upper_gray=np.array([120,120,120])
    total_black=np.array([0,0,0])
    mask=cv2.inRange(extractednorm2,total_black,upper_gray)
    #imageotsumask=cv2.bitwise_and(hsvnormcontour,hsvnormcontour,mask=mask)
    if DEBUG_LEVEL> 3:
        imageotsumask=cv2.bitwise_and(hsvnormcontour,hsvnormcontour,mask=mask)
        cv2.imshow('black selected', 255-imageotsumask)
        imageotsumask=cv2.dilate(imageotsumask, (30,5), iterations=3)
        imageotsumask=cv2.dilate(imageotsumask, box(5,5), iterations=4)
        cv2.imshow('black selected dilated 1', 255-imageotsumask)
        #cv2.waitKey(0)
        imageotsumask=cv2.dilate(imageotsumask, box(0,10), iterations=1)
        cv2.imshow('black selected dilated 2', 255-imageotsumask)
        #imageotsumask=cv2.dilate(imageotsumask, box(5,0), iterations=3)
        #cv2.imshow('black selected dilated 3', 255-imageotsumask)
        
  
 
    bg = cv2.medianBlur(hsvnormcontour, 51) # suitably large kernel to cover all text
    out = 255 - cv2.absdiff(hsvnormcontour, bg)
    if DEBUG_LEVEL> 3:
        cv2.imshow('text from bg ',out)
   
        cv2.imshow('mask bordered ',mask)
    #imageotsumask=cv2.bitwise_and(hsvnormcontour,hsvnormcontour,mask=mask)
    if DEBUG_LEVEL> 3:
        cv2.imshow('mixed otsu selected', 255-imageotsumask)
   
    #cv2.waitKey(0)
    small = resize_to_screen(hsvnormcontour)
    if DEBUG_LEVEL> 4:
        cv2.imshow('small normed contour 1',small)
        cv2.imshow('mask raw', mask)
        print('waiting for key')   
        cv2.waitKey(0)
       
    confidence_level=30
    #confidence_level_out=60
    confidence_level_out=60
    
    img_data = pytesseract.image_to_data(mask, lang=lang, config=config, output_type=pytesseract.Output.DATAFRAME)
    #maskTess=mask.copy()
    #print(img_data[ img_data["conf"].astype(float)> confidence_level]["text"])
    #df_select=img_data[img_data["conf"].astype(float)> confidence_level]
    #df_select2=df_select[df_select["height"].astype(float)> 20]
    df_mask_out=img_data[img_data["conf"].astype(float)> confidence_level_out]
    df_mask_out=df_mask_out[df_mask_out["height"].astype(float)> 20]
    df_mask_out=df_mask_out[df_mask_out["width"].astype(float)> 40]
    if DEBUG_LEVEL>3:
        print('df from mask, conf 60',df_mask_out)
    #print('details', df_mask_out)
    #df_rect=df_mask_out.loc[:,"left":"text"]
    
    df_mask=df_mask_out.loc[:,"left":"text"]
    #df_rect.reindex()
    df_mask= df_mask.sort_values(by='top')
    df_mask.reset_index(drop=True, inplace=True)
    #print( 'df_mask after reindex')
    #print( df_mask)
    if DEBUG_LEVEL>3:
        # hier alle > conf=20, in de selct enkel deze > 60
        df_mask_out.to_csv('output/output_mask_ocr_otsu.csv', index=False)
    #cv2.waitKey(0)
    
    #pagemask, page_outline = get_page_extents(small)
    # overwrite page_dewarp mask
    #mask1=resize_to_screen(mask)
    print('image size to dewarp', mask.shape)
    #pagemask = cv2.erode(mask1, box(4, 4), iterations=2)
    pagemask = cv2.erode(mask, box(4, 4), iterations=1)
    #pagemask = cv2.dilate(pagemask, box(30, 8)) ###new
    pagemask = cv2.dilate(pagemask, box(30, 12))
    #pagemask = cv2.dilate(pagemask, box(15, 5))
    #pagemask = cv2.erode(pagemask, box(3, 1))
    color = (255, 255, 0)
    thickness=2
    ## add tessaract rects , NEW!!!!
    for i, rect in df_mask.iterrows():
        rect_array=np.array(rect)
        start_point=(rect_array[0],rect_array[1])
        end_point=(rect_array[0]+rect_array[2],rect_array[1]+rect_array[3])
        pagemask[rect_array[1]:rect_array[1]+rect_array[3],rect_array[0]:rect_array[0]+rect_array[2]]=255

    pagemask = cv2.dilate(pagemask, box(3, 4))
    #pagemask = cv2.erode(pagemask, box(3, 1))
    pagemask = cv2.erode(pagemask, box(3, 3))
    if DEBUG_LEVEL> 3:
        cv2.imshow('pagemask rect from Tessaract',pagemask)
        print('waiting for key')
        cv2.waitKey(0)
    pagemask=resize_to_screen(pagemask)
    
 
    cinfo_list = get_contours('name', small, pagemask, 'text', DEBUG_LEVEL=DEBUG_LEVEL)
    #print('cinfo type good', cinfo_list[0])
    
   
       
    spans = assemble_spans('name', small, pagemask, cinfo_list, DEBUG_LEVEL=DEBUG_LEVEL)
    
    
    spansout=[]
    for span in reversed(spans):
        spanmerged=merge_span(span, DEBUG_LEVEL=DEBUG_LEVEL)
        [xmin,ymin,width,height]=spanmerged[0].rect
        start_point=(xmin,ymin)
        end_point=(xmin+width,ymin+height)
        color = (255, 255, 0)
        thickness=2
        #cv2.rectangle(small, start_point, end_point, color, thickness)
        #spans.remove(span)
        #spanmerged=merge_span(span)
        spansout.append(spanmerged)
    if (DEBUG_LEVEL>2):
        visualize_spans('spansout', small, pagemask, spansout, DEBUG_LEVEL=DEBUG_LEVEL)
 
        #print('reduced spans from', len(spans) ,'to', len(spansout))
 

   
    
    
    #of enkel de columns:
    df_span = pd.DataFrame(data=None, columns=df_mask.columns)
    df_rect2=df_span.copy(deep=False)
   
    for span in reversed(spansout):
        cinfo=span[0]
       
        [xmin,ymin,width,height]=cinfo.rect
       
        if (width < TEXT_MIN_WIDTH or
            height < TEXT_MIN_HEIGHT or
            width < TEXT_MIN_ASPECT*height):
            continue
        #xmin=np.max([0,xmin-5]) # werkt
        start_point=(xmin,ymin)
        end_point=((xmin+width),(ymin+height))
        #cv2.rectangle(small,start_point,end_point,(127,0,255),2)
        #cv2.rectangle(small,start_point,end_point,(220,250,0),2)
        new_image_small = (small[ymin:(ymin+height), xmin:(xmin+width)])
        start_point=(xmin*2,ymin*2)
        end_point=((xmin+width)*2,(ymin+height)*2)
        new_image = (hsvnormcontour[ymin*2:(ymin+height)*2, xmin*2:(xmin+width)*2])
        #new_image_mask=(maskTess[ymin*2:(ymin+height)*2, xmin*2:(xmin+width)*2])
       
        
     
        if(DEBUG_LEVEL>2):
            cv2.namedWindow("boxed", cv2.WINDOW_NORMAL)
            cv2.imshow('boxed', new_image)
            print('waiting for key')
            cv2.waitKey(0)
      
        data = pytesseract.image_to_string(new_image, lang=lang, config='--psm 6')
        if (data): # if no data,no details
 
            if data[0:-1] in df_mask["text"].values:

                continue # string already found
        
            row={"left":cinfo.rect[0]*2,"top":cinfo.rect[1]*2,"width":cinfo.rect[2]*2,"height":cinfo.rect[3]*2  ,"conf":None, "text":data[0:-1]
            }
        
            new_pd = pd.DataFrame([row])
          
       
      
        textbgr = pytesseract.image_to_data(new_image, lang=lang, config=config, output_type=pytesseract.Output.DATAFRAME)
    
        confidence_level=40
        if textbgr.empty:
            print('no data parts')
            continue
  
        else:
            df2_select=textbgr[textbgr["conf"].astype(float)> confidence_level]
            ## ook minimal height en width
            df2_select=df2_select[df2_select["height"].astype(float)> 20]
            df2_select=df2_select[df2_select["width"].astype(float)> 40]
            if df2_select.empty:
                continue

  
            #print('df_rect2 borders',xmin,ymin,)
            df_temp=df2_select.loc[:,"left":"text"]
            df_temp["top"]=df_temp["top"]+ymin*2
            df_temp["left"]=df_temp["left"]+xmin*2
            # hier stukjes van spam
            #for index,row in df_temp.iterrows():
               # print('df details', row[-1])
            
            df_list = [df_rect2, df_temp]
            df_list = filter(lambda x: not x.empty, df_list)

            df_rect2 = pd.concat(list(df_list), axis=0, ignore_index=True)
            #df_rect2=pd.concat([df_rect2,df_temp])
            # only save full span if part with confidence
            
            df_span=pd.concat([df_span,new_pd], axis=0, ignore_index=True)
            if(DEBUG_LEVEL>2):
                print('spans in df_span:')
                print(df_span)
            
                print('spans parts in df_rect2:')
                print(df_rect2)
                
    #########df_rect2=pd.concat([df_rect2,df_mask])

    df_rect2= df_rect2.sort_values(by='top')
    df_span= df_span.sort_values(by='top')
    df_mask.reset_index(drop=True, inplace=True)
    print('from mask', df_mask)
    #cv2.waitKey(0)
    df_rect2.reset_index(drop=True, inplace=True)
    #df_rect2.reset_index(drop=True)
    #df_rect1.reset_index(drop=True)
    df_span.reset_index(drop=True, inplace=True)
    print('from spans details' ,df_rect2)
    
    
    ###  print here df_mask and connection to df_rect
    if (len(df_mask)>0): # if no data,no details
        for i, row in df_mask.iterrows():
        #print(np.array(rect), rect.shape)
            text=row["text"]
            if text in df_rect2["text"].values:
                print('to drop in mask', row)
                df_mask.drop(index=i, inplace=True)
                
            elif row["conf"]< 60:
                df_mask.drop(index=i,inplace=True)
            else:
                continue
                
                #continue # string already found
        #HIER
            
          
    print ('restof df_mask', df_mask)
  
 
    
    df_list = [df_rect2, df_mask]
    df_list = filter(lambda x: not x.empty, df_list)

    df_rect2 = pd.concat(list(df_list), axis=0, ignore_index=True)
    #df_rect2 = pd.concat([df for df in df_list if not df.empty])
    
  
    #df_rect2=pd.concat([df_rect2,df_mask], axis=0, ignore_index=True)
  
    showrect(df_rect2,hsvnormcontour,(150,250,100),2)
    
    #showrect(df_rect1,hsvnormcontour,(150,250,100),2)
    showrect(df_span,hsvnormcontour,(150,250,100),2)
    showrect(df_mask,hsvnormcontour,(150,50,250),2)
    #cv2.waitKey(0)

    
    
    df_list = [df_rect2, df_span]
    df_list = filter(lambda x: not x.empty, df_list)

    df_rect1 = pd.concat(list(df_list), axis=0, ignore_index=True)
    
    #df_rect1=pd.concat([df_span,df_rect2], axis=0, ignore_index=True)
    df_rect1 = df_rect1.drop_duplicates(subset=['text'], keep='first')
    print('df_rect1 results', df_rect1)
    mrzlines=df_rect1.loc[(df_rect1['left'] < 170 ) & (df_rect1['top'] > 1100 )&(df_rect1['width'] >  1000)].sort_values("top")
    print('mrz line?', mrzlines)
  
    print('hsvnorm and small', hsvnormcontour.shape, small.shape)
    #cv2.imshow('boxed_small', small)
    #cv2.destroyWindow(shapepicker.get_window_name())
    cv2.namedWindow("boxed", cv2.WINDOW_NORMAL)
    cv2.imshow('boxed', hsvnormcontour)
    cv2.waitKey(0)
    #cv2.resizeWindow("boxed",  550, 350)
    cv2.resizeWindow("boxed",  700, 450)
  
    #cv2.waitKey(0)
    rectpicker = Rectpicker(DEBUG_LEVEL=DEBUG_LEVEL)
    rectpicker(np.array(df_rect1)[0:],root)
    cv2.setMouseCallback("boxed", rectpicker.get_rect_on_mouse_click)
    cv2.waitKey(500)
    

    reshapedImage["df_rect"]=df_rect1.to_json(orient='records')
    
    nameout = Path(filename).stem+current_datetime_string

   
    with open(OUTDIR+nameout+'.json', 'w') as f:
        json.dump(reshapedImage,f)
    
    
    
  
    if(DEBUG_LEVEL >3):
# Considering "json_list.json" is a JSON file
#### check readback and display json output file
        with open(OUTDIR+nameout+'.json') as fd:
            json_data = json.load(fd)
            pprint(json_data["crop"])
            df_read=json.loads(json_data["df_rect"])
           
            df_read=pd.DataFrame(df_read)
            imagetocropX64 =json_data["imageBordered"]
            
            imagetocrop=base64.b64decode(imagetocropX64) # drop eol
            
           
            jpg_as_np = np.frombuffer(imagetocrop, dtype=np.uint8)
            
            img = cv2.imdecode(jpg_as_np, flags=1)
            if (DEBUG_LEVEL>2):
                print('len imagetocrop before and jpg and plain', len(imagetocropX64), len(imagetocrop), img.shape)
            
            
            
          
            print('image cropped size', img.shape)
            cropped=json_data["crop"]
            
            lu = (round(cropped[0][0]*img.shape[1]), round(cropped[0][1]*img.shape[0]))
            ru = (round(cropped[1][0]*img.shape[1]), round(cropped[1][1]*img.shape[0]))
            rd = (round(cropped[2][0]*img.shape[1]), round(cropped[2][1]*img.shape[0]))
            ld = (round(cropped[3][0]*img.shape[1]), round(cropped[3][1]*img.shape[0]))
            cv2.line(    img, lu, ru, (255, 0, 255),2)
            cv2.line(    img, ru, rd, (255, 0, 255),2)
            cv2.line(    img, rd, ld, (255, 0, 255),2)
            cv2.line(    img, ld, lu, (255, 0, 255),2)
            cv2.imshow('decoded', img)
            
            print( 'crop points', json_data["crop"] , lu,ru,rd,ld)
            
            #print(len(imagetocrop))
            #cv2.imshow('decoded', imagetocrop)
            #print(Image.open(imagetocrop).type) # is list
            cv2.waitKey(0)
            #print('len(imageBorderedrecovered):', len(imagetocrop))
            #io.BytesIO(base64.decodebytes(bytes(base64_str, "utf-8")))
            #df_read = pd.DataFrame.from_dict(json_data["df_rect"], orient='index')
         
            #print('df_rect type', df_read.type)
        
            pprint(df_read)

            
    #cv2.imshow('input to tessarct', hsvnormcontour)
    #cv2.waitKey(0)
    
    
  
   
    print('outfile for mrz is this', outfile)
    cv2.waitKey(3300)
    #print(df_select2)
    if DEBUG_LEVEL >2:
        df_rect1.to_csv(OUTDIR+'output_ocr_otsu.csv', index=False)
    print('press q on window to exit')
    while(1):
        k = cv2.waitKey(33)
        #print(k)
        if k== ord('q'):   # Esc key to stop
            print('seen q')
            exit()
        elif k==-1:  # normally -1 returned,so don't print it
            continue
        else:
            continue
    #cv2.waitKey('\x1b')
   
   
    
    
 
