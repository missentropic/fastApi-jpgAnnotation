from math import sin, cos, atan
import cv2
import numpy as np
from matplotlib import pyplot as plt
from processors import Opener, Closer, EdgeDetector, Colorpicker, Shapepicker, lineFromPoints_homog,PointDto,lines_from_corners
from sklearn.cluster import KMeans, DBSCAN
from itertools import combinations
from numpy import linalg as LA
from operator import itemgetter
from scipy.spatial import distance_matrix
from random import randint
from PIL import Image, ImageTk, ImageOps



class HoughLineCornerDetector:
    def __init__(self, rho_acc = 1, theta_acc = 180, minthresh = 150, maxlines= 12, output_process = True, colorpicker=None, shapepicker=None,DEBUG_LEVEL=3):
        self.rho_acc = rho_acc
        self.theta_acc = theta_acc
        self.minthresh = minthresh
        self.thresh = minthresh
        self.maxlines = maxlines
        #self.output_process = output_process
        self.colorpicker=colorpicker
        self.shapepicker=shapepicker
        self._preprocessor = [
            Closer(output_process = output_process, iterations=6,kernel_size=5),
        ]
        self.DEBUG_LEVEL=DEBUG_LEVEL
        

    
    def __call__(self, image, nearpoints, colorpicker=None):
        # Step 1: Process for edge detection
        # nearpoints are ordered leftup =firt point
        self.nearpoints=nearpoints
        print('self.DEBUG_LEVEL from hough',self.DEBUG_LEVEL )
        if(self.DEBUG_LEVEL>1):
            print('image shape for hough\n', image.shape, nearpoints)
            #, np.min(nearpoints[:,0]),np.max(nearpoints[:,0]),np.min(nearpoints[:,1]),np.max(nearpoints[:,1]))
        # enkel imagecropped mag gebruikt voor hough detection
        if isinstance(self.shapepicker, Shapepicker):
            print('selected rect from hough',self.shapepicker.get_rect_hough_fractions_borderd())
            print('numpy image shape',np.array(image.shape)[:2])
            rect_shape_fractions=self.shapepicker.get_rect_hough_fractions_bordered()
            # what to do with this?


            nearpoints=self.shapepicker.get_corner_pts_rescaled(dim=image.shape) # moet nog origin af
            print('nearpoints on bordered image for hough and croppints', nearpoints)

            self.left_rect =int(rect_shape_fractions[0]*image.shape[1])
            self.right_rect =int(rect_shape_fractions[2]*image.shape[1])
            self.top_rect =int(rect_shape_fractions[1]*image.shape[0])
            self.bottom_rect=int(rect_shape_fractions[3]*image.shape[0])
            #print(int(rect_shape_fractions[0]*image.shape[1]),int(rect_shape_fractions[2]*image.shape[1]),

            #print(self.left_rect,self.top_rect,self.right_rect,self.bottom_rect)
            image = image[int(rect_shape_fractions[1]*image.shape[0]):int(rect_shape_fractions[3]*image.shape[0]),int(rect_shape_fractions[0]*image.shape[1]):int(rect_shape_fractions[2]*image.shape[1])]

            cv2.waitKey(1000)
            neworigin=[self.left_rect,self.top_rect]

            print('neworigin ', neworigin)


            print('nearpoints before origin', nearpoints)
            nearpoints-=neworigin
            self.nearpoints=nearpoints

            print('nearpoints after origin', nearpoints)
            #print('nearpoints adjusted', nearpoints)
            #print('after cropping', image.shape, nearpoints)
        if(self.DEBUG_LEVEL>2):
            cv2.imshow('faded unbordered', image)
            print('faded shape', image.shape)
            cv2.waitKey(0)
      
    
        #???
        self._image = image
        self._colorpicker=colorpicker
        #self.shapepicker=shapepicker
        self._intersections=[]
        
        for processor in self._preprocessor:
            ##self._image = processor(self._image)
            self._image = processor(self._image)
        combinedEdges=EdgeDetector(shapepicker=self.shapepicker , DEBUG_LEVEL=self.DEBUG_LEVEL)
        self._image=combinedEdges(self._image, colorpicker=self.colorpicker,nearpoints=self.nearpoints)

        
        # indien colorpicker None is, neem hough_lines, neem intersections, en xy point is mean intersections.
        if isinstance(self.shapepicker, Shapepicker):
            print('shapepicker lines used')
            self._lines= self._get_close_hough_lines()
            print('get close hough completed')
        else:
            if (len(nearpoints)>3):
                #self._lines= self._get_hough_lines()
            #print('self._hough lines',self._lines)
                self._lines= self._get_close_hough_lines()
                print('self._hough lines',self._lines)
            else:
                 self._lines= self._get_hough_lines()
        
       
        if(self.DEBUG_LEVEL>2):
            print('self before cluster', self._lines)
            self._draw_hough_lines(self._lines)
        self._lines=self._cluster_hough_lines(self._lines,0.001,1,0.1)
        self._lines=  self._select_strong_lines(0.001,1,0.2)
        self._lines=self._purge_hough_lines(self._lines,0.000001,1,0.15)
        if(self.DEBUG_LEVEL>2):
            print('self after purge', self._lines)
        self._intersections = self._get_intersections(nearpoints)
        # Step 4: Get Quadrilaterals
        return self._find_quadrilaterals()

    
    def _get_hough_lines(self):
        thresh=1000
        j=0
      
        #print (j,self.maxlines, self.minthresh, thresh)
        while(j < self.maxlines and thresh>self.minthresh):
            try:
                lines = cv2.HoughLines(
                self._image,
                #self.rho_acc,
                2,
                np.pi / self.theta_acc,
                #self.thresh
                thresh,100
                );j=lines.shape[0]
               
                
            except:j=0
            thresh=thresh-10
        self._draw_hough_lines(lines)
        return(lines)
        
        
        
            
            
    def _get_close_hough_lines(self):
    # we moeten nog de lijnen die buiten het selectiegebied liggen maskeren.!!!
    # rho theta lines
        #cornerlines=self.shapepicker.get_corner_lines(self.nearpoints)
        # dit geeft hier enkel de 4 hoeklijnen
        cornerlines=lines_from_corners(self.nearpoints)
        print('unravel lines from nearpoints',np.ravel(cornerlines).shape[0]>>1, cornerlines, 'self points', self.nearpoints)
        if(self.DEBUG_LEVEL>4):
            print('unravel lines',np.ravel(cornerlines).shape[0]>>1)
        #print('corner lines from Shapepicker', cornerlines, 'imageShape:', self._image.shape)
        #cv2.waitKey(0)
        cornermidlines=self._cluster_hough_lines(cornerlines,0.0000001,1,0.7)
        # hier enkel 2 hoofdrichtingen en rho van midden.
        # te weerhouden lijnen moeten buiten de shapepicker lines liggen. dus verder van de cornermidlines dan van de selectline en in de goede richting
        ### voor elke line moet je afstand van cornermidline met zelfde orientatie zoeken.
        print('cornermidlines clustered lines', cornermidlines)
        def rho_dist_from_cornermidline(line,cornermidlines):
            best_theta_idx=np.argsort(np.abs(np.reshape(cornermidlines,(-1,2))[:,1]-line[1]))[0]
            return(line[0]- np.reshape(cornermidlines,(-1,2))[best_theta_idx,0])
        
        linestot=[]
        maxlines=7
        for line in cornerlines:
            #print('line in close_hough',line  )
            rho_mid_dist=rho_dist_from_cornermidline(line,cornermidlines)
            #if(rho_mid_dist==0):
                #print('oooooooooooooooo rhomiddist', line,cornermidlines)
            
            thresh=400
            j=0
            linestemparray=[line]
            linespart=[]
           
            self.DEBUG_LEVEL=2
            while(j < self.maxlines and thresh>self.minthresh):
                if(self.DEBUG_LEVEL>3):
                    print (j,self.maxlines, self.minthresh, thresh)
                try:
                    linespart = cv2.HoughLines(
                    self._image,
                    self.rho_acc,
                    np.pi / self.theta_acc,
                  
                    thresh,100,2,0,line[1]-0.05,line[1]+0.05
                    )
                    if linespart is not None:
                        j = linespart.shape[0]
                    else:
                        j = 0
                   
                
                except:
                    if linespart is not None:
                        j = linespart.shape[0]
                    else:
                        j = 0
                thresh=thresh-20
       
            #print('before check linespart empty', linespart)
            if linespart is None or len(linespart) == 0:
                linespart=np.array(line) # only 1 line
              
            linespart=self._filter_lines_by_shapeline(70,rho_mid_dist,line, linespart)
     
            if(linespart.shape[0]==0):
                linespart=[np.array(line)] # only 1 line

            linestot.append(linespart[0]) # enkel de eerste
            print('line from corner ', line ,' and linestot', linestot[-1])
        linestotarray= np.asarray(linestot)
        linestotarray= np.reshape(linestotarray, (-1,1,2))
        return(linestotarray)
      
        
    def _select_strong_lines( self, rho_dist,theta_dist,maxdist):
        maxlines=7
        strong_lines = np.zeros([maxlines,1,2])
        lines=self._lines
    
        n2 = 0
        for n1 in range(0,len(self._lines)):
            #print(n1, n2, strong_lines)
            # add the line
            if(n2 < strong_lines.shape[0]):
                # neglect vertical lines at the border
                if(lines[n1][:,1]==0):
                    if(lines[n1][:,1]<20 ):
                        continue
                    if(lines[n1][:,1]> self._image.shape[1]-20 ):
                        continue
                strong_lines[n2] = lines[n1]
                n2 = n2+1
                if n1 > 0:
                    cluster_check_lines=  np.reshape(np.copy(strong_lines[:n2,:,:]), (-1,1,2))
                    Xtemp=np.reshape(lines, (np.ravel(lines).shape[0]>>1 ,-1))
                    if self._cluster_hough_lines(cluster_check_lines,rho_dist, theta_dist, maxdist).shape[0] < n2 :
                        n2= n2 - 1

        return(strong_lines[:n2,])
                   
                
                    
                    
    
    def _filter_lines_by_shapeline( self, rho_dist,rho_mid_dist,refline,lines):
        # this is only retaining lines that have rho_distances from refline.
        # theta was filtered before since only lines in neighborthood of theta are presented.
         returnlines=[]
         X=np.reshape(lines ,(np.ravel(lines).shape[0]>>1 ,-1))
         #print('unravel linespart',X)
         for line in X:
                 
            if (abs(line[0]-refline[0])<rho_dist):
                #if(np.sign(line[0]-refline[0])==np.sign(rho_mid_dist)):
               
                    if((line[0]-refline[0])/rho_mid_dist > -0.15):
                    #print('rho_dist,rho_mid_dist, line',rho_dist,rho_mid_dist, line)
                       
                        returnlines.append(line)
        
         returnlinesdiff=np.reshape(returnlines,[-1,2])
         return(np.array(returnlines))
                  
                    
                    
                    
        
    def _cluster_hough_lines(self, lines, rho_dist,theta_dist,maxdist):
        # opgelet, de representatie van de kmeans is niet als lines
        # group lines by angle
        # find outer lines
        # drop inner lines
        # drop major non rectangle orientations
       
        
        maxlines=min(30,np.ravel(lines).shape[0]>>1)
        '''print('aantal lijnen:', np.ravel(lines).shape[0]>>1)'''
        X=np.reshape(lines, (np.ravel(lines).shape[0]>>1 ,-1))
        X=X[:maxlines,:]
        #print('transposed back',X)
        X[:,0]=X[:,0]*rho_dist
        X[:,1]=X[:,1]*theta_dist
       
        X[X[:,0]<0,1]=X[X[:,0]<0,1]-np.pi
        X[X[:,0]<0,0]=-X[X[:,0]<0,0] # rho positive
        
       
        db = DBSCAN(eps=maxdist, min_samples=1).fit(X)
        labels = db.labels_
        sorted_labels, sorted_inds = zip(*sorted([(i,e) for i,e in enumerate(labels)], key=itemgetter(1)))

        X=X[sorted_labels,:]
        labels=np.array(sorted_inds)
        db_center_points=[]
        for cluster in np.unique(labels):
            #db_center_points[cluster]=np.mean(X[labels==cluster], axis=0)
            #print(db_center_points[cluster])
            db_center_points.append(np.mean(X[labels==cluster], axis=0).tolist())
            
        X1=np.reshape(db_center_points, (np.ravel(db_center_points).shape[0]>>1 ,-1))
        X1[:,0]=X1[:,0]/rho_dist
        X1[:,1]=X1[:,1]/theta_dist
        lines= np.reshape(X1, (-1,1,2))
        return(lines)


    def _purge_hough_lines(self, lines, rho_dist,theta_dist,maxdist):
        # opgelet, de representatie is niet als lines
        # group lines by angle
        # find outer lines
        # drop inner lines
        # drop major non rectangle orientations
       
        X=np.reshape(lines, (np.ravel(lines).shape[0]>>1 ,-1))
        
        X[:,0]=X[:,0]*rho_dist
        X[:,1]=X[:,1]*theta_dist
        X[X[:,0]<0,1]=X[X[:,0]<0,1]-np.pi
        X[X[:,0]<0,0]=-X[X[:,0]<0,0]
               
        db = DBSCAN(eps=maxdist, min_samples=1).fit(X)
        labels = db.labels_
        
        sorted_labels, sorted_inds = zip(*sorted([(i,e) for i,e in enumerate(labels)], key=itemgetter(1)))
        X=X[sorted_labels,:]
        #print(X)
        labels=np.array(sorted_inds)
        
        # sorteer eerst de labels volgens voorkomen.
        # deze met meeste elementen zijn waarschijnlijk te verwijderen
        
        #print('labels', labels)
        X[:,0]=X[:,0]/rho_dist
        X[:,1]=X[:,1]/theta_dist
        # make polar plot
        db_intern_points=[]
        db_intern_idx=[]
        #process clusters of similar theta
        # de clusters zijn nu al gesorteerd, enkel de lijnen dienen gesorteerd.
                        
        lines= np.reshape(X, (-1,1,2))
        for cluster in np.unique(labels):
            to_internal_array_idx= [index for index,value in enumerate(labels) if value == cluster]
            idxs=np.argsort(X[to_internal_array_idx,0])
            [lines,labels]=self._purge_internal(lines,labels,cluster,0)
        X=np.reshape(lines, (np.ravel(lines).shape[0]>>1 ,-1))
        return(lines)

   
    def _purge_internal(self,lines, labels, cluster ,sort_axis):
        internal=[]
        internalidx=[]
        to_internal_array_idx= [index for index,value in enumerate(labels) if value == cluster]
       
        if len(to_internal_array_idx) > 2:
            for vector in lines[to_internal_array_idx]:
               #internal.append(LA.linalg.norm(vector[0][0],ord=None))
                internal.append(vector[0][sort_axis])
            #print('internal point coordinate',internal)
            sorted_extr_idx=np.argsort(internal)
        
            #print('sorted_extr', sorted_extr_idx,sorted_extr_idx[1:-1] )
            internalidx=sorted_extr_idx[1:-1]
            first=0
            #print('first resetted')
            for idx in sorted(sorted_extr_idx[1:-1]):
            # hier moet je rekening houden indien de lines korter worden, dan kun je element niet meer vinden
             
                lines=np.delete(lines, to_internal_array_idx[idx]-first, 0)
                labels=np.delete(labels,to_internal_array_idx[idx]-first, 0)
                
                first+=1
        return [lines,labels]

    
    def _draw_hough_lines(self, lines):
        hough_line_output = self._get_color_image()

        #for line in lines[:12,]:
        for line in lines:
            rho, theta = line[0]
            a, b = np.cos(theta), np.sin(theta)
            x0, y0 = a * rho, b * rho
            n = 5000
            x1 = int(x0 + n * (-b))
            y1 = int(y0 + n * (a))
            x2 = int(x0 - n * (-b))
            y2 = int(y0 - n * (a))

            cv2.line(
                hough_line_output, 
                (x1, y1), 
                (x2, y2), 
                (0, 0, 255), 
                2
            )
        if(self.DEBUG_LEVEL>3):
        #if self.output_process:
            cv2.imwrite('output/hough_line.jpg', hough_line_output)

    
    def _get_intersections(self, nearpoints):
        """Finds the intersections between groups of lines."""
        #lines = self._lines[:8,]
        lines = self._lines
        intersections = []
        group_lines = combinations(range(len(lines)), 2)
        '''x_in_range = lambda x: -200 <= x <= self._image.shape[0]*2
        y_in_range = lambda y: -200 <= y <= self._image.shape[1]*2'''
        x_in_range = lambda x: -200 <= x <= self._image.shape[1]*2
        y_in_range = lambda y: -200 <= y <= self._image.shape[0]*2
    
        print('nearpoints in hough', nearpoints)
        '''for i, j in group_lines:
            print('all grouplines', i,j)
            line_i, line_j = lines[i][0], lines[j][0]
            print('line_1, line_2,angle',line_i,line_j,self._get_angle_between_lines(line_i, line_j))'''

        for i, j in group_lines:
            line_i, line_j = lines[i][0], lines[j][0]
            print('line_1, line_2,angle',line_i,line_j,self._get_angle_between_lines(line_i, line_j))
            if 45.0 < self._get_angle_between_lines(line_i, line_j) < 135.0:
                int_point = self._intersection(line_i, line_j)
                print("line cross",i,j, int_point, 'in range',x_in_range(int_point[0][0]),self._image.shape[1]*2,y_in_range(int_point[0][1]),self._image.shape[0]*2 )
                
                if x_in_range(int_point[0][0]) and y_in_range(int_point[0][1]):
                    if(self.DEBUG_LEVEL>3):
                        print('distances from shape points', int_point, np.min(np.linalg.norm(nearpoints-int_point,axis=1)),)
                    if np.min(np.linalg.norm(nearpoints-int_point,axis=1))< 200:
                        print('point added')
                        intersections.append(int_point)
                        print('intersections', intersections)
                        
        #sort intersections cfr nearpoints
        # kunnen er nog steeds meer dan 4 zijn.(of minder)
        print('first intersections from hough', intersections)
      
     
        idx_1= (np.argmin(distance_matrix(np.reshape(intersections,(-1,2)),nearpoints), axis=1))
        intersections_first_sort=intersections.copy()
        for idx in range(len(idx_1)):
            #print(idx_1[idx])
            intersections[idx]= intersections_first_sort[idx_1[idx]]
        if(self.DEBUG_LEVEL>2):
            self._draw_intersections(intersections)
        print('intersections from hough', intersections)
        return intersections


        
    #def _sort_intersections(self, nearpoints):
    
  
        
    def _remove_intermediate_points(self):
        # if more than 2 points on line, then remove intermediate point
        def collinear(p0, p1, p2):
            x1, y1 = p1[0] - p0[0], p1[1] - p0[1]
            x2, y2 = p2[0] - p0[0], p2[1] - p0[1]
            
            if(self.output_process):
                if abs(x1 * y2 - x2 * y1) < 1e-12:
                    print('collinear points',p0,p1,p2 )
                
                
            return abs(x1 * y2 - x2 * y1) < 1e-12
            
                        
        X = np.array([[point[0][0], point[0][1]] for point in self._intersections])
        print(X)
        for i in range(len(X)):
            for j in range(i+1,len(X)):
                for k in range(j+1,len(X)):
                    if collinear( X[i],X[j],X[k]):
                        p#rint('points on lines:',i,j,k, collinear( X[i],X[j],X[k]))
          


    def _find_quadrilaterals(self):
        X = np.array([[point[0][0], point[0][1]] for point in self._intersections])
       
       
        #if intersection points on one of lines, and intersection points intermediate, then remove intersection points.
        if len(self._intersections) > 4:
            #doet voorlopig niks.
            self._remove_intermediate_points()

        db = DBSCAN(eps=10, min_samples=1).fit(X)
        labels = db.labels_
        
        db_center_points=[]

        no_clusters = len(set(labels)) - (1 if -1 in labels else 0)
        
        #print('No of clusters:', no_clusters)
     
        for cluster in range(no_clusters):
            db_center_points.append(np.mean(X[labels==cluster], axis=0).tolist())
       
    
        if self.DEBUG_LEVEL>3:
            #self._draw_quadrilaterals(self._lines, kmeans.cluster_centers_)
            
            self._draw_quadrilaterals(self._lines, db_center_points)

        #return  [[center.tolist()] for center in kmeans.cluster_centers_]
        return  [db_center_points]


    def _draw_quadrilaterals(self, lines, cluster_centers):
        grouped_output = self._get_color_image()

        for idx, line in enumerate(lines):
            rho, theta = line[0]
            a, b = np.cos(theta), np.sin(theta)
            x0, y0 = a * rho, b * rho
            n = 5000
            x1 = int(x0 + n * (-b))
            y1 = int(y0 + n * (a))
            x2 = int(x0 - n * (-b))
            y2 = int(y0 - n * (a))

            cv2.line(
                grouped_output, 
                (x1, y1), 
                (x2, y2), 
                (0, 0, 255), 
                2
            )
        
        for point in cluster_centers:
            x, y = point
            #print(point)

            cv2.circle(
                grouped_output,
                (int(x), int(y)),
                5,
                (255, 255, 255),
                5
            )
        if self.DEBUG_LEVEL>3:
            cv2.imwrite('output/grouped.jpg', grouped_output)
        return

            
   
    
    def _get_center_points( X, labels):
        #print(X)
        #print(labels)
        no_clusters = len(set(labels)) - (1 if -1 in labels else 0)
        print('No of clusters:', no_clusters)
        db_center_points=[]
        for cluster in range(no_clusters):
            db_center_points.append(np.mean(X[labels==cluster], axis=0).tolist())
       
        print('db_center_points', db_center_points)
        return(db_center_points)
        
    def _get_angle_between_lines(self, line_1, line_2):
        rho1, theta1 = line_1
        rho2, theta2 = line_2
        return (abs(theta1-theta2)* (180 / np.pi))

    
    def _intersection(self, line1, line2):
        """Finds the intersection of two lines given in Hesse normal form.

        Returns closest integer pixel locations.
        See https://stackoverflow.com/a/383527/5087436
        """
        rho1, theta1 = line1
        rho2, theta2 = line2

        A = np.array([
            [np.cos(theta1), np.sin(theta1)],
            [np.cos(theta2), np.sin(theta2)]
        ])

        b = np.array([[rho1], [rho2]])
        x0, y0 = np.linalg.solve(A, b)
        x0, y0 = int(np.round(x0)), int(np.round(y0))
        return [[x0, y0]]


    def _draw_intersections(self, intersections):
        intersection_point_output = self._get_color_image()

        for line in self._lines:
            rho, theta = line[0]
            a = np.cos(theta)
            b = np.sin(theta)
            x0 = a * rho
            y0 = b * rho
            n = 5000
            x1 = int(x0 + n * (-b))
            y1 = int(y0 + n * (a))
            x2 = int(x0 - n * (-b))
            y2 = int(y0 - n * (a))

            cv2.line(
                intersection_point_output, 
                (x1, y1), 
                (x2, y2), 
                (0, 0, 255), 
                2
            )

        for point in intersections:
            x, y = point[0]

            cv2.circle(
                intersection_point_output,
                (x, y),
                5,
                (255, 255, 127),
                5
            )
        if self.DEBUG_LEVEL>3:
            cv2.imwrite('output/intersection_point_output.jpg', intersection_point_output)


    def _get_color_image(self):
        return cv2.cvtColor(self._image.copy(), cv2.COLOR_GRAY2RGB)
