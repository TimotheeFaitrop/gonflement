from glob import glob
import numpy as np
import math
import matplotlib.pyplot as plt
import sys
import skimage.feature as sfe
import skimage.filters as sfi
from skimage.measure import label, regionprops
from skimage.segmentation import clear_border
import cv2
import cv2.aruco as aruco


class Calibrate(dict):
    """Identification class of the corners of a chessboard by 
        Charuco's method"""
    def __init__(self, 
                 _dict_):
        self._dict_ = _dict_
        # ncx, ncy, sqr, mrk = pattern_cst(pattern)
        self.ncx = _dict_['ncx']
        self.ncy = _dict_['ncy']
        self.sqr = _dict_['sqr']
        self.mrk = self.sqr / 2
        self.dictionary = aruco.Dictionary_get(aruco.DICT_6X6_250)
        self.parameters = aruco.DetectorParameters_create()
        self.parameters.adaptiveThreshWinSizeMax = 300
        self.board = aruco.CharucoBoard_create(
            self.ncx,
            self.ncy,
            self.sqr,
            self.mrk,
            self.dictionary)
    
    def calibrate(self, 
                  im):
        """ Detection of the corners
        
        Args:
            im : str
                Image path to detect
            
        Returns:
            corners_list : list (Dim = N * 3)
                List of the detected corners 
        """
        if len (im) < 20 :
            print("=> Calculation of the image ...", str(im))
        else :
            print("=> Calculation of the image ...", str(im[-20:]))
        img = cv2.imread(im, 0)        
        corners, ids, rip = aruco.detectMarkers(img, 
                                                self.dictionary, 
                                                parameters=self.parameters)
        
        if len(corners) != 0 :
            if len(corners) < len(self.board.ids):
                for idd in self.board.ids:
                    if idd not in ids:
                        print("mark ", idd, " not detected")
                        
            if ids is not None and len(ids) > 0:
                ret, chcorners, chids = aruco.interpolateCornersCharuco(
                    corners, ids, img, self.board)
                print(len(corners), ' marks detected. ', ret, ' points detected')
                print('---')
                corners_list = []
                BU = []
                for i in range (0, len(chcorners)) :
                    BU.append(chcorners[i][0])
                    corners_list.append([BU[i][0],BU[i][1],chids[i][0]])
        else :
            corners_list = False
        return (corners_list, ret) 
    
    def complete_missing_points (self, 
                                 corners_list, 
                                 im, 
                                 hybrid_verification = False) :  
        """ Detection of the corners with Hessian invariants filtering
        
        Args:
            corners_list : numpy.array
                Array of the detected points (automatically with ChAruco) 
            im : str
                Image path to detect
            hybrid_verification : bool, optional
                If True, verify each pattern detection and propose to pick 
                manually the bad detected corners. The image with all detected
                corners is show and you can decide to change any point using
                it ID (ID indicated on the image) as an input. If there is no
                bad detected corner, press ENTER to go to the next image.
            
        Returns:
            corners_list_opt : list (Dim = N * 3)
                List of the detected corners (automatically with ChAruco and 
                                              Hessian invariants + manually)
        """                        
        corners_list_opt = np.asarray(corners_list)
        x, y, ids = np.transpose(corners_list_opt)
        img = cv2.imread(im, 0)

        # Filter the image with the Hessian matrix parameters to detect the 
        # corners (points)
        img_hess = plt.imread(im)
        HE0, HE1 = sfe.hessian_matrix_eigvals(sfe.hessian_matrix(img_hess, 9))
        HE = abs(HE0 * HE1)
        thresh = sfi.threshold_otsu(HE)
        bin_im = HE > thresh
        
        # Plot the already detected points
        if hybrid_verification :
            fig0, ax = plt.subplots()
            plt.imshow(img_hess, cmap='gray')
            plt.scatter(x,y, c='r')
            for name, txt in enumerate(ids):
                ax.annotate(txt, (x[name], y[name]))
        
        # Choose 2 points A and B already detected that could create 
        # the referential
        nx, ny = self.ncx-1, self.ncy-1
        n_corners = nx*ny
        pts_list = np.arange(n_corners)
        pts_list = np.reshape(pts_list, (ny,nx))
        ptA = corners_list_opt[0]
        xA, yA, idA = ptA
        lineA, columnA = np.where(pts_list==idA)
        pts_list_cut = np.delete(pts_list, lineA, 0)
        pts_list_cut = np.delete(pts_list_cut, columnA, 1)
        pts_list_cut = np.ravel(pts_list_cut)
        ptB = []
        out_of_range_points = 0
        for pt in pts_list_cut :
            if np.any(corners_list_opt[:,2] == pt) :
                lineB, columnB = np.where(pts_list == pt)
                line, column = np.where(corners_list_opt == pt)
                ptB = corners_list_opt[line]
                xB, yB, idB = ptB[0]
                break
            
        if np.any(ptB) :
            # Define the referencial coordinates of the pattern grid
            nx = columnB - columnA
            ny = lineB - lineA
            dx = xB - xA
            dy = yB - yA
            dP = math.sqrt(dx**2 + dy**2)
            l = dP / math.sqrt(nx**2 + ny**2)
            alpha = math.atan(-dy/dx)
            if dx < 0 :
                alpha += math.pi
            alpha2 = math.atan(ny/nx)
            if nx < 0 :
                alpha2 += math.pi
            alpha1 = alpha - alpha2
            xx = l * math.cos(alpha1)
            xy = - l * math.sin(alpha1)
            yy = - l * math.cos(alpha1)
            yx = - l * math.sin(alpha1)
        
            # Define the origine point
            d0x = columnA * xx + lineA * yx
            d0y = columnA * xy + lineA * yy
            x0 = xA - d0x
            y0 = yA - d0y
        
            # Find the holes
            for id_ in np.ravel(pts_list) :
                if np.any(corners_list_opt[:,2] == id_) :
                    # Point already detected
                    ()
                else : 
                    # Find the missing point
                    line2, column2 = np.where(pts_list == id_)
                    dix = column2 * xx + line2 * yx
                    diy = column2 * xy + line2 * yy
                    xi = int(x0 + dix)
                    yi = int(y0 + diy)
                    d = int(l//2)
                    
                    # Find the missing point, if on the screen
                    xm, ym = img.shape
                    if (xm < int(yi+d)) or (ym < int(xi+d)) or (0> int(yi-d)) or (0> int(xi-d)) :
                        out_of_range_points += 1
                        bary, barx = np.nan, np.nan
                    else :
                        # Try Hessian detection and pick the biggest binary 
                        # area
                        bin_im_win = bin_im[yi-d:yi+d, xi-d:xi+d]
                        # im_focus = img_hess[yi-d:yi+d, xi-d:xi+d]
                        label_img=label(clear_border(bin_im_win))
                        regions = regionprops(label_img)
                        areas = []
                        for region in (regions):
                            areas.append(region.area)
                        if any (areas) :
                            max_area = max(areas)
                            max_i = areas.index(max_area)
                            region = regions[max_i]
                            bary, barx = region.centroid
                        else :
                            bary, barx = np.nan, np.nan
                    y_dot = bary + yi - d
                    x_dot = barx + xi - d
    
                    arr = np.array([x_dot, y_dot, id_])
                    if hybrid_verification :
                        plt.annotate(id_, (x_dot, y_dot))
                        plt.scatter(x_dot, y_dot, c='b', label = 'Hessian')
    
                    corners_list_opt = np.insert(corners_list_opt, 
                                                 id_, 
                                                 arr, 
                                                 axis=0)
                         
            # Plot the points of interest
            # if hybrid_verification :
            #     plt.scatter(x0,y0, c='g')
            #     plt.scatter(x0 + xx, y0 + xy, c='c')
            #     plt.scatter(x0 + yx, y0 + yy, c='c')
            #     plt.scatter(xA, yA, c='m')
            #     plt.scatter(xB, yB, c='y')           
            #     plt.imsave('Temp_plot.png', corners_list_opt)
            #     plt.ion()
            #     plt.show()
            while hybrid_verification :
                plt.pause(0.001)
                print('')
                print('Choose a bad detected corner if any. If None is, press Enter')
                txt = input()
                if txt =='' :
                    print('End correction')
                    plt.close()
                    break
                else :
                    if any (txt) in corners_list_opt[:,2] :
                        # If the Hessian detection is bad, manualy detection
                        # missing_points = [0, 0]
                        def onclick(event):
                            global missing_points
                            missing_points = [event.xdata, event.ydata]
                            plt.close()
                        id_ = int(txt)
                        line2, column2 = np.where(pts_list == id_)
                        dix = column2 * xx + line2 * yx
                        diy = column2 * xy + line2 * yy
                        xi = int(x0 + dix)
                        yi = int(y0 + diy)
                        fig, ax = plt.subplots()
                        plt.imshow(img[int(yi-d):int(yi+d), int(xi-d):int(xi+d)], cmap='gray')
                        fig.canvas.mpl_connect('button_press_event', onclick)
                        plt.title('Click on the missing corner')
                        plt.show()
                        plt.waitforbuttonpress()
                        plt.pause(0.001)
                        xi = xi+missing_points[0]-d
                        yi = yi+missing_points[1]-d
                        fig, ax = plt.subplots()
                        plt.imshow(img[int(yi-10):int(yi+10), int(xi-10):int(xi+10)], cmap='gray')
                        fig.canvas.mpl_connect('button_press_event', onclick)
                        plt.title('Click again')
                        plt.show()
                        plt.waitforbuttonpress()
                        xi = xi+missing_points[0]-10
                        yi = yi+missing_points[1]-10
                        arr = np.array([xi, yi, id_])
                        print('arr ', arr)
                        # print(corners_list)
                        corners_list_opt[id_] = arr
                        fig0
                        plt.scatter(xi,yi,c='g')
                    else :
                        print('No corner with the id ', txt, ' chose another one')

                    
        else :
            print('Impossible to detect manualy corners of image : ', im)
            corners_list_opt = False
        print (out_of_range_points, ' points out of the image or to close to the border')
        return (corners_list_opt)

   
def calibration_model(nx, 
                      ny, 
                      l) : 
    """ Creation of the model of the calibration pattern
    
    Args:
        nx : int
            Number of x squares
        ny : int
            Number of y squares
        l : int
            Size of a square
        
    Returns:
        Xref : list (Dim = N * 3)
            List of the real corners
            
    """
    Xref = []
    for i in range (0, ny-1) :
        for j in range (0, nx-1) :
            Xref.append([(nx-(j+1))*l, (i+1)*l, j+(ny-1)*i])
    return Xref


def NAN_calibration_model (Images, 
                           Xref, 
                           __dict__,
                           hybrid_verification = False) :
    """ Group all of the images detected and filter the points not detected. 
        For each corners not detected on an image, replace the points with NAN. 
    
    Args:
        Images : list
            List of the detected corners
        Xref : list
            List of the real corners
        pattern : str
            Name of the pattern used ('macro' or 'micro')
        hybrid_verification : bool, optional
            If True, verify each pattern detection and propose to pick 
            manually the bad detected corners. The image with all detected
            corners is show and you can decide to change any point using
            it ID (ID indicated on the image) as an input. If there is no
            bad detected corner, press ENTER to go to the next image.
        
    Returns:
        all_x : np.array (Dim = Nimages * N * 3)
            Array of the real corners
        all_X : np.array (Dim = Nimages * N * 3)
            Array of the detected corners
            
    """    
    M = len(Images)
    
    # First, detect the holes = missing points
    Nall = len(Xref)
    nb_pts = np.zeros(M)
    all_X = np.zeros((M, Nall, 3))
    for i in range (0, M) :
        im = sorted(glob(Images[i]))[0]
        corners_list, pts = Calibrate(__dict__).calibrate(im)
        nb_pts[i] = pts
        corners_list = np.asarray(corners_list)
        corners_list = Calibrate(__dict__).complete_missing_points(corners_list, 
                                                                   im,
                                                                   hybrid_verification = hybrid_verification)
        all_X[i] = corners_list

    all_x = []
    for i in range (0, M) :
        all_x.append(Xref)        
    # Use it as array
    all_x = np.asarray(all_x)
    all_x = all_x[:, :, [0, 1]]
    all_X = all_X[:, :, [0, 1]]
    nb_pts = np.reshape(nb_pts, (2, M//2))
    return (all_x, all_X, nb_pts)


def pattern_detection (__dict__,
                       detection = True,
                       saving_folder = 'Folders_npy',
                       hybrid_verification = False) :
    """Detect the corners of Charucco's pattern.
    
    Args:
       __dict__ : dict
           Pattern properties define in a dict.
       detection : bool, optional
           If True, all the analysis will be done. If False, the code will take 
           the informations in 'saving_folder'
       saving_folder : str, optional
           Folder to save datas
       hybrid_verification : bool, optional
           If True, verify each pattern detection and propose to pick 
           manually the bad detected corners. The image with all detected
           corners is show and you can decide to change any point using
           it ID (ID indicated on the image) as an input. If there is no
           bad detected corner, press ENTER to go to the next image.

    Returns:
       all_X : numpy.ndarray
           The corners of the pattern detect by the camera ranged in an array 
           arrange with all left pictures followed by all right pictures. 
           Expl : [left_picture_1, left_picture_2, right_picture_1, 
                   right_picture_2]
       all_x : numpy.ndarray
           The theorical corners of the pattern
    """
    # Taking the main parameters from bibliotheque_data_eddy.
    left_folder = __dict__['left_folder']
    right_folder = __dict__['right_folder']
    name = __dict__['name']
    ncx = __dict__['ncx']
    ncy = __dict__['ncy']
    sqr = __dict__['sqr']
    Images_left = sorted(glob(str(left_folder) + '/*'))
    Images_right = sorted(glob(str(right_folder) + '/*'))
    Images = Images_left
    for i in range (len(Images_right)) :
        Images.append(Images_right[i])
    Save_Ucam_Xref = [str(saving_folder) + "/all_X_" + name + ".npy", 
                      str(saving_folder) + "/all_x_" + name + ".npy", 
                      str(saving_folder) + "/nb_pts_" + name + ".npy"]

    # Corners detection
    if detection :
        print('    - Detection of the pattern in progress ...')
        # Creation of the theoretical pattern + detection of camera's pattern
        Xref = calibration_model(ncx, ncy, sqr)
        all_x, all_X, nb_pts = NAN_calibration_model(Images, 
                                                     Xref, 
                                                     __dict__,
                                                     hybrid_verification = hybrid_verification)

        if not np.any(all_X[0]):
            print('Not any point detected in all images/cameras')
        else :
            np.save(Save_Ucam_Xref[0], all_X)
            np.save(Save_Ucam_Xref[1], all_x)
            np.save(Save_Ucam_Xref[2], nb_pts)
    
            print('    - Saving datas in ', saving_folder)
    # Taking pre-calculated datas from the saving_folder
    else :
        print('    - Taking datas from ', saving_folder)        
        all_X = np.load(Save_Ucam_Xref[0])
        all_x = np.load(Save_Ucam_Xref[1])
        nb_pts = np.load(Save_Ucam_Xref[2])
        
    return(all_X, all_x, nb_pts)


def camera_np_coordinates (all_X, 
                           all_x, 
                           x3_list) :
    """Organising the coordinates of the calibration
    
    Args:
       all_X : numpy.ndarray
           The corners of the pattern detect by the camera
       all_x : numpy.ndarray
           The theorical corners of the pattern
       x3_list : numpy.ndarray
           List of the different z position. (Ordered the same way in the 
           target folder)
       saving_folder : str, optional
           Where to save datas
    Returns:
       x : numpy.ndarray
           Organised real positions in 3D space
       Xc1 : numpy.ndarray
           Organised detected positions of camera 1
       Xc2 : numpy.ndarray
           Organised detected positions of camera 2
    """
    for i in [1, 2] :
        print('')
        mid = all_X.shape[0]//2    
        all_Xi = all_X[(i-1)*mid:i*mid,:,:]
        all_xi = all_x[i*(mid-1):i*mid,:,:]
        sU = all_Xi.shape
        Xref = all_xi[0]
        all_xi = np.empty ((sU[0], sU[1], sU[2]+1))
        x = np.empty ((sU[0] * sU[1], sU[2]+1))
        X = np.empty ((sU[0] * sU[1], sU[2]))
        for j in range (sU[0]) :
            all_xi[j][:,0] = Xref[:,0]
            all_xi[j][:,1] = Xref[:,1]
            all_xi[j][:,2] = x3_list[j]

            x[j*sU[1] : (j+1)*sU[1], :]  = all_xi[j]
            X[j*sU[1] : (j+1)*sU[1], :]  = all_Xi[j]

        # Real position in space : Xref (x1, x2, x3)
        x1 = x[:,0]
        x2 = x[:,1]
        x3 = x[:,2]
        x = np.asarray([x1,x2,x3]) # reshape x

        # Position detected from cameras : Ucam (X1, X2)
        X1 = X[:,0]
        X2 = X[:,1]
        X = np.asarray([X1,X2]) # reshape X
        
        if i == 1 :
            Xc1 = X
        if i == 2 :
            Xc2 = X
    # If there is some NAN value, then delete all 2D and 3D corresponding 
    # points
    if np.isnan(Xc1).any() or np.isnan(Xc2).any() :
        mask1 = np.ma.masked_invalid(Xc1)
        mask2 = np.ma.masked_invalid(Xc2)
        mask = mask1.mask + mask2.mask
        Xc1 = Xc1[np.logical_not(mask)]
        Xc1 = np.reshape(Xc1, (2, len(Xc1)//2))
        Xc2 = Xc2[np.logical_not(mask)]
        Xc2 = np.reshape(Xc2, (2, len(Xc2)//2))
        mask = mask[0]
        x1 = x1[np.logical_not(mask)]
        x2 = x2[np.logical_not(mask)]
        x3 = x3[np.logical_not(mask)]
        x = np.asarray([x1,x2,x3])
    else :
        mask = np.array([False])
        
    return (x, Xc1, Xc2)
    
