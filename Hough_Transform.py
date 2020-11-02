import numpy as np
import cv2
from scipy.spatial import distance

roi_defined = False
video_name = ['Antoine_Mug', 'VOT-Car', 'VOT-Sunshade', 'VOT-Woman', 'VOT-Basket', 'VOT-Ball']

threshold = 100
experience = video_name[3]

cap = cv2.VideoCapture('Test-Videos/'+experience+'.mp4')


def f_dst_weights(frame, x,y,w,h):
    X, Y, _ = frame.shape
    weights = np.zeros((X, Y)) + 0.15

    # defining a zone of curiosity
    ww = min(x+int(1.5*w), X) - max(x-int(w/2), 0)
    hh = min(y+int(1.5*h), Y) - max(y-int(h/2), 0)
    template = np.indices((ww, hh))
    template[0] += max(x-int(w/2), 0)
    template[1] += max(y-int(h/2), 0)

    # the center from which the distance will be counted
    target = np.array([[x+int(w/2),y+int(h/2)]])

    # Calculate the distance from the center to all points of interest.
    d = distance.cdist(template.reshape(2, ww*hh).T, target, 'euclidean').reshape(ww,hh)
    # we use the Gaussian distribution to transform the distance
    std = 25
    gaussian = (1/(std*((2*np.pi)**0.5)))*np.exp( -((d)**2)/(2*std*std) )
    # normalization
    cv2.normalize(gaussian, gaussian, 0.15, 1, cv2.NORM_MINMAX)
    # Creating weights for the density.
    weights[max(x-int(w/2), 0):min(x+int(1.5*w), X), max(y-int(h/2), 0): min(y+int(1.5*h), Y)] = gaussian
    # cv2.imshow('Weights', weights)
    return weights

def get_gradient_magnitude(frame_g):
    dx = cv2.Sobel(frame_g,cv2.CV_64F,1,0,ksize=3)
    dy = cv2.Sobel(frame_g,cv2.CV_64F,0,1,ksize=3)
    # Compute the magnitude of the gradient
    return  np.hypot(dx,dy).astype('uint8')


def get_gradient_orientation(frame_g):
    dx = cv2.Sobel(frame_g,cv2.CV_64F,1,0,ksize=3)
    dy = cv2.Sobel(frame_g,cv2.CV_64F,0,1,ksize=3)
    # Compute the orientation
    return  (np.arctan2(dy,dx) * 180 / np.pi)


def build_r_table(obj):
    X,Y =  obj.shape
    gradient_magnitude = get_gradient_magnitude(obj)
    _ , filtered = cv2.threshold(gradient_magnitude, threshold, 255, cv2.THRESH_BINARY)
    cv2.imshow('r_table', filtered)
    orientation = get_gradient_orientation(filtered)
    orientation[filtered == 0] = -255
    unique_orientation = np.unique(orientation)

    r_table = dict()
    center = np.array([[int(X/2) ,int(Y/2)]])

    for teta in unique_orientation:
        if teta == -255:
            continue
        r_table[teta] = center - np.argwhere(orientation == teta)
    return r_table


def transform_hough(image, r_table, x,y,w,h):

    X, Y = image.shape
    gradient_magnitude = get_gradient_magnitude(image)
    _ , filtered = cv2.threshold(gradient_magnitude, threshold, 255, cv2.THRESH_BINARY)
    orientation = get_gradient_orientation(filtered)
    orientation[filtered == 0] = -255
    backtorgb = cv2.cvtColor(filtered,cv2.COLOR_GRAY2RGB)
    backtorgb[np.where((backtorgb==[0,0,0]).all(axis=2))] = [0,0,255]
    cv2.imshow('get_gradient_orientation', backtorgb)
    vote = np.zeros(image.shape)

    for teta in r_table:
        tmp = np.argwhere(orientation == teta)
        if tmp.shape[0] == 0 :
            continue
        for r in r_table[teta]:
            ind_for_vote = tmp + r
            ind_for_vote = ind_for_vote[ (ind_for_vote[:,0] < X) & (ind_for_vote[:,0] > 0) &(ind_for_vote[:,1] < Y) & (ind_for_vote[:,1] > 0)  ]
            vote[ind_for_vote[:,0], ind_for_vote[:,1]] += 1
    vote[max(x-w, 0):min(x+2*w, X), max(y - h, 0):min(y+2*h, Y)] += 200
    centers = np.argwhere(vote == np.amax(vote))
    center = centers.mean(axis = 0).astype('int')
    return center[0], center[1]

def define_ROI(event, x_p, y_p, flags, param):
    global x,y,w,h,roi_defined
    # if the left mouse button was clicked,
    # record the starting ROI coordinates
    if event == cv2.EVENT_LBUTTONDOWN:
        x, y = x_p, y_p
        roi_defined = False
    # if the left mouse button was released,
    # record the ROI coordinates and dimensions
    elif event == cv2.EVENT_LBUTTONUP:
        x2, y2 = x_p, y_p
        w = abs(x2-x)
        h = abs(y2-y)
        x = min(x,x2)
        y = min(y,y2)
        roi_defined = True

x,y,w,h = None, None, None, None

# take first frame of the video
ret,frame = cap.read()
# load the image, clone it, and setup the mouse callback function
clone = frame.copy()
cv2.namedWindow("First image")
cv2.setMouseCallback("First image", define_ROI)

# keep looping until the 'q' key is pressed
while True:
    # display the image and wait for a keypress
    cv2.imshow("First image", frame)
    key = cv2.waitKey(1) & 0xFF
    # if the ROI is defined, draw it!
    if (roi_defined):
        # draw a green rectangle around the region of interest
        cv2.rectangle(frame, (x,y), (x+w,y+h), (0, 255, 0), 2)
    # else reset the image...
    else:
        frame = clone.copy()
    # if the 'q' key is pressed, break from the loop
    if key == ord("q"):
        break

track_window = (x,y,w,h)
new_x = x
new_y = y
# set up the ROI for tracking
roi = frame[y:y+h+1, x:x+w+1]

# cv2.imshow('roi',roi)
# conversion to Hue-Saturation-Value space
# 0 < H < 180 ; 0 < S < 255 ; 0 < V < 255
hsv_roi =  cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
grey_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)


RT = build_r_table(grey_roi)

# computation mask of the histogram:
# Pixels with S<30, V<20 or V>235 are ignored
mask = cv2.inRange(hsv_roi, np.array((0.,30.,20.)), np.array((180.,255.,235.)))

# Marginal histogram of the Hue component
roi_hist = cv2.calcHist([hsv_roi],[0],mask,[180],[0,180])
# Histogram values are normalised to [0,255]
cv2.normalize(roi_hist,roi_hist,0,255,cv2.NORM_MINMAX)
roi_hist_start = roi_hist.copy()
# Setup the termination criteria: either 10 iterations,
# or move by less than 1 pixel
term_crit = ( cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 10, 1 )

cpt = 1
while(1):
    ret ,frame = cap.read()
    if ret == True:
        X, Y, _ = frame.shape
        frame_c = frame.copy()
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        dst = cv2.calcBackProject([hsv],[0],roi_hist,[0,180],1)

        m_dst = f_dst_weights(frame, y,x,h,w)
        tmp = dst*m_dst
        tmp = tmp.astype('uint8')

        frame_g = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)



        new_x, new_y = transform_hough(frame_g, RT, new_y,new_x,w,h)
        frame_tracked_Hofe = cv2.rectangle(frame, (new_y - int(w/2), new_x-int(h/2)), (new_y+int(w/2),new_x+int(h/2)), (0,0,255) ,2)

        cv2.imshow('frame_tracked_Hofe',frame_tracked_Hofe)

        gradient_magnitude = get_gradient_magnitude(frame_g)
        _ , filtered = cv2.threshold(gradient_magnitude, threshold, 255, cv2.THRESH_BINARY)
        cv2.imshow('filtered_gradient_magnitude', filtered)
        # apply meanshift to dst to get the new location
        ret, track_window = cv2.meanShift(tmp, track_window, term_crit)

        # Draw a blue rectangle on the current image
        x,y,w,h = track_window
        frame_tracked = cv2.rectangle(frame, (x, y), (x+w,y+h), (255,0,0) ,2)
        cv2.imshow('Sequence',frame_tracked)

        roi_t = frame_c[y:y+h+1, x:x+w+1]
        # conversion to Hue-Saturation-Value space
        # 0 < H < 180 ; 0 < S < 255 ; 0 < V < 255
        hsv_roi_t =  cv2.cvtColor(roi_t, cv2.COLOR_BGR2HSV)
        # computation mask of the histogram:
        # Pixels with S<30, V<20 or V>235 are ignored
        mask_t = cv2.inRange(hsv_roi_t, np.array((0.,30.,20.)), np.array((180.,255.,235.)))
        # Marginal histogram of the Hue component
        roi_hist_t = cv2.calcHist([hsv_roi_t],[0],mask_t,[180],[0,180])
        # Histogram values are normalised to [0,255]
        cv2.normalize(roi_hist_t,roi_hist_t,0,255,cv2.NORM_MINMAX)

        tmp = abs(np.sum( roi_hist -  roi_hist_t ))

        k = cv2.waitKey(60) & 0xff

        if k == 27:
                break
        elif k == ord('s'):
            cv2.imwrite('output/' + experience + '/' + experience + 'Frame_%04d.png' % cpt, frame_tracked)
            cv2.imwrite('output/' + experience + '/' + experience + 'frame_g_Frame_%04d.png' % cpt, frame_g)
            cv2.imwrite('output/' + experience + '/' + experience + 'filtered_Frame_%04d.png' % cpt, filtered)
        cpt += 1
    else:
        break

cv2.destroyAllWindows()
cap.release()
