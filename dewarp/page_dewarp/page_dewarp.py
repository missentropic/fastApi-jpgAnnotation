#!/usr/bin/env python
######################################################################
# page_dewarp.py - Proof-of-concept of page-dewarping based on a
# "cubic sheet" model. Requires OpenCV (version 3 or greater),
# PIL/Pillow, and scipy.optimize.
######################################################################
# Author:  Matt Zucker
# Date:    July 2016
# License: MIT License (see LICENSE.txt)
# Author2:  Martine Lapere
# aanpassingen en uitbreidingen Martine Lapere
######################################################################

import os
import sys
import datetime
import cv2
from PIL import Image
import numpy as np
import scipy.optimize
from itertools import combinations

# for some reason pylint complains about cv2 members being undefined :(
# pylint: disable=E1101

#PAGE_MARGIN_X = 50       # reduced px to ignore near L/R edge
PAGE_MARGIN_X = 25       # reduced px to ignore near L/R edge
PAGE_MARGIN_Y = 25       # reduced px to ignore near T/B edge

OUTPUT_ZOOM = 1.0        # how much to zoom output relative to *original* image
OUTPUT_DPI = 300         # just affects stated DPI of PNG, not appearance
REMAP_DECIMATE = 16      # downscaling factor for remapping image

ADAPTIVE_WINSZ = 55      # window size for adaptive threshold in reduced px

'''TEXT_MIN_WIDTH = 15      # min reduced px width of detected text contour
#TEXT_MIN_HEIGHT = 2      # min reduced px height of detected text contour
TEXT_MIN_HEIGHT = 15      # min reduced px height of detected text contour
#TEXT_MIN_ASPECT = 1.5    # filter out text contours below this w/h ratio
TEXT_MIN_ASPECT = 1    # filter out text contours below this w/h ratio
#TEXT_MAX_THICKNESS = 10  # max reduced px thickness of detected text contour
TEXT_MAX_THICKNESS = 100  # max reduced px thickness of detected text contour'''

TEXT_MIN_WIDTH = 30      # min reduced px width of detected text contour
#TEXT_MIN_HEIGHT = 2      # min reduced px height of detected text contour
TEXT_MIN_HEIGHT = 30      # min reduced px height of detected text contour
#TEXT_MIN_ASPECT = 1.5    # filter out text contours below this w/h ratio
TEXT_MIN_ASPECT = 1    # filter out text contours below this w/h ratio
#TEXT_MAX_THICKNESS = 10  # max reduced px thickness of detected text contour
TEXT_MAX_THICKNESS = 200  # max reduced px thickness of detected text contour


EDGE_MAX_OVERLAP = 1.0   # max reduced px horiz. overlap of contours in span
#EDGE_MAX_OVERLAP = 0.6   # max reduced px horiz. overlap of contours in span
#EDGE_MAX_LENGTH = 35.0  # max reduced px length of edge connecting contours
EDGE_MAX_LENGTH = 45.0  # max reduced px length of edge connecting contours
#EDGE_ANGLE_COST = 15.0   # cost of angles in edges (tradeoff vs. length)
EDGE_ANGLE_COST = 25.0   # cost of angles in edges (tradeoff vs. length)
#EDGE_MAX_ANGLE = 7.5     # maximum change in angle allowed between contours
EDGE_MAX_ANGLE = 5     # maximum change in angle allowed between contours in span

RVEC_IDX = slice(0, 3)   # index of rvec in params vector
TVEC_IDX = slice(3, 6)   # index of tvec in params vector
CUBIC_IDX = slice(6, 8)  # index of cubic slopes in params vector

SPAN_MIN_WIDTH = 15      # minimum reduced px width for span
SPAN_MIN_ELEMENT_WIDTH = 10      # minimum reduced px width for span
SPAN_PX_PER_STEP = 20    # reduced px spacing for sampling along spans

FOCAL_LENGTH = 1.2       # normalized focal length of camera

DEBUG_LEVEL = 2          # 0=none, 1=some, 2=lots, 3=all
DEBUG_OUTPUT = 'both'    # file, screen, both

WINDOW_NAME = 'Dewarp'   # Window name for visualization

# nice color palette for visualizing contours, etc.
CCOLORS = [
    (255, 0, 0),
    (255, 63, 0),
    (255, 127, 0),
    (255, 191, 0),
    (255, 255, 0),
    (191, 255, 0),
    (127, 255, 0),
    (63, 255, 0),
    (0, 255, 0),
    (0, 255, 63),
    (0, 255, 127),
    (0, 255, 191),
    (0, 255, 255),
    (0, 191, 255),
    (0, 127, 255),
    (0, 63, 255),
    (0, 0, 255),
    (63, 0, 255),
    (127, 0, 255),
    (191, 0, 255),
    (255, 0, 255),
    (255, 0, 191),
    (255, 0, 127),
    (255, 0, 63),
]

# default intrinsic parameter matrix
K = np.array([
    [FOCAL_LENGTH, 0, 0],
    [0, FOCAL_LENGTH, 0],
    [0, 0, 1]], dtype=np.float32)


def debug_show(name, step, text, display):

    if DEBUG_OUTPUT != 'screen':
        filetext = text.replace(' ', '_')
        outfile = name + '_debug_' + str(step) + '_' + filetext + '.png'
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


def round_nearest_multiple(i, factor):
    i = int(i)
    rem = i % factor
    if not rem:
        return i
    else:
        return i + factor - rem


def pix2norm(shape, pts):
    height, width = shape[:2]
    scl = 2.0/(max(height, width))
    offset = np.array([width, height], dtype=pts.dtype).reshape((-1, 1, 2))*0.5
    return (pts - offset) * scl


def norm2pix(shape, pts, as_integer):
    height, width = shape[:2]
    scl = max(height, width)*0.5
    offset = np.array([0.5*width, 0.5*height],
                      dtype=pts.dtype).reshape((-1, 1, 2))
    rval = pts * scl + offset
    if as_integer:
        return (rval + 0.5).astype(int)
    else:
        return rval


def fltp(point):
    return tuple(point.astype(int).flatten())


def draw_correspondences(img, dstpoints, projpts):

    display = img.copy()
    dstpoints = norm2pix(img.shape, dstpoints, True)
    projpts = norm2pix(img.shape, projpts, True)

    for pts, color in [(projpts, (255, 0, 0)),
                       (dstpoints, (0, 0, 255))]:

        for point in pts:
            cv2.circle(display, fltp(point), 3, color, -1, cv2.LINE_AA)

    for point_a, point_b in zip(projpts, dstpoints):
        cv2.line(display, fltp(point_a), fltp(point_b),
                 (255, 255, 255), 1, cv2.LINE_AA)

    return display


def get_default_params(corners, ycoords, xcoords):

    #if DEBUG_LEVEL>3:
    #    print('page_dewarp input to get_default_param',corners ,ycoords,xcoords)

    # page width and height
    page_width = np.linalg.norm(corners[1] - corners[0])
    page_height = np.linalg.norm(corners[-1] - corners[0])
    rough_dims = (page_width, page_height)

    # our initial guess for the cubic has no slope
    cubic_slopes = [0.0, 0.0]

    # object points of flat page in 3D coordinates
    corners_object3d = np.array([
        [0, 0, 0],
        [page_width, 0, 0],
        [page_width, page_height, 0],
        [0, page_height, 0]])

    # estimate rotation and translation from four 2D-to-3D point
    # correspondences
    _, rvec, tvec = cv2.solvePnP(corners_object3d,
                                 corners, K, np.zeros(5))

    span_counts = [len(xc) for xc in xcoords]

    params = np.hstack((np.array(rvec).flatten(),
                        np.array(tvec).flatten(),
                        np.array(cubic_slopes).flatten(),
                        ycoords.flatten()) +
                       tuple(xcoords))

    return rough_dims, span_counts, params


def project_xy(xy_coords, pvec):

    # get cubic polynomial coefficients given
    #
    #  f(0) = 0, f'(0) = alpha
    #  f(1) = 0, f'(1) = beta

    alpha, beta = tuple(pvec[CUBIC_IDX])

    poly = np.array([
        alpha + beta,
        -2*alpha - beta,
        alpha,
        0])

    xy_coords = xy_coords.reshape((-1, 2))
    z_coords = np.polyval(poly, xy_coords[:, 0])

    objpoints = np.hstack((xy_coords, z_coords.reshape((-1, 1))))

    image_points, _ = cv2.projectPoints(objpoints,
                                        pvec[RVEC_IDX],
                                        pvec[TVEC_IDX],
                                        K, np.zeros(5))

    return image_points


def project_keypoints(pvec, keypoint_index):

    xy_coords = pvec[keypoint_index]
    xy_coords[0, :] = 0

    return project_xy(xy_coords, pvec)


def resize_to_screen(src, maxw=1280, maxh=700, copy=False):
## bug lapere

    height,width = src.shape[:2]

    scl_x = float(width)/maxw
    scl_y = float(height)/maxh
    #print(scl_x,scl_y, maxw, maxh)

    #scl = (np.ceil(max(scl_x, scl_y)))
    scl = (max(scl_x, scl_y))
    scl = 1
    #print(height, width, 'scaling to', scl)
    
    if scl > 1.0:
        inv_scl = 1.0/scl
        outw=int(width*inv_scl)
        outh=int(height*inv_scl)
        print('resized width en height',outw,outh)
        img = cv2.resize(src,(outw, outh),  cv2.INTER_AREA)
    elif copy:
        img = src.copy()
    else:
        #img = src
        img=cv2.resize(src, (0, 0), None, scl, scl, cv2.INTER_LINEAR)
        
    print('resized img shape,', img.shape)

    return img, scl


def box(width, height):
    return np.ones((height, width), dtype=np.uint8)


def get_page_extents(small):

    height,width,  = small.shape[:2]
    print('get_extents shape width height', width , height)

    xmin = PAGE_MARGIN_X
    ymin = PAGE_MARGIN_Y
    xmax = width-PAGE_MARGIN_X
    ymax = height-PAGE_MARGIN_Y

    page = np.zeros((height, width), dtype=np.uint8)
    cv2.rectangle(page, (xmin, ymin), (xmax, ymax), (255, 255, 255), -1)

    outline = np.array([
        [xmin, ymin],
        [xmin, ymax],
        [xmax, ymax],
        [xmax, ymin]])
    if(DEBUG_LEVEL > 3):
        print('outline page borders', outline)
        #cv2.imshow('outline page get extends', page)
        #cv2.waitKey(0)

    return page, outline


def get_mask(name, small, pagemask, masktype, DEBUG_LEVEL=3):

    sgray = cv2.cvtColor(small, cv2.COLOR_RGB2GRAY)

    if masktype == 'text':
       

        mask = cv2.adaptiveThreshold(sgray, 255, cv2.ADAPTIVE_THRESH_MEAN_C,
                                     cv2.THRESH_BINARY_INV,
                                     ADAPTIVE_WINSZ,
                                     25)

        if DEBUG_LEVEL >= 3:
            debug_show(name, 0.1, 'thresholded', mask)
        
        mask = cv2.erode(mask, box(4, 4))
        # prevent dilate from borders

        #mask=np.minimum(mask,pagemask)
        mask=np.maximum(mask,pagemask)

        #mask = cv2.dilate(mask, box(9, 1))
        #mask = cv2.dilate(mask, box(30, 3))
        #mask = cv2.dilate(mask, box(36, 8))
        #mask = cv2.dilate(mask, box(25, 8))
        mask = cv2.dilate(mask, box(30, 8))
        mask = cv2.dilate(mask, box(10, 5))
        if DEBUG_LEVEL >= 3:
            debug_show(name, 0.2, 'dilated', mask)

        mask = cv2.erode(mask, box(3, 1))

        if DEBUG_LEVEL >= 3:
            debug_show(name, 0.3, 'eroded', mask)

    else:
        print('masktype received is not text')
        mask = cv2.adaptiveThreshold(sgray, 255, cv2.ADAPTIVE_THRESH_MEAN_C,
                                     cv2.THRESH_BINARY_INV,
                                     ADAPTIVE_WINSZ,
                                     7)

        if DEBUG_LEVEL >= 3:
            debug_show(name, 0.4, 'thresholded', mask)

       # mask = cv2.erode(mask, box(3, 1), iterations=3)

        if DEBUG_LEVEL >= 3:
            debug_show(name, 0.5, 'eroded', mask)
        # horizontal extend
        mask = cv2.dilate(mask, box(8, 2))
       

        if DEBUG_LEVEL >= 3:
            debug_show(name, 0.6, 'dilated', mask)
    #cv2.imshow('maskdilated',mask)
   
    #cv2.waitKey(0)
    #return np.minimum(mask, pagemask)
    return mask


def interval_measure_overlap(int_a, int_b):
    return min(int_a[1], int_b[1]) - max(int_a[0], int_b[0])



    

def angle_dist(angle_b, angle_a):

    diff = angle_b - angle_a

    while diff > np.pi:
        diff -= 2*np.pi

    while diff < -np.pi:
        diff += 2*np.pi

    return np.abs(diff)


def blob_mean_and_tangent(contour):
   
    
    moments = cv2.moments(contour)

    area = moments['m00']

    mean_x = moments['m10'] / area
    mean_y = moments['m01'] / area

    moments_matrix = np.array([
        [moments['mu20'], moments['mu11']],
        [moments['mu11'], moments['mu02']]
    ]) / area

    _, svd_u, _ = cv2.SVDecomp(moments_matrix)

    center = np.array([mean_x, mean_y])
    tangent = svd_u[:, 0].flatten().copy()
  
    return center, tangent


class ContourInfo(object):

    def __init__(self, contour, rect, mask):
       
        self.contour = contour
        self.rect = rect
        self.mask = mask
        if(self.contour.shape[0]==4):
                #center = np.array([mean_x, mean_y])
           
           
            self.center=np.array([self.rect[0]+0.5*self.rect[2], self.rect[1]+0.5*self.rect[3]])
            print('center of rect x', self.rect, self.center)
            self.tangent=np.array([1.0 , 0.0]).flatten()
            self.angle=0.0
        else:

            self.center, self.tangent = blob_mean_and_tangent(contour)
            

            self.angle = np.arctan2(self.tangent[1], self.tangent[0])

        clx = [self.proj_x(point) for point in contour]

        lxmin = min(clx)
        lxmax = max(clx)

        self.local_xrng = (lxmin, lxmax)
      

        self.point0 = self.center + self.tangent * lxmin
        self.point1 = self.center + self.tangent * lxmax
        

        self.pred = None
        self.succ = None

    def proj_x(self, point):
        return np.dot(self.tangent, point.flatten()-self.center)

    def local_overlap(self, other):
        xmin = self.proj_x(other.point0)
        xmax = self.proj_x(other.point1)
        return interval_measure_overlap(self.local_xrng, (xmin, xmax))
        
    def get_contour(self):
        return self.contour
        
    def get_rect(self):
        return self.rect


def generate_candidate_edge(cinfo_a, cinfo_b):

    # we want a left of b (so a's successor will be b and b's
    # predecessor will be a) make sure right endpoint of b is to the
    # right of left endpoint of a.
    if cinfo_a.point0[0] > cinfo_b.point1[0]:
        tmp = cinfo_a
        cinfo_a = cinfo_b
        cinfo_b = tmp

    x_overlap_a = cinfo_a.local_overlap(cinfo_b)
    x_overlap_b = cinfo_b.local_overlap(cinfo_a)

    overall_tangent = cinfo_b.center - cinfo_a.center
    overall_angle = np.arctan2(overall_tangent[1], overall_tangent[0])

    delta_angle = max(angle_dist(cinfo_a.angle, overall_angle),
                      angle_dist(cinfo_b.angle, overall_angle)) * 180/np.pi

    # we want the largest overlap in x to be small
    x_overlap = max(x_overlap_a, x_overlap_b)

    dist = np.linalg.norm(cinfo_b.point0 - cinfo_a.point1)
    #print('edge dist', dist)

    if (dist > EDGE_MAX_LENGTH or
            x_overlap > EDGE_MAX_OVERLAP or
            delta_angle > EDGE_MAX_ANGLE):
        return None
    else:
        score = dist + delta_angle*EDGE_ANGLE_COST
        return (score, cinfo_a, cinfo_b)


def make_tight_mask(contour, xmin, ymin, width, height):

    tight_mask = np.zeros((height, width), dtype=np.uint8)
    
    #print('tight mask numpy', np.array((xmin, ymin)).reshape((-1, 1, 2)))
    tight_contour = contour - np.array((xmin, ymin)).reshape((-1, 1, 2))
    #print('tight_contour', tight_contour)

    cv2.drawContours(tight_mask, [tight_contour], 0,
                     (1, 1, 1), -1)
    

    return tight_mask


def get_contours(name, small, pagemask, masktype, DEBUG_LEVEL=3):

    TEXT_MIN_WIDTH = 30      # min reduced px width of detected text contour
    #TEXT_MIN_HEIGHT = 2      # min reduced px height of detected text contour
    TEXT_MIN_HEIGHT = 30      # min reduced px height of detected text contour
    #TEXT_MIN_ASPECT = 1.5    # filter out text contours below this w/h ratio
    TEXT_MIN_ASPECT = 1    # filter out text contours below this w/h ratio
    #TEXT_MAX_THICKNESS = 10  # max reduced px thickness of detected text contour
    TEXT_MAX_THICKNESS = small.shape[0]/5 # max reduced px thickness of detected text contour

    print('TEXT_MAX_THICKNESS', TEXT_MAX_THICKNESS)
    


    
    pagem, page_outline = get_page_extents(small)
    print('pagem and pagemask and small in dewarp', pagem.shape,pagemask.shape, small.shape)
    #mask = get_mask(name, small, pagemask, masktype, DEBUG_LEVEL=4)
    #mask=np.minimum(pagem,pagemask)
    mask=pagemask
    #mask=pagem
    # some remaining small x artifacts
    DEBUG_LEVEL=2
    if (DEBUG_LEVEL>3):
        cv2.imshow('mask for contours in page_dewarp', mask)
        cv2.waitKey(0)
    

    #_, contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_NONE)
    #contours,hierachy=cv2.findContours(thresh,cv2.RETR_TREE,cv2.CHAIN_APPROX_SIMPLE)
    contours,hierachy = cv2.findContours(mask, cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_NONE)

    contours_out = []
    #print(contours)

    for contour in contours:
        

        rect = cv2.boundingRect(contour)
       
        xmin, ymin, width, height = rect
        '''ymin= np.maximum(0,ymin-3)
        height+=3
        xmin-=4
        width+=4'''
        rect=(xmin, ymin, width, height)
        #print('rect from contour', rect)
        
        ## patch
       
        

        if (width < TEXT_MIN_WIDTH or
                height < TEXT_MIN_HEIGHT or
                width < TEXT_MIN_ASPECT*height or
                height > TEXT_MAX_THICKNESS):
            continue
        #print('contour rect', rect)
       
        ## ymin seems too big
        start_point=(xmin,ymin)
        end_point=(xmin+width,ymin+height)
        color = (255, 0, 0)
        thickness=2
        
        ############
        
        #cnt = contours[4]
        #cv2.drawContours(mask, [contour], 0, (0,255,0), 3)
        #cv2.drawContours(small, [contour], 0, (0,255,255), 1)
        
        tight_mask = make_tight_mask(contour, xmin, ymin, width, height)#????
       

        if tight_mask.sum(axis=0).max() > TEXT_MAX_THICKNESS:
            continue
        #cv2.rectangle(small, start_point, end_point, color, thickness)
        contours_out.append(ContourInfo(contour, rect, tight_mask))
    

    if DEBUG_LEVEL >= 3:
        visualize_contours(name, small, contours_out)
    #cv2.imshow('contour detection', small)
    #cv2.waitKey(0)
    
    return contours_out


def assemble_spans(name, small, pagemask, cinfo_list, DEBUG_LEVEL=3):

    # sort list volgens de y waarde
    cinfo_list = sorted(cinfo_list, key=lambda cinfo: cinfo.rect[1])

    # generate all candidate edges
    candidate_edges = []

    for i, cinfo_i in enumerate(cinfo_list):
        #print('span for rect ', i, cinfo_i.rect)
        #Voor alle voorgaande (kleinere y)
        for j in range(i):
            # note e is of the form (score, left_cinfo, right_cinfo)
            edge = generate_candidate_edge(cinfo_i, cinfo_list[j])
            if edge is not None:
                candidate_edges.append(edge)
                if(DEBUG_LEVEL>3):
                    print('edge added',j, edge[1].get_rect(),  edge[2].get_rect())

    # sort candidate edges by score (lower is better)
    candidate_edges.sort()

    # for each candidate edge
    for _, cinfo_a, cinfo_b in candidate_edges:
        # if left and right are unassigned, join them
        if cinfo_a.succ is None and cinfo_b.pred is None:
            cinfo_a.succ = cinfo_b
            cinfo_b.pred = cinfo_a

    # generate list of spans as output
    spans = []

    # until we have removed everything from the list
    while cinfo_list:

        # get the first on the list
        cinfo = cinfo_list[0]
        #print('cinfo rect', cinfo.get_rect())

        # keep following predecessors until none exists
        while cinfo.pred:
            cinfo = cinfo.pred

        # start a new span
        cur_span = []

        width = 0.0

        # follow successors til end of span
        while cinfo:
            # remove from list (sadly making this loop *also* O(n^2)
            cinfo_list.remove(cinfo)
          
            
            # add to span
            cur_span.append(cinfo)
            
            #print('cur_span lengths',len(cinfo_list),'>',len(cur_span))
            width += cinfo.local_xrng[1] - cinfo.local_xrng[0]
          
            # set successor
            cinfo = cinfo.succ

        # add if long enough
        if width > SPAN_MIN_WIDTH:
            spans.append(cur_span)
            

    if DEBUG_LEVEL >= 3:
        visualize_spans(name, small, pagemask, spans)

    return spans


def sample_spans(shape, spans):

    span_points = []

    for span in spans:

        contour_points = []

        for cinfo in span:
            #print('cinfo', cinfo)
            yvals = np.arange(cinfo.mask.shape[0]).reshape((-1, 1))# iteration over height mask
            totals = (yvals * cinfo.mask).sum(axis=0)
            means = totals / cinfo.mask.sum(axis=0)
            #print('cinfo.mask.sum(axis=0)', cinfo.mask.sum(axis=0).sum()),
            #print ('cinfo stat ymeans', yvals, totals, means)
            #print ('cinfo stat  total ',  totals)
            xmin, ymin = cinfo.rect[:2]
            #print('xmin, ymin, means', xmin, ymin, means)

            step = SPAN_PX_PER_STEP
            start = ((len(means)-1) % step) //2
            #print('start', start)

            contour_points += [(x+xmin, means[x]+ymin)
                               for x in range(start, len(means), step)]

        contour_points = np.array(contour_points,
                                  dtype=np.float32).reshape((-1, 1, 2))

        contour_points = pix2norm(shape, contour_points)

        span_points.append(contour_points)

    return span_points
    
    
    
    
def merge_span(span, DEBUG_LEVEL=2):
    contours=[]
    spanout = []
  
    #print('span length', len(span))
    
   
        
    for cinfo in span:
        #print('contour rect cinfo in span ', cinfo.rect)
        contours.append(cinfo.contour)
        #span.remove(cinfo)
    # volgende is niet correct
    contour = np.vstack(contours)
    
    contour=cv2.convexHull(contour)
    #rect = cv2.boundingRect(contour)
    rect = merge_span_rect(span)
    #print('merged contour rect', rect)
    ##
    
        #print('merged rect', rect)

        #print('rect aftermerge', rect)
    xmin, ymin, width, height = rect
    tight_mask = make_tight_mask(contour, xmin, ymin, width, height)#????
    
    spanout.append(ContourInfo(contour, rect, tight_mask))
    #if(DEBUG_LEVEL>4):
        #print('spanout length after merge', len(spanout))
   
    return(spanout)
    

def merge_span_rect( span, max_span_gap= EDGE_MAX_LENGTH, DEBUG_LEVEL=2):

    span_rect = [10000,10000,0,0]
    [xmin,ymin,width,height]=span_rect
    xmax=0
    ymax=0
    
        
        #rect_measure_overlap
  
    for cinfo in span:
        xmin= np.minimum(cinfo.rect[0], xmin)
        ymin=np.minimum(cinfo.rect[1], ymin)
        xmax= np.maximum(cinfo.rect[0]+cinfo.rect[2], xmax)
        ymax=np.maximum(cinfo.rect[1]+cinfo.rect[3], ymax)
        
    span_rect=[xmin,ymin,xmax-xmin+1,ymax-ymin+1]
    #if (DEBUG_LEVEL>2):
        #print('span rect from merge_span_rect', span_rect)
    return span_rect
    



def keypoints_from_samples(name, small, pagemask, page_outline,
                           span_points):

    all_evecs = np.array([[0.0, 0.0]])
    all_weights = 0

    for points in span_points:

        _, evec = cv2.PCACompute(points.reshape((-1, 2)),
                                 None, maxComponents=1)

        weight = np.linalg.norm(points[-1] - points[0])

        all_evecs += evec * weight
        all_weights += weight

    evec = all_evecs / all_weights

    x_dir = evec.flatten()

    if x_dir[0] < 0:
        x_dir = -x_dir

    y_dir = np.array([-x_dir[1], x_dir[0]])

    pagecoords = cv2.convexHull(page_outline)
    pagecoords = pix2norm(pagemask.shape, pagecoords.reshape((-1, 1, 2)))
    pagecoords = pagecoords.reshape((-1, 2))

    px_coords = np.dot(pagecoords, x_dir)
    py_coords = np.dot(pagecoords, y_dir)

    px0 = px_coords.min()
    px1 = px_coords.max()

    py0 = py_coords.min()
    py1 = py_coords.max()

    p00 = px0 * x_dir + py0 * y_dir
    p10 = px1 * x_dir + py0 * y_dir
    p11 = px1 * x_dir + py1 * y_dir
    p01 = px0 * x_dir + py1 * y_dir

    corners = np.vstack((p00, p10, p11, p01)).reshape((-1, 1, 2))

    ycoords = []
    xcoords = []

    for points in span_points:
        pts = points.reshape((-1, 2))
        px_coords = np.dot(pts, x_dir)
        py_coords = np.dot(pts, y_dir)
        ycoords.append(py_coords.mean() - py0)
        xcoords.append(px_coords - px0)

    if DEBUG_LEVEL >= 2:
        visualize_span_points(name, small, span_points, corners)

    return corners, np.array(ycoords), xcoords


def visualize_contours(name, small, cinfo_list, DEBUG_LEVEL=2):

    regions = np.zeros_like(small)

    for j, cinfo in enumerate(cinfo_list):

        cv2.drawContours(regions, [cinfo.contour], 0,
                         CCOLORS[j % len(CCOLORS)], -1)

    mask = (regions.max(axis=2) != 0)

    display = small.copy()
    display[mask] = (display[mask]/2) + (regions[mask]/2)

    for j, cinfo in enumerate(cinfo_list):
        color = CCOLORS[j % len(CCOLORS)]
        color = tuple([c/4 for c in color])

        cv2.circle(display, fltp(cinfo.center), 3,
                   (255, 255, 255), 1, cv2.LINE_AA)

        cv2.line(display, fltp(cinfo.point0), fltp(cinfo.point1),
                 (255, 255, 255), 1, cv2.LINE_AA)

    debug_show(name, 1, 'contours', display)


def visualize_spans(name, small, pagemask, spans, DEBUG_LEVEL=2):

    regions = np.zeros_like(small)

    for i, span in enumerate(spans):
        contours = [cinfo.contour for cinfo in span]
        cv2.drawContours(regions, contours, -1,
                         CCOLORS[i*3 % len(CCOLORS)], -1)

    mask = (regions.max(axis=2) != 0)
    display = small.copy()
    display[mask] = (display[mask]/2) + (regions[mask]/2)
    display[pagemask == 0] = np.round(display[pagemask == 0]/ 4)
    #print('output span image', name)

    debug_show(name, 2, 'spans', display)


def visualize_span_points(name, small, span_points, corners):

    display = small.copy()

    for i, points in enumerate(span_points):

        points = norm2pix(small.shape, points, False)

        mean, small_evec = cv2.PCACompute(points.reshape((-1, 2)),
                                          None,
                                          maxComponents=1)

        dps = np.dot(points.reshape((-1, 2)), small_evec.reshape((2, 1)))
        dpm = np.dot(mean.flatten(), small_evec.flatten())

        point0 = mean + small_evec * (dps.min()-dpm)
        point1 = mean + small_evec * (dps.max()-dpm)

        for point in points:
            cv2.circle(display, fltp(point), 3,
                       CCOLORS[i % len(CCOLORS)], -1, cv2.LINE_AA)

        cv2.line(display, fltp(point0), fltp(point1),
                 (255, 255, 255), 1, cv2.LINE_AA)

    cv2.polylines(display, [norm2pix(small.shape, corners, True)],
                  True, (255, 255, 255))

    debug_show(name, 3, 'span points', display)


def imgsize(img):
    height, width = img.shape[:2]
    return '{}x{}'.format(width, height)


def make_keypoint_index(span_counts):

    nspans = len(span_counts)
    npts = sum(span_counts)
    keypoint_index = np.zeros((npts+1, 2), dtype=int)
    start = 1

    for i, count in enumerate(span_counts):
        end = start + count
        keypoint_index[start:start+end, 1] = 8+i
        start = end

    keypoint_index[1:, 0] = np.arange(npts) + 8 + nspans

    return keypoint_index


def optimize_params(name, small, dstpoints, span_counts, params):

    keypoint_index = make_keypoint_index(span_counts)

    def objective(pvec):
        ppts = project_keypoints(pvec, keypoint_index)
        return np.sum((dstpoints - ppts)**2)

    print ('  initial objective is', objective(params))

    if DEBUG_LEVEL >= 1:
        projpts = project_keypoints(params, keypoint_index)
        display = draw_correspondences(small, dstpoints, projpts)
        debug_show(name, 4, 'keypoints before', display)

    print ('  optimizing', len(params), 'parameters...')
    start = datetime.datetime.now()
    res = scipy.optimize.minimize(objective, params,
                                  method='Powell')
    end = datetime.datetime.now()
    print ('  optimization took', round((end-start).total_seconds(), 2), 'sec.')
    print ('  final objective is', res.fun)
    params = res.x

    if DEBUG_LEVEL >= 1:
        projpts = project_keypoints(params, keypoint_index)
        display = draw_correspondences(small, dstpoints, projpts)
        debug_show(name, 5, 'keypoints after', display)

    return params


def get_page_dims(corners, rough_dims, params):

    dst_br = corners[2].flatten()

    dims = np.array(rough_dims)

    def objective(dims):
        proj_br = project_xy(dims, params)
        return np.sum((dst_br - proj_br.flatten())**2)

    res = scipy.optimize.minimize(objective, dims, method='Powell')
    dims = res.x

    print ('  got page dims', dims[0], 'x', dims[1])

    return dims


def remap_image(name, img, small, page_dims, params):

    height = 0.5 * page_dims[1] * OUTPUT_ZOOM * img.shape[0]
    height = round_nearest_multiple(height, REMAP_DECIMATE)

    width = round_nearest_multiple(height * page_dims[0] / page_dims[1],
                                   REMAP_DECIMATE)

    print ('  output will be {}x{}'.format(width, height))

    height_small = int(height / REMAP_DECIMATE)
    width_small = int(width / REMAP_DECIMATE)
    print('height_small, width_small', height_small, width_small)

    page_x_range = np.linspace(0, page_dims[0], width_small)
    page_y_range = np.linspace(0, page_dims[1], height_small)

    page_x_coords, page_y_coords = np.meshgrid(page_x_range, page_y_range)

    page_xy_coords = np.hstack((page_x_coords.flatten().reshape((-1, 1)),
                                page_y_coords.flatten().reshape((-1, 1))))

    page_xy_coords = page_xy_coords.astype(np.float32)

    image_points = project_xy(page_xy_coords, params)
    image_points = norm2pix(img.shape, image_points, False)

    image_x_coords = image_points[:, 0, 0].reshape(page_x_coords.shape)
    image_y_coords = image_points[:, 0, 1].reshape(page_y_coords.shape)

    image_x_coords = cv2.resize(image_x_coords, (width, height),
                                interpolation=cv2.INTER_CUBIC)

    image_y_coords = cv2.resize(image_y_coords, (width, height),
                                interpolation=cv2.INTER_CUBIC)

    img_gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)

    remapped = cv2.remap(img_gray, image_x_coords, image_y_coords,
                         cv2.INTER_CUBIC,
                         None, cv2.BORDER_REPLICATE)

    thresh = cv2.adaptiveThreshold(remapped, 255, cv2.ADAPTIVE_THRESH_MEAN_C,
                                   cv2.THRESH_BINARY, ADAPTIVE_WINSZ, 25)

    pil_image = Image.fromarray(thresh)
    pil_image = pil_image.convert('1')

    threshfile = name + '_thresh.png'
    pil_image.save(threshfile, dpi=(OUTPUT_DPI, OUTPUT_DPI))

    if DEBUG_LEVEL >= 1:
        height = small.shape[0]
        width = int(round(height * float(thresh.shape[1])/thresh.shape[0]))
        display = cv2.resize(thresh, (width, height),
                             interpolation=cv2.INTER_AREA)
        debug_show(name, 6, 'output', display)

    return threshfile


def main():

    if len(sys.argv) < 2:
        print ('usage:', sys.argv[0], 'IMAGE1 [IMAGE2 ...]')
        sys.exit(0)

    if DEBUG_LEVEL > 0 and DEBUG_OUTPUT != 'file':
        cv2.namedWindow(WINDOW_NAME)

    outfiles = []

    for imgfile in sys.argv[1:]:

        img = cv2.imread(imgfile)
        print(imgfile)
        
        small, resize_to_screen_ratio = resize_to_screen(img)
        basename = os.path.basename(imgfile)
        name, _ = os.path.splitext(basename)

        print ('loaded', basename, 'with size', imgsize(img),)
        print ('and resized to', imgsize(small))

        if DEBUG_LEVEL >= 3:
            debug_show(name, 0.0, 'original', small)
        print('small image size', small.shape)

        pagemask, page_outline = get_page_extents(small)
        #cv2.imshow('pagemask', pagemask)
        print('small image size',small.shape)
        cinfo_list = get_contours(name, small, pagemask, 'text')
        
        print('cinfo_list contour ',cinfo_list )
       
        spans = assemble_spans(name, small, pagemask, cinfo_list)
        #print('spans', spans)
        

        if len(spans) < 3:
            print ('  detecting lines because only', len(spans), 'text spans')
            cinfo_list = get_contours(name, small, pagemask, 'line')
            spans2 = assemble_spans(name, small, pagemask, cinfo_list)
            if len(spans2) > len(spans):
                spans = spans2

        if len(spans) < 1:
            print ('skipping', name, 'because only', len(spans), 'spans')
            continue

        span_points = sample_spans(small.shape, spans)

        print ('  got', len(spans), 'spans',)
        print ('with', sum([len(pts) for pts in span_points]), 'points.')

        corners, ycoords, xcoords = keypoints_from_samples(name, small,
                                                           pagemask,
                                                           page_outline,
                                                           span_points)

        rough_dims, span_counts, params = get_default_params(corners,
                                                             ycoords, xcoords)

        dstpoints = np.vstack((corners[0].reshape((1, 1, 2)),) +
                              tuple(span_points))

        params = optimize_params(name, small,
                                 dstpoints,
                                 span_counts, params)

        page_dims = get_page_dims(corners, rough_dims, params)

        outfile = remap_image(name, img, small, page_dims, params)

        outfiles.append(outfile)

        print ('  wrote', outfile)
        print

    print ('to convert to PDF (requires ImageMagick):')
    print ('  convert -compress Group4 ' + ' '.join(outfiles) + ' output.pdf')


if __name__ == '__main__':
    main()

