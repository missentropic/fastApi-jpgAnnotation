import cv2
import math
from scipy import ndimage
import tkinter as tk
from PIL import Image, ImageTk, ImageOps
import numpy as np
import colorsys
from skimage.segmentation import active_contour
from dataclasses import dataclass, field

import pytesseract


@dataclass
class PointDto:
        x: float
        y: float
    
        def toarray(self):
            res = list([x,y])
            return(res)

class PolygonPoints:


        
        
        def __init__(self):
            """Override initializer which can accept iterable"""
            #self.points = list[PointDto]=[]
            self.points =[]
            self.centered_points=[]
            self.points_sorted=[]
            self.polygon_closed = False
            self.close_threshold_px=10
            self.top_left_corner=[]
            self.export_origin=PointDto(0,0)
            
        
        def addPoint(self,x: float, y: float):
            #val scale = calculateScale()
            # first point is top left, it is saved for further processing
            if (not len(self.points)>0):
                self.top_left_corner=PointDto(x , y )
            self.points.append(PointDto(x , y ))
            
            #print('self.points from PolygonPoints.addpoint', self.points)
            self.sort_on_angle()
            
            
            
        def deleteNearest(self,x: float, y: float):
            if not self.points: return
            idx, _ = min(
            enumerate(self.points),
            key=lambda item: math.hypot(item[1].x - x, item[1].y - y))
            # the [1] refers to the value instead of the index
            self.points.pop(idx)
            print('self.points na delete', self.points)
            
            
        def center_points(self):
            if not len(self.points)>1:     # 🔥 this was missing
                self.centered_points = []
                return
            else:
                cx = sum(p.x for p in self.points) / len(self.points)
                cy = sum(p.y for p in self.points) / len(self.points)
                print('cx and cy', cx,cy)
            ### hier fout
                print("RAW POINTS:", [(p.x, p.y) for p in self.points])
                
                self.centered_points = [PointDto(p.x - cx, p.y - cy) for p in self.points]
                print('centroid coordinates', self.centered_points)
            
            
        def sort_on_angle(self):
            self.center_points()
            self.points_sorted=[]
            if( len(self.centered_points)>2):
            # nu calculate angle. met z en poolvcordinates
                #print('shape', np.array( [([p.x , p.y]) for p in self.centered_points]).shape)
                polar_angles=     z2polar(cart2z(np.array( [([p.x , p.y]) for p in self.centered_points])))[1,:]
                #polar_angles=     atan2( [([p.x , p.y]) for p in self.centered_points])[1,:]
                #print('polar angles', polar_angles[1,:])
                #print('polar angles', polar_angles)
                angle_idx=np.argsort(polar_angles)
                #print(self.points[angle_idx[0]])
                idx=0
                while (idx<len(angle_idx)):
                    self.points_sorted.append(self.points[angle_idx[idx]])
                
                    idx+=1
              
                self.points=self.points_sorted
               # print('points sorted', self.points_sorted)
            
        
         
        def clear(self):
            """Remove all points."""
            self.points.clear()
            
        def reshuffle_points(self):
            #print('reshuffel input points from reshuffel', self.points)
            iteration = 0
            while (not self.is_near_first(self.points[0].x, self.points[0].y) and iteration<4):
                    self.points.append(self.points.pop(0))
                    iteration+=1
            # next is het sort by angle.
            
            #print('reshuffeld points', self.points)
            
            
        def set_export_origin(self, left,top):
            self.export_origin=PointDto(top,left)
            
                
        def exportPoly(self, event):
            self.reshuffle_points()
            coords = [[p.x-self.export_origin(x), p.y-self.export_origin(y)] for p in self.points]
            #rotate list so left is first point
            self.reshuffle_points()
           
            print("Points after converting to array : " + str(coords))
        
            
            return(coords)

        def set_polygon_closed():
            self.polygon_closed=True
            
        def reset_polygon_closed():
            self.polygon_closed=False
            
        def __len__(self):
            return len(self.points)

        def __repr__(self):
            return f"Polygon({self.points})"
            
            
        def is_near_first(self, view_x: float, view_y: float) -> bool:
            if not self.points:  # same as isEmpty()
                return False

            #scale = self.calculate_scale()
            scale=1
            #first = self.points[0]
            first= self.top_left_corner

            fx = first.x * scale
            fy = first.y * scale

            dx = fx - view_x
            dy = fy - view_y

            return dx * dx + dy * dy <= self.close_threshold_px * self.close_threshold_px
            
            
        def is_near_corner(self, view_x: float, view_y: float) -> bool:
            if not self.points:
                return False

            scale = 1  # or self.calculate_scale()

            for corner in self.points:
                fx = corner.x * scale
                fy = corner.y * scale

                dx = fx - view_x
                dy = fy - view_y

                if dx * dx + dy * dy <= self.close_threshold_px ** 2:
                    return True   # exit loop + function immediately

            return False
    

                
        def redraw(self, canvas):
            
            canvas.delete("annotation")

            #scale = self.calculate_scale()
            scale=1

            # Draw polygon lines
            #for i in range(len(self.points) - 1):
            if (len(self.points)<1):
                return()
            self.reshuffle_points()
            #hier gaat het mis
            print('self points after reshuffle', self.points)
            for i in range(len(self.points) - 1):
                p1 = self.points[i]
                p2 = self.points[i + 1]

                canvas.create_line(
                    p1.x * scale, p1.y * scale,
                    p2.x * scale, p2.y * scale,
                    fill="lime",
                    width=2,
                    tags="annotation"
                )

            # Close polygon if needed
            if self.polygon_closed and len(self.points) == 4:
                first = self.points[0]
                last = self.points[-1]

                canvas.create_line(
                    last.x * scale, last.y * scale,
                    first.x * scale, first.y * scale,
                    fill="lime",
                    width=2,
                    tags="annotation"
                )

            # Draw points as red circles
            for p in self.points:
                x = p.x * scale
                y = p.y * scale

                canvas.create_oval(
                    x - 4, y - 4,
                    x + 4, y + 4,
                    fill="red",
                    outline="",
                    tags="annotation"
                )
          
          
          
          
class RotationCorrector:
    def __init__(self, DEBUG_LEVEL=2):
        self.output_process = output_process

    def __call__(self, image):
        img_before = image.copy()
        
        img_edges = cv2.Canny(img_before, 50, 150, apertureSize=3)
        lines = cv2.HoughLinesP(
            img_edges, 
            1, 
            math.pi / 90.0, 
            100, 
            minLineLength = 100,
            maxLineGap = 5
        )
        if (DEBUG_LEVEL>3):
            print("Number of lines found in rotationCorrector:", len(lines))
        
        def get_angle(line): 
            x1, y1, x2, y2 = line[0]
            return math.degrees(math.atan2(y2 - y1, x2 - x1))

        median_angle = np.median(np.array([get_angle(line) for line in lines]))
        img_rotated = ndimage.rotate(
            img_before, 
            median_angle, 
            cval = 255,
            reshape = False
        )

        print("Angle is {}".format(median_angle))
        
        if (DEBUG_LEVEL>3):
            cv2.imwrite('output/10. tab_extract rotated.jpg', img_rotated)

        return img_rotated


class Resizer:
    """Resizes image.

    Params
    ------
    image   is the image to be resized
    height  is the height the resized image should have. Width is changed by similar ratio.

    Returns
    -------
    Resized image
    """
    def __init__(self, resizeHeight = True, maxDim = 1280, DEBUG_LEVEL=2):
        self.resizeHeight=resizeHeight
        self._resizeDim=maxDim
        #self._height = np.round(maxHeight)
        #self._width = np.round(maxWidth)
        self.DEBUG_LEVEL=DEBUG_LEVEL
        self._ratio=1


    def __call__(self, image):
      
        if(self.resizeHeight):
            self._ratio = round(self._resizeDim / image.shape[0], 3)
           
        else:
            print('resize width')
            self._ratio = round(self._resizeDim / image.shape[1], 3)
        self._width=int(image.shape[1] * self._ratio)
        self._height=int(image.shape[0] * self._ratio)
        
        dim = (int(self._width), int(self._height))
      
        
        #if image.shape[0] <= self._height:
        if self._ratio >= 1:
            resized = cv2.resize(image, dim, interpolation = cv2.INTER_LINEAR)
        else:
            resized = cv2.resize(image, dim, interpolation = cv2.INTER_AREA)
        if (self.DEBUG_LEVEL>2):
            print('image shape entry resizer processors', image.shape, 'max height', self._height)
            #cv2.imwrite('output/resized.jpg', resized)
            print('resized image shape processors', resized.shape)
       
        return resized, self._ratio
        
   
   


class OtsuThresholder:
    """Thresholds image by using the otsu method

    Params
    ------
    image   is the image to be Thresholded

    Returns
    -------
    Thresholded image
    """
    def __init__(self, thresh1 = 0, thresh2 = 255,DEBUG_LEVEL=2):
        self.thresh1 = thresh1
        self.thresh2 = thresh2
        self.DEBUG_LEVEL=DEBUG_LEVEL


    def __call__(self, image):
        image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        T_, thresholded = cv2.threshold(image, self.thresh1, self.thresh2, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        if (self.DEBUG_LEVEL>2):
            cv2.imwrite('output/thresholded.jpg', thresholded)
        
        return thresholded


class FastDenoiser:
    """Denoises image by using the fastNlMeansDenoising method

    Params
    ------
    image       is the image to be Thresholded
    strength    the amount of denoising to apply

    Returns
    -------
    Denoised image
    """
    def __init__(self, strength = 7,DEBUG_LEVEL=2):
        self._strength = strength
        self.DEBUG_LEVEL=DEBUG_LEVEL


    def __call__(self, image):
        temp = cv2.fastNlMeansDenoising(image, h = self._strength)
        if (self.DEBUG_LEVEL>2): cv2.imwrite('output/denoised.jpg', temp)
        return temp
        
        
class GrabCutEdgeDetector:
   

    """Params
    ------
    image       is the image to be Thresholded
    lower_color : numpy array given the lower color eg np.array([40,0,60])
    upper_color : numpy array given the upper color eg np.array([150,255,255])
    

    Returns
    -------
    edge of the grabcut mask using lower_color to upper_color as foreground
    
    """
    
    def __init__(self, image,lower_color, upper_color,output_process = False,DEBUG_LEVEL=2):
    
        self.image=image
        self.output_process = output_process
        self.lower_color=lower_color
        self.upper_color=upper_color
        self.DEBUG_LEVEL=DEBUG_LEVEL
       


    def __call__(self):
        
        hsv= cv2.cvtColor(self.image, cv2.COLOR_BGR2HSV)
            #h, s, v = cv2.split(hsv)
           
        lower_blue=self.lower_color
        upper_blue=self.upper_color
        mask = cv2.inRange(hsv, lower_blue, upper_blue)
        ret,inv_mask=cv2.threshold(mask,127,255,cv2.THRESH_BINARY_INV)
        bgdModel = np.zeros((1,65),np.float64)
        fgdModel = np.zeros((1,65),np.float64)
            #mask[mask == 0] = cv2.GC_PR_BGD
            #mask[mask == 255] = cv2.GC_FGD
        mask[inv_mask == 0] = cv2.GC_PR_BGD
        mask[inv_mask == 255] = cv2.GC_PR_FGD
        #Run grabcut
        cGB =image*mask[:,:,np.newaxis]
        mask, bgdModel, fgdModel= cv2.grabCut(image,mask,None,bgdModel,fgdModel,5,cv2.GC_INIT_WITH_MASK)
        if (self.DEBUG_LEVEL>2):  cv2.imwrite('output/grabcut.jpg', temp)
        return temp
        
        
        sobeltotx = np.zeros(mask.shape, dtype='f')
        sobeltoty = np.zeros(mask.shape, dtype='f')
        sobeltot= np.zeros(mask.shape, dtype='f')
        for masker in np.unique(mask):
             if(max(np.unique(mask)))>1:
                mask_part = np.where((mask==masker),0,1).astype('uint8')
                #sobelx = cv2.Sobel(mask_part,cv2.CV_64F,1,0,ksize=7)
                #sobely = cv2.Sobel(mask_part,cv2.CV_64F,0,1,ksize=7)
                sobelx = cv2.Sobel(mask_part,cv2.CV_64F,1,0,ksize=5)
                sobely = cv2.Sobel(mask_part,cv2.CV_64F,0,1,ksize=5)
                sobeltotx=np.add(sobeltotx,np.abs(sobelx))
                sobeltoty=np.add(sobeltoty,np.abs(sobely))
                sobeltotx[sobeltotx<5]=5
                sobeltoty[sobeltoty<5]=5
                sobeltotxlog=np.ceil(np.log2(sobeltotx))
                sobeltotylog=np.ceil(np.log2(sobeltoty))
                sobeltot=np.add(sobeltotxlog,sobeltotylog)
                sobeltot=np.where(sobeltot<12, 0, 255).astype(np.uint8)
        
        return [sobeltot]
            
        
        


class Closer:
    def __init__(self, kernel_size = 3, iterations = 10, output_process = False,DEBUG_LEVEL=3):
        self._kernel_size = kernel_size
        self._iterations = iterations
        #self.output_process = output_process
        self._DEBUG_LEVEL=DEBUG_LEVEL


    def __call__(self, image):
        kernel = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE, 
            (self._kernel_size, self._kernel_size)
        )
        closed = cv2.morphologyEx(
            image, 
            cv2.MORPH_CLOSE, 
            kernel,
            iterations = self._iterations
        )
        if(self._DEBUG_LEVEL>3):
            cv2.imwrite('output/closed.jpg', closed)
        return closed


class Opener:
    def __init__(self, kernel_size = 3, iterations = 25, output_process = False,DEBUG_LEVEL=3):
        self._kernel_size = kernel_size
        self._iterations = iterations
        self.output_process = output_process
        self._DEBUG_LEVEL=DEBUG_LEVEL

    def __call__(self, image):
        kernel = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE, 
            (self._kernel_size, self._kernel_size)
        )
        opened = cv2.morphologyEx(
            image, 
            cv2.MORPH_OPEN,
            kernel,
            iterations = self._iterations 
        )
        if(self._DEBUG_LEVEL>3):
            cv2.imwrite('output/opened.jpg', opened)
        return opened
        
        
class Brightness_enhancer:
    def __init__(self, target = 0.8, beta = 0, output_process = False,DEBUG_LEVEL=3):
        self._min_bright = target
        self._beta=beta
        self.output_process = output_process
        self._DEBUG_LEVEL=DEBUG_LEVEL

    def __call__(self, image):
       
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        h, s, v = cv2.split(hsv)
       
       
     
        #final_hsv = cv2.merge((h, s, v))
        
        [cols, rows,_] = image.shape
        brightness = np.sum(v) / (255 * cols * rows)
        low=np.mean(np.min(v))
       
        ratio = brightness / self._min_bright
        beta=-1/ratio*low
        '''if ratio >= 1:
            print("Image brightness ok")
            return image
        '''
        if ratio >= 0:#always
            vnew=cv2.convertScaleAbs(v, alpha = 1 / ratio)
            final_hsv = cv2.merge((h, s, vnew))
            final=cv2.cvtColor(final_hsv, cv2.COLOR_HSV2BGR)
            if(self._DEBUG_LEVEL>3):
                cv2.imwrite('output/brightadjusted.jpg', final)
    # Otherwise, adjust brightness to get the target brightness
            return final
            
            
class Saturation_enhancer:
    def __init__(self, target = 0.3, beta = 0, output_process = False,DEBUG_LEVEL=3):
        self._target_sat = target
        self._beta=beta
        self.output_process = output_process
        self._DEBUG_LEVEL=DEBUG_LEVEL

    def __call__(self, image):
       
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        h, s, v = cv2.split(hsv)
       
       
     
        #final_hsv = cv2.merge((h, s, v))
        
        [cols, rows,_] = image.shape
        saturation = np.sum(s) / (255 * cols * rows)
        ratio = saturation / self._target_sat
        '''if ratio >= 1:
            print("Image brightness ok")
            return image
         '''
        if ratio > 0:
            snew=cv2.convertScaleAbs(s, alpha = 1 / ratio, beta = 0)
            final_hsv = cv2.merge((h, snew, v))
            final=cv2.cvtColor(final_hsv, cv2.COLOR_HSV2BGR)
            if(self._DEBUG_LEVEL>3):
                cv2.imwrite('output/saturationadjusted.jpg', final)
    # Otherwise, adjust brightness to get the target brightness
            return final
        
        

        
        



class EdgeDetector:
    #def __init__(self, output_process = False, add_color_selector= False):
    def __init__(self, output_process = False,shapepicker =None, DEBUG_LEVEL=2):
        self.output_process = output_process
        #self.add_color_selector=add_color_selector
        self._shapepicker=shapepicker
        self.DEBUG_LEVEL=DEBUG_LEVEL
      
        self._preprocessor = [
            Closer(output_process = output_process, iterations=10,kernel_size=5),
            ]

    def __call__(self, image, thresh1 = 50, thresh2 = 130, apertureSize = 3, colorpicker = None , nearpoints=None):
        # van de gewone edge worden contouren genomen.
        # daarna een dubbele edge via grabcut selectie.
        self.nearpoints=nearpoints
        if(self.DEBUG_LEVEL>2):
            print('image size in edge detector', image.shape)
            print('tap key to continue', image.shape)
            cv2.waitKey(0)
       
        kernel = np.ones((2, 2), np.uint8)
      
        imagecontour=image.copy() #filtered
        
        
        
        hsvcontour=cv2.cvtColor(imagecontour, cv2.COLOR_BGR2HSV)
        [H,S,V]=cv2.split(hsvcontour)
        
        def sigm(x):
            return 1 / (1 + math.exp(-x))
        
        
        
        ### dit beter na de selectie van shape

        
        # enkel een Closer gaat niet, moet 2 maal
        for processor in self._preprocessor:
            image = processor(image)
    
        #image_gray=otsu(image_diff)
        #
        if self.DEBUG_LEVEL>2:
            cv2.imwrite('output/edgesface1blur.jpg', image)
            #cv2.imwrite('output/otsuthres.jpg', imageotsu)
            
  
        edges = cv2.Canny(image, thresh1, thresh2, apertureSize = apertureSize)
        edges = cv2.dilate(edges, kernel, iterations=1)
        edgescontour=edges.copy()
        #print("we are at line 622")
        if self.DEBUG_LEVEL>2:
            cv2.imwrite('output/edgesnocolour.jpg', edgescontour)
        #edgescontour=edges.copy()
        # tweede maal
        for processor in self._preprocessor:
            image = processor(image)

       
        '''if isinstance(self._shapepicker, Shapepicker):
            contourpts=self._shapepicker.get_corner_pts()
            centroidXCoordinate = int(np.mean(contourpts, axis=0)[0])
            centroidYCoordinate = int(np.mean(contourpts, axis=0)[1])
            
            
        else:
        
            self._laplacian = cv2.Laplacian(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY),cv2.CV_64F)
        
        
            contours, hierarchy = cv2.findContours(self._laplacian.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        #cv2.namedWindow("contourw", cv2.WINDOW_AUTOSIZE)
        
            cntsel = contours[0]
        ### temp
      
        
            maxmoment=0
            contours = sorted(contours, key=cv2.contourArea,reverse=True)
        
            for cnt in contours:
                if (self.DEBUG_LEVEL>3):
                    print ('contours shape', cnt.shape)
                convexHull = cv2.convexHull(cnt)
            
                perimeterc = cv2.arcLength(convexHull, True)
             
                if perimeterc > 300:
                    moment = cv2.moments(convexHull)
                    if moment['m00']> maxmoment:
                        if self.DEBUG_LEVEL>2:
                            print('area, maxarea', moment['m00'], maxmoment)
                        maxmoment=moment['m00']
                        maxcnt=cnt
                     
                        centroidXCoordinate = int(moment['m10'] / moment['m00'])
                        centroidYCoordinate = int(moment['m01'] / moment['m00'])
                   
            convexHull = cv2.convexHull(maxcnt)
            cv2.drawContours(imagecontour, [convexHull], -1, (0, 255, 255), 2)
          
        '''
      
        ## de kleur is kleur van central point of max contour, or of shae if shapepicker
        
      
        colorpickercontour=Colorpicker(image)
        #colorpickercontour.set_color_range_on_xy(x=centroidXCoordinate,y=centroidYCoordinate)
        if isinstance(self._shapepicker, Shapepicker):
            colorpickercontour.set_color_range_on_shapePicker(self._shapepicker)
        else:
            if len(self.nearpoints)> 3:
                colorpickercontour.set_color_range_on_nearpoints(self.nearpoints)

            
        # aparte behandeling indien een manueel kleuroint werd gekozen
        if isinstance(colorpicker, Colorpicker):
            lower_color=colorpicker._get_lower_color_boundery()
            upper_color=colorpicker._get_upper_color_boundery()
               
        # deze steeds True, want erboven gedefinieerd
        elif isinstance(colorpickercontour, Colorpicker):
            lower_color=colorpickercontour._get_lower_color_boundery()
            upper_color=colorpickercontour._get_upper_color_boundery()
         
            hsv= cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
         
            
            #lower_blue = np.array([40,0,60])
            #upper_blue = np.array([150,255,255])'''
            if(self.DEBUG_LEVEL>1):
                print('lower en upper before adjust', lower_color, upper_color)
            if lower_color[0]> 140:
                lower_color1=np.copy(lower_color)
                lower_color1[0] = 0
                mask1 = cv2.inRange(hsv, lower_color1, upper_color)
                if self.DEBUG_LEVEL>4:
                    cv2.imwrite('output/mask11.jpg', mask1)
                upper_color1=np.copy(upper_color)
                upper_color1[0] = 179
                mask2 = cv2.inRange(hsv, lower_color, upper_color1)
                if self.DEBUG_LEVEL>2:
                    cv2.imwrite('output/mask12.jpg', mask2*255)
                mask=mask1+mask2
            else:
                
                mask = cv2.inRange(hsv, lower_color, upper_color)
            if self.DEBUG_LEVEL>4:
                print('lower en upper after adjust', lower_color, upper_color)
                cv2.imwrite('output/mask1.jpg', mask)
            ret,inv_mask=cv2.threshold(mask,127,255,cv2.THRESH_BINARY_INV)
            bgdModel = np.zeros((1,65),np.float64)
            fgdModel = np.zeros((1,65),np.float64)
            mask[inv_mask == 0] = cv2.GC_PR_BGD
            mask[inv_mask == 255] = cv2.GC_PR_FGD
       
        #Run grabcut
            cGB =image*mask[:,:,np.newaxis]
            mask, bgdModel, fgdModel= cv2.grabCut(image,mask,None,bgdModel,fgdModel,5,cv2.GC_INIT_WITH_MASK)
            if self.output_process:
                cv2.imwrite('output/grabcutmask.jpg', mask*255)
            cGB =image*mask[:,:,np.newaxis]
            sobeltotx = np.zeros(mask.shape, dtype='f')
            sobeltoty = np.zeros(mask.shape, dtype='f')
            sobeltotxlog = np.zeros(mask.shape, dtype='f')
            sobeltotylog = np.zeros(mask.shape, dtype='f')
            sobeltot = np.zeros(mask.shape)
            for masker in np.unique(mask):
              if(max(np.unique(mask)))>1:
                mask_part = np.where((mask==masker),0,1).astype('uint8')
                #sobelx = cv2.Sobel(mask_part,cv2.CV_64F,1,0,ksize=7)
                #sobely = cv2.Sobel(mask_part,cv2.CV_64F,0,1,ksize=7)
                sobelx = cv2.Sobel(mask_part,cv2.CV_64F,1,0,ksize=5)
                sobely = cv2.Sobel(mask_part,cv2.CV_64F,0,1,ksize=5)
                sobeltotx=np.add(sobeltotx,np.abs(sobelx))
                sobeltoty=np.add(sobeltoty,np.abs(sobely))
                sobeltotx[sobeltotx<5]=5
                sobeltoty[sobeltoty<5]=5
                sobeltotxlog=np.ceil(np.log2(sobeltotx))
                sobeltotylog=np.ceil(np.log2(sobeltoty))
                sobeltot=np.add(sobeltotxlog,sobeltotylog)
                #print('unique sobeltot ',np.unique( sobeltot))
                sobeltot=np.where(sobeltot<np.ceil(np.max(sobeltot)-4), 0, 255).astype(np.uint8)
                #nu nog smooth
                #sobeltot = cv2.Canny(sobeltot, 50, 150, apertureSize=3)
                # nu enkel selectie op grabcut
                edges=np.maximum(edges,sobeltot)
                #edges=sobeltot
                #edges=sobeltot
                if self.DEBUG_LEVEL>3:
                    cv2.imwrite('output/grabcut.jpg', cGB)
        else:
            if self.DEBUG_LEVEL>1:
                print('no color picker onject defined in EdgeDetector')
        edges = cv2.dilate(edges, kernel, iterations=1)
        if self.DEBUG_LEVEL>2:
            cv2.imwrite('output/edges.jpg', edges),
            
        return edges
        
        
class Shapepicker:


    
        
        
   
    #def __init__(self , imagePick, resize_ratio,  window_name,root,display_scale=0.5, DEBUG_LEVEL = 2):
    def __init__(self , imagePick,  window_name,root,display_scale=0.5, DEBUG_LEVEL = 2):
        
        
        self._add_shape_selector = True
        self._imagepick=imagePick
        #self._resize_ratio=resize_ratio # eerste resize van imagePick naar imageBordered
        self._display_scale=display_scale  # vor user interface, display and pick
        #self._offset_cropped=[0.0,0.0] #ratio gebruikt??
        self._window_name=window_name
        self.DEBUG_LEVEL=DEBUG_LEVEL
        self.rect_hough_fractions_bordered=[0.0,0.0, 0.0,0.0] # left top right bottom
      
        ## deze 3 inits zijn niet nodig met nieuwe PolygonPoints
        self.pgPoints=PolygonPoints()
        self.borderPoints=PolygonPoints()
        
    
      
        self._corners=np.zeros([4,2],dtype=int)
        self._cornersPick=np.zeros([4,2],dtype=int)
        ## alles in fraction of imagePick
        self._cornersf=np.zeros([4,2],dtype=float)
        self._corner_offset=PointDto(0,0)
        ###self._count=0
        self.running=True
        ''' vervangen door tk windiow
        cv2.namedWindow(self._window_name,cv2.WINDOW_AUTOSIZE)
     
        cv2.imshow(self._window_name, self._imagepick)
        #cv2.waitKey(0)
        cv2.setMouseCallback(self._window_name, self.set_shape_on_mouse_click)'''
        
        # ---------- TK WINDOW ----------
        #self.root = tk.Toplevel()
        self.root=root
        self.root.title(self._window_name)
        
        # create canvas FIRST
        self.canvas = tk.Canvas(self.root, cursor="cross")
        self.canvas.pack()

        # Convert OpenCV BGR → RGB
        image_rgb = self._imagepick[:, :, ::-1]
        self.pil_img = Image.fromarray(image_rgb)

       
            
        if self._display_scale != 1:
            w, h = self.pil_img.size
            self.pil_img = self.pil_img.resize(
                (int(w * self._display_scale), int(h * self._display_scale))
            )

        self.tk_img = ImageTk.PhotoImage(self.pil_img)
        
        # deze zijn dus bordered * resize_ratio * display_scale
        
        self.canvas.image = self.tk_img
        print('shapepicker display image size ', self.tk_img.width(), self.tk_img.height())
      
# NOW draw
        
        self.canvas.config(width=self.tk_img.width(),
                   height=self.tk_img.height())

        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.tk_img)
        # Mouse click binding
        '''while self.running:
            self.root.update_idletasks()
            self.root.update()'''

        ''' einde vervanging '''
        self.canvas.bind("<Button-1>", self.set_shape_on_left_click)
        #self.canvas.bind("<Button-3>", self.on_right_click)   # Windows/Linux
        self.canvas.bind("<Button-2>", self.set_shape_on_right_click)   # Mac
        '''while self.running:
            self.root.update_idletasks()
            self.root.update()'''
        #self.root.mainloop()
        
    def __call__(self):
       
        #self._lower_color = np.array([40,0,60]),
        #self._upper_color = np.array([150,255,255])
        print('shape picker called')
        self.canvas.bind("<Button-1>", self.set_shape_on_left_click)
        #self.canvas.bind("<Button-3>", self.on_right_click)   # Windows/Linux
        self.canvas.bind("<Button-2>", self.set_shape_on_right_click)   # Mac
        #self.canvas.bind("<KeyPress>", self.on_key_press)
        #self.root.mainloop()
       
      
        return()
        
    def stop(self):
        self.running=False
        #self.root.destroy()
        #self.root.withdraw()
        #self.root.destroy()
        #self.root.update()
        self.root.quit()
                #return()
        


           

            
            
    def set_shape_on_left_click(self, event):
        x, y = event.x, event.y
        
        if self.DEBUG_LEVEL >= 3:
            print(f"Click at: {x}, {y} from set_shape_on_left_click")
        self.canvas.delete("annotation")
        if (not (self.pgPoints.polygon_closed) and len(self.pgPoints) >= 4 and self.pgPoints.is_near_corner(x, y)) :
            
            self.pgPoints.polygon_closed = True
            print('closing near corner is ', self.pgPoints.polygon_closed)
            self.pgPoints.redraw(self.canvas)
        elif (not self.pgPoints.polygon_closed):
                        #addPoint(ix, iy)
        # store point in polygon
            self.pgPoints.addPoint(x, y)
            if self.DEBUG_LEVEL >= 3:
                print('points after set_shape_on_left_click addPoint before redraw',self.pgPoints)
            self.pgPoints.redraw(self.canvas)
        if ( self.pgPoints.polygon_closed):
        # Stop processing clicks
            self.canvas.unbind("<Button-1>")
            self.canvas.bind("<Button-1>", self.pgPoints.exportPoly)
            # Stop processing clicks
            self.canvas.unbind("<Button-2>")
            print(' shape selected')
            # topy boty leftx rightx zijn uitersten van image select points, je vegt dan nog border toe.
            # en bekomt zo top_hough bot_hough left_hough right_hough. dit zijn dus de borders waarbinnen de hough mag zoeken
            topy = np.min([p.y for p in self.pgPoints.points])
            boty = np.max([p.y for p in self.pgPoints.points])
            leftx= np.min([p.x for p in self.pgPoints.points])
            rightx = np.max([p.x for p in self.pgPoints.points])
            border_width=int(boty-topy)/10
            
            '''top=(topy-border_width)/self.tk_img.height()
            bottom=(boty+border_width)/self.tk_img.height()
           
            left=(leftx-border_width)/self.tk_img.width()
            right=(rightx+border_width)/self.tk_img.width()'''
            top_hough=(topy-border_width)
            bottom_hough=(boty+border_width)
            left_hough=(leftx-border_width)
            right_hough=(rightx+border_width)
            # er moet nog een kleine border overbrijven rond de selection
            if(self.DEBUG_LEVEL> 3):
                print('border from selection to Hough:  (border_width),top, bottom, left, right', '(',border_width,')',top_hough, bottom_hough, left_hough, right_hough)
        
            print('size pil image', self.pil_img.size )
            
            ## deze is verkee
            self.rect_hough_borders =(left_hough,top_hough,self.pil_img.size[0]-right_hough,self.pil_img.size[1]-bottom_hough)
            
            if(self.DEBUG_LEVEL>2):
                print('border for hough: left top right botttom', self.rect_hough_borders)
                imagesh=ImageOps.crop(self.pil_img, self.rect_hough)
                cropshow = np.array(imagesh)[:, :, ::-1].copy()
                print('size pil from cropped popup show', imagesh.size)
           
                cv2.imshow('cropped selection',cropshow)
            
           
            self.rect_hough_fractions_bordered= [left_hough/self.pil_img.size[0],top_hough/self.pil_img.size[1],right_hough/self.pil_img.size[0],bottom_hough/self.pil_img.size[1] ]
            
           
 
            print('new bordered selection top left bottom right ',self.get_rect_hough_fractions_bordered())
            
            
            #self.root.destroy()
            self.root.protocol("WM_DELETE_WINDOW", self.stop)


            
    def set_shape_on_right_click(self, event):
        x, y = event.x, event.y

        if self.DEBUG_LEVEL >= 2:
            print(f"Right click at: {x},{y}")

        if not self.pgPoints.points:
            return

     
        self.pgPoints.deleteNearest(x,y)
        self.pgPoints.redraw(self.canvas)
        
    
    
    def on_key_press(event):
    # event.state bitmask: Control key is bit 0x4 on most systems
        print('key pressed seen')
        ctrl_pressed = (event.state & 0x4) != 0
        if ctrl_pressed and event.keysym.lower() == "s":
            self.pgPoints.exportPoly()

        

    def get_rect_hough_fractions_bordered(self):
               return(np.array(self.rect_hough_fractions_bordered))
               ##left top right bottom
    
    def get_corner_pts_rescaled(self,sorted=True, dim=None):
        if (not dim):
            dim= self._imagepick.shape
        print ('dim', dim)
        #self._corners_abs=np.array(([(p.x/self.pil_img.size[0], p.y/self.pil_img.size[1]) for p in self.pgPoints.points]))
        self._corners_abs=(self.get_corner_pts()* np.array([dim[1],dim[0]])).astype(np.int64)
        #.astype(np.int64)
        return(self._corners_abs)

    def get_corner_pts(self,sorted=True, dim=None):
        print('self.pgPoints.points',self.pgPoints.points , self._display_scale)
        self._corners=np.array(([(p.x/(self._display_scale), p.y/(self._display_scale)) for p in self.pgPoints.points]))
        #self._corners=([(p.x/(self._display_scale), p.y/(self._display_scale)) for p in self.pgPoints.points]).astype(np.int64)
        if (not dim):
            dim= self._imagepick.shape
        print ('dim', dim)
       
        self._cornersf=np.array(([(p.x/self.pil_img.size[0], p.y/self.pil_img.size[1]) for p in self.pgPoints.points]))
        #self._cornersf=np.array(([(p.x*dim[1]/self.pil_img.size[0], p.y*dim[0]/self.pil_img.size[1]) for p in self.pgPoints.points])).astype(np.int64)
        self._corners_to_dim=np.array(([(p.x*dim[1]/self.pil_img.size[0], p.y*dim[0]/self.pil_img.size[1]) for p in self.pgPoints.points])).astype(np.int64)
             
        print('self.corners on  imagebordered', self._corners)
        print('self.cornersf on resized image', self._cornersf)
        mean_pt = np.mean(self._corners,axis=0)
        c_centered = np.array(self._corners-mean_pt)
             
        polar_coord=z2polar(cart2z(c_centered))
        #print('testpicker nmeans', polar_coord)
        #de eerste coordinaat is de linker bovenhoek
        polar_diff=(polar_coord[1,:]-polar_coord[1,0])
        polar_add=(polar_diff<0)*2*np.pi
        if (sorted==True):
            angle_idx=np.argsort(polar_diff+polar_add)
        else:
            angle_idx=np.argsort(polar_diff)
        #print('sort of selected points', angle_idx)

        polar_coord=polar_coord.T[angle_idx].T
        self._corners=self._corners[angle_idx]
        self._cornersf=self._cornersf[angle_idx]
      
        return(self._cornersf )
        

        
        
    def get_corner_lines(self, bordered_nearpoints):
        #bordered_corners=self.get_corner_pts_offset()
        bordered_corners=bordered_nearpoints
        
        #print('processing corners ',self._corners[1], self._corners[2] , rholineFromPoints(self._corners[1],self._corners[2]))
        prelines=[rholineFromPoints(bordered_corners[i],bordered_corners[i+1]) for i in range(3)]
        prelines.append(rholineFromPoints(bordered_corners[3],bordered_corners[0]))
        return(prelines)
        

        
    def get_window_name(self):
        return(self._window_name)

        
       
    
    
class Colorpicker:
    def __init__(self ,image, add_color_selector= False, DEBUG_LEVEL = 2):
        
        self._add_color_selector = add_color_selector
        self._image=image
        self._hsv= cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        self._lower_color = np.array([40,0,60]),
        self._upper_color = np.array([150,255,255])
        #cv2.imwrite('output/edgesface1blur.jpg', image)
        self._imageBGMasked=self._hsv
        self.DEBUG_LEVEL=DEBUG_LEVEL
  
        
        
    def __call__(self):
       
        self._lower_color = np.array([40,0,60]),
        self._upper_color = np.array([150,255,255])
        print('color picker called')
        return()
        
    def set_color_range_on_xy(self,x,y):
            radius = 100
            ### we nemen gemiddelde color around this point, want reeds closed
            HSVpoint=self._hsv[y,x]
            if(self.output_process):
                print('hsv pixel chosen', HSVpoint)
           
            mask = np.zeros(self._hsv.shape[:2], np.uint8)
            mask = cv2.circle(mask, (x,y), radius, (255,255,255), -1)
            HSVmean = cv2.mean(self._hsv, mask=mask)
            HSVpoint=np.array(HSVmean[:3])
            
        #HUE, SATURATION, AND VALUE (BRIGHTNESS) RANGES. TOLERANCE COULD BE ADJUSTED.
        # Set range = 0 for hue and range = 1 for saturation and brightness
        # set upper_or_lower = 1 for upper and upper_or_lower = 0 for lower
            hue_upper = self._get_boundaries(HSVpoint[0], 20, 0, 1)
            hue_lower = self._get_boundaries(HSVpoint[0], 20, 0, 0)
            saturation_upper = self._get_boundaries(HSVpoint[1], 15, 1, 1)
            saturation_lower = self._get_boundaries(HSVpoint[1], 15, 1, 0)
            value_upper = self._get_boundaries(HSVpoint[2], 40, 1, 1)
            value_lower = self._get_boundaries(HSVpoint[2], 40, 1, 0)
            self._upper_color =  np.array([hue_upper, saturation_upper, value_upper])
            self._lower_color =  np.array([hue_lower, saturation_lower, value_lower])
            print('lower selected',  self._lower_color)
            return()

    def set_color_range_on_shapePicker(self,shapepicker):
            #radius = 100
            ### we nemen gemiddelde color around this point, want reeds closed
            #polypts=shapepicker.get_corner_pick_pts()

            polypts=shapepicker.get_corner_pts_rescaled(self._image.shape)


            print('polypoints shape', polypts.shape, polypts)
            mask = np.zeros((self._image.shape[0], self._image.shape[1]),dtype=np.uint8)
            cv2.fillConvexPoly(mask, polypts, 1)
            #cv2.imshow('mask grabcut', mask*255)
            #mask = mask > 0 # To convert to Boolean
            #mask= cv2.fillPoly(image, pts=[polypts], color=(0, 0, 0)
            #HSVpoint=self._hsv[y,x]
            

            
                
            #mask = cv2.inRange(hsv, lower_blue, upper_blue)
            #mask = np.zeros(self._hsv.shape[:2], np.uint8)
            #mask = cv2.circle(mask, (x,y), radius, (255,255,255), -1)
            HSVmean = cv2.mean(self._hsv, mask=mask)
            HSVpoint=np.array(HSVmean[:3])
            
            
        #HUE, SATURATION, AND VALUE (BRIGHTNESS) RANGES. TOLERANCE COULD BE ADJUSTED.
        # Set range = 0 for hue and range = 1 for saturation and brightness
        # set upper_or_lower = 1 for upper and upper_or_lower = 0 for lower
            hue_upper = self._get_boundaries(HSVpoint[0], 20, 0, 1)
            hue_lower = self._get_boundaries(HSVpoint[0], 20, 0, 0)
            saturation_upper = self._get_boundaries(HSVpoint[1], 15, 1, 1)
            saturation_lower = self._get_boundaries(HSVpoint[1], 15, 1, 0)
            value_upper = self._get_boundaries(HSVpoint[2], 40, 1, 1)
            value_lower = self._get_boundaries(HSVpoint[2], 40, 1, 0)
            self._upper_color =  np.array([hue_upper, saturation_upper, value_upper])
            self._lower_color =  np.array([hue_lower, saturation_lower, value_lower])
            print('lower selected',  self._lower_color)
            #mask=self._imageBGMasked
            mask = cv2.inRange(self._hsv, self._lower_color, self._upper_color)
            #print('mask', mask)
            #cv2.imshow('mask grabcut', mask*255)
            #self._imageBGMasked[hsv in range]=HSVpoint
            return()

    def set_color_range_on_nearpoints(self,nearpoints):
                        #radius = 100
                        ### we nemen gemiddelde color around this point, want reeds closed
                        #polypts=shapepicker.get_corner_pick_pts()

            #polypts=nearpoints
            #polypts=np.array([(round(p.x), round(p.y)) for p in nearpoints])
            #nearpoints=np.array([(round(p.x), round(p.y)) for p in nearpoints])
            polypts=nearpoints

            print('polypoints shape', polypts.shape, polypts)
            mask = np.zeros((self._image.shape[0], self._image.shape[1]),dtype=np.uint8)
            cv2.fillConvexPoly(mask, polypts, 1)






            HSVmean = cv2.mean(self._hsv, mask=mask)
            HSVpoint=np.array(HSVmean[:3])


            #HUE, SATURATION, AND VALUE (BRIGHTNESS) RANGES. TOLERANCE COULD BE ADJUSTED.
            # Set range = 0 for hue and range = 1 for saturation and brightness
            # set upper_or_lower = 1 for upper and upper_or_lower = 0 for lower
            hue_upper = self._get_boundaries(HSVpoint[0], 20, 0, 1)
            hue_lower = self._get_boundaries(HSVpoint[0], 20, 0, 0)
            saturation_upper = self._get_boundaries(HSVpoint[1], 15, 1, 1)
            saturation_lower = self._get_boundaries(HSVpoint[1], 15, 1, 0)
            value_upper = self._get_boundaries(HSVpoint[2], 40, 1, 1)
            value_lower = self._get_boundaries(HSVpoint[2], 40, 1, 0)
            self._upper_color =  np.array([hue_upper, saturation_upper, value_upper])
            self._lower_color =  np.array([hue_lower, saturation_lower, value_lower])
            print('lower selected',  self._lower_color)
            #mask=self._imageBGMasked
            mask = cv2.inRange(self._hsv, self._lower_color, self._upper_color)
            return()
  
    def set_color_range_on_mouse_click(self, event,x,y,flags,param):
        if event == cv2.EVENT_LBUTTONDOWN:
            self.set_color_range_on_xy(x,y)
            return()
    
    
    
    def _get_lower_color_boundery(self):
        return(self._lower_color)
       
    def _get_upper_color_boundery(self):
        return(self._upper_color)

        
    def _get_boundaries(self,value, tolerance, ranges, upper_or_lower):
        if ranges == 0:
            # set the boundary for hue
            boundary = 179 # but circular
            if upper_or_lower == 1: #upper
                if(value + tolerance > boundary):
                    value=boundary
                else:
                    value=value+tolerance
            else: # lower
                if(value - tolerance < 0):
                    value=value-tolerance +180  # circular
                    #value=0
                else:
                    value=value-tolerance
        elif ranges == 1:
            # set the boundary for saturation and value
            boundary = 255
            if upper_or_lower == 1: #upper boundery
                value = min(value + tolerance, boundary)
            else: # lower boundery
                value = max(value - tolerance, 0)
        return value
        


class ClickEvent:
    def __init__(self ,image, add_color_selector= False, DEBUG_LEVEL = 2):
            
            self._add_color_selector = add_color_selector
            #self._image=image
            self._hsv= cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
            self.DEBUG_LEVEL=DEBUG_LEVEL
            cv2.setMouseCallback('image', click_event)
            


    def click_event(event, x, y, flags, params):
      
        # checking for left mouse clicks
        if event == cv2.EVENT_LBUTTONDOWN:
      
            # displaying the coordinates
            # on the Shell
            #print(x, ' ', y)
      
            # displaying the coordinates
            # on the image window
            font = cv2.FONT_HERSHEY_SIMPLEX
            cv2.putText(img, str(x) + ',' +
                        str(y), (x,y), font,
                        1, (255, 0, 0), 2)
            cv2.imshow('image', image)
      
        # checking for right mouse clicks
        if event==cv2.EVENT_RBUTTONDOWN:
      
            # displaying the coordinates
            # on the Shell
            print(x, ' ', y)
      
            # displaying the coordinates
            # on the image window
            font = cv2.FONT_HERSHEY_SIMPLEX
            b = img[y, x, 0]
            g = img[y, x, 1]
            r = img[y, x, 2]
            cv2.putText(img, str(b) + ',' +
                        str(g) + ',' + str(r),
                        (x,y), font, 1,
                        (255, 255, 0), 2)
            cv2.imshow('image', image)
      

  
'''
def rholineFromPoints(P1, P2, nbrp):
        
    
    pointbuff=np.linspace(P1,P2,num=nbrp)
    return pointbuff

    # setting mouse handler for the image
    # and calling the click_event() function
 '''
 
 
 
 
class Rectpicker:
    def __init__(self , DEBUG_LEVEL = 3):
        self.DEBUG_LEVEL=DEBUG_LEVEL
        
        
        
    def __call__(self,Rects,tkroot):
       
        #self._lower_color = np.array([40,0,60]),
        #self._upper_color = np.array([150,255,255])
        print('Rect picker called')
        self.Rects=Rects
        print('self rects received in Rectpicker',self.Rects.shape)
        self.root=tkroot
        
    
    def set_xy(self, x,y):
        self.x=x
        self.y=y
        #print(x,y)
        return
        
    def check_point_in_rect(self,xp,yp, rect):
        x=int(rect[0])
        y=int(rect[1])
        width=int(rect[2])
        height=int(rect[3])
        conf=rect[4]
        text=rect[5]
        #print('min distance', np.min(np.array([xp-x, yp-y, x+width-xp, y+height-yp])))
        #(x,y,width,height,conf,text)=rect
        if(xp<x):
            return(False)
        if(yp<y):
            return(False)
        if(xp> x+width):
            return(False)
        if(yp>y+height):
            return(False)
        #print('min distance', text, np.min(np.array([xp-x, yp-y, x+width-xp, y+height-yp])))
        '''self.root.withdraw()
        self.root.clipboard_clear()
        self.root.clipboard_append(text)'''
        return(text, np.min(np.array([xp-x, yp-y, x+width-xp, y+height-yp])), conf)
        '''p1 = np.matrix([[x, y]])
        p2 = np.matrix([[x + width, y]])
        p3 = np.matrix([[x, y + height]])
        p4 = np.matrix([[x + width, y + height]])
        contour = list(np.array([[p1, p2, p3, p4]]))
        result = cv2.pointPolygonTest(contour, (xp,yp), False)
        '''
        
        

           
            
    def get_rect_on_mouse_click(self, event,x,y,flags,param):
       
        rectList=[]
        if event == cv2.EVENT_LBUTTONDOWN:
            self.set_xy(x,y)
            print('xy', x, y)
            mindist=2000
            for rect in self.Rects:
                outrect=self.check_point_in_rect(self.x,self.y, rect)
                if(outrect):
                    if(outrect[1]<mindist):
                        mindist=outrect[1]
                        rectList=outrect # text ,distance en conf
                    
           
                
            
                
                    #self.root.withdraw()
                    self.root.clipboard_clear()
           
                    self.root.clipboard_append(rectList[0])
                    print(rectList[0],rectList[2] )
            cv2.waitKey(1000)
            return(rectList)
        else:
            return
            
  
  
  ######### general functions
 
        
  
def thetaFromPoints(ptn1,ptn2):
            z=cart2z(np.array([ptn1-ptn2]))
            theta=np.angle(z)
            
            

def cross_prod_homog(vec1,vec2):
    outvec_homog=np.cross(vec1,vec2)
    outvec_norm=outvec_homog/outvec_homog[2]
    return(outvec_norm)
    
    
    
def fromHomog(arrayin):
        for row in range(arrayin.shape[0]):
           
            arrayin[row]=arrayin[row]/arrayin[row][2]
        return(arrayin[:,:2])

def toHomog(arrayin):
    outarray=np.ones([arrayin.shape[0],3])    
    outarray[:arrayin.shape[0],:2]=arrayin
    return(outarray)
    
    
def polarLineToHomog(arrayin):
    arrayout=toHomog(arrayin)
    arrayout[:,0]=-np.cos(arrayin[:,1])/arrayin[:,0]
    arrayout[:,1]=-np.sin(arrayin[:,1])/arrayin[:,0]
    return(arrayout)


def rholineFromPoints(ptn1,ptn2):
            z=cart2z(np.array([ptn1-ptn2]))
            if(abs(z)>0):
                m=z/abs(z)  # rico
            else:
                m=0+0j
            n=m*(1j )  # normaal
            [a,b]=[m.real,m.imag] #stukken rico rechte
            theta=np.angle(n)
            if n.real == 0:
              return ([np.abs(ptn1[0]), 0])
            else:
                r= ((n.imag*ptn1[0]+n.real*ptn1[1]))
                r=-(b*ptn1[0]+a*ptn1[1])
                r=+a*ptn1[1]-b*ptn1[0]
                #print('r, theta orig', r,theta)
                if (r<0):
                    r=-r
                    if(theta>0):
                        theta= (theta-np.pi)
                    else:
                        theta= (theta+np.pi)
                return([r[0],theta[0]])
 
 

def lineFromPoints_homog(ptn1,ptn2):
    #input points are not homogen, output homogen
    vec_temp=np.ones([2,3])
    vec_temp[0,:2]= ptn1
    vec_temp[1,:2]= ptn2
    return(cross_prod_homog(vec_temp[0],vec_temp[1]))
    
def lines_from_corners(bordered_nearpoints):
        #bordered_corners=self.get_corner_pts_offset()
        bordered_corners=bordered_nearpoints

        #print('processing corners ',self._corners[1], self._corners[2] , rholineFromPoints(self._corners[1],self._corners[2]))
        prelines=[rholineFromPoints(bordered_corners[i],bordered_corners[i+1]) for i in range(3)]
        prelines.append(rholineFromPoints(bordered_corners[3],bordered_corners[0]))
        return(prelines)
 
def pointsFromLine_homog(ln1_h,ln2_h):
    return(cross_prod_homog(ln1_h,ln2_h))
            
def cart2z(arr):
            z = arr[:,0] + 1j * arr[:,1]
            return(z)

def fsigmoid(x, origin, top):
            #origin is 0,5 value
            #top is 0,9 value
            scale=(top-origin)/6
            return sigmoid((x-origin)/scale)
        
def sigmoid(x):
            return 1 / (1 + math.exp(-x))
            
def polar2z(r,theta):
            return r * exp( 1j * theta )

def z2polar(z):
            return ( np.array([abs(z), np.angle(z) ]))
            
def pol2cart(arr):
            arr_out=arr.copy()
            rho_arr= arr[0,:].copy()
            theta_arr=arr[1,:].copy()
            sin_arr=np.sin(theta_arr)
            cos_arr=np.cos(theta_arr)
            arr_out[0,:]=rho_arr * cos_arr
            arr_out[1,:]=rho_arr * sin_arr
            return(arr_out)
            
            
            
def contourFromRect(rect):
    x = rect[0]
    y = rect[1]
    width = rect[2]
    height = rect[3]

    '''p1 = np.matrix([[x, y]])
    p2 = np.matrix([[x + width, y]])
    p3 = np.matrix([[x, y + height]])
    p4 = np.matrix([[x + width, y + height]])
    contour = (np.array([p1, p2, p3, p4]))
    
    
    '''
    p1 = np.array([x, y])
    p2 = np.array([x + width, y])
    p3 = np.array([x, y + height])
    p4 = np.array([x + width, y + height])
    parray=[[x, y],[x + width, y],[x, y + height],[x + width, y + height]]
    contour =np.array(parray).reshape((-1,1,2)).astype(np.uint8)
   
    return(contour)
    
    
    
    
    
def overlappingRelArea(rect1, rect2):
        x = 0
        y = 1
        w = 2
        h = 3

        # Area of 1st Rectangle, width *height
        area1 = rect1[w]  * rect1[h]

        # Area of 2nd Rectangle
        area2 = rect2[w]  * rect2[h]

        
        x_dist = (min(rect1[x]+rect1[w], rect2[x]+rect2[w]) - max(rect1[x], rect2[x]))

        y_dist = (min(rect1[y]+rect1[h], rect2[y]+rect2[h]) - max(rect1[y], rect2[y]))
        areaI = 0
        if (x_dist > 0 and y_dist > 0) :
            areaI = x_dist * y_dist
        print('xdist', x_dist,'ydist',y_dist,'areaI', areaI, 'area1', area1,'area2',area2)
        return ( areaI)/(area1+area2)

            
