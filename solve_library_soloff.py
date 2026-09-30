import sigfig as sgf
import numpy as np
from matplotlib import pyplot as plt
import scipy.optimize as sopt
 

class Soloff_Polynome(dict) :
    def __init__(self, _dict_):
        self._dict_ = _dict_
        self.polynomial_form = _dict_['polynomial_form']

    def pol_form (self, x) :
        """Create the matrix M = f(x) with f the polynomial function of degree 
        (aab : a for x1, x2 and b for x3)
        
        Args:
           x : numpy.ndarray
               Real points x(x1, x2, x3)
           
        Returns:
           M : numpy.ndarray
               M = f(x)
        """
        polynomial_form = self.polynomial_form
        x1,x2,x3 = x
        n = len(x1)
        if   polynomial_form == 111 :
            M = np.asarray ([np.ones((n)),   x1,        x2,        x3])
        elif polynomial_form == 221 :
            x12 = x1 * x1
            x22 = x2 * x2
            M = np.asarray ([np.ones((n)),   x1,        x2,        x3,         x12,
                             x1 *x2,         x22,       x1*x3,     x2*x3])   
        elif polynomial_form == 222 :
            x12 = x1 * x1
            x22 = x2 * x2
            x32 = x3 * x3
            M = np.asarray ([np.ones((n)),   x1,        x2,        x3,         x1**2,
                             x1 *x2,         x2**2,     x1*x3,     x2*x3,      x32])  
        elif polynomial_form == 332 :
            x12 = x1 * x1
            x22 = x2 * x2
            x32 = x3 * x3
            x13 = x1 * x1 * x1
            x23 = x2 * x2 * x2
            M = np.asarray ([np.ones((n)),   x1,        x2,         x3,        x12,
                             x1 *x2,         x22,       x1*x3,      x2*x3,     x32,
                             x13,            x12*x2,    x1*x22,     x23,       x12*x3,
                             x1*x2*x3,       x22*x3,    x1*x32,     x2*x32])            
        elif polynomial_form == 333 :
            x12 = x1 * x1
            x22 = x2 * x2
            x32 = x3 * x3
            x13 = x1 * x1 * x1
            x23 = x2 * x2 * x2
            x33 = x3 * x3 * x3
            M = np.asarray ([np.ones((n)),   x1,        x2,         x3,        x12,
                             x1 *x2,         x22,       x1*x3,      x2*x3,     x32,
                             x13,            x12*x2,    x1*x22,     x23,       x12*x3,
                             x1*x2*x3,       x22*x3,    x1*x32,     x2*x32,    x33])    
        elif polynomial_form == 443 :
            x12 = x1 * x1
            x22 = x2 * x2
            x32 = x3 * x3
            x13 = x1 * x1 * x1
            x23 = x2 * x2 * x2
            x33 = x3 * x3 * x3
            x14 = x1 * x1 * x1 * x1
            x24 = x2 * x2 * x2 * x2
            M = np.asarray ([np.ones((n)),   x1,            x2,         x3,        x12,
                             x1 *x2,         x22,           x1*x3,      x2*x3,     x32,
                             x13,            x12*x2,        x1*x22,     x23,       x12*x3,
                             x1*x2*x3,       x22*x3,        x1*x32,     x2*x32,    x33,
                             x14,            x13*x2,        x12*x22,    x1*x23,    x24,
                             x13*x3,         x12*x2*x3,    x1*x22*x3,  x23*x3,    x12*x32,
                             x1*x2*x32,      x22*x32,       x1*x33,     x2*x33])   
        elif polynomial_form == 444 :
            x12 = x1 * x1
            x22 = x2 * x2
            x32 = x3 * x3
            x13 = x1 * x1 * x1
            x23 = x2 * x2 * x2
            x33 = x3 * x3 * x3
            x14 = x1 * x1 * x1 * x1
            x24 = x2 * x2 * x2 * x2
            x34 = x3 * x3 * x3 * x3
            M = np.asarray ([np.ones((n)),   x1,            x2,         x3,        x12,
                             x1 *x2,         x22,           x1*x3,      x2*x3,     x32,
                             x13,            x12*x2,        x1*x22,     x23,       x12*x3,
                             x1*x2*x3,       x22*x3,        x1*x32,     x2*x32,    x33,
                             x14,            x13*x2,        x12*x22,    x1*x23,    x24,
                             x13*x3,         x12*x2*x3,    x1*x22*x3,  x23*x3,    x12*x32,
                             x1*x2*x32,      x22*x32,       x1*x33,     x2*x33,    x34])   
        elif polynomial_form == 554 :
            x12 = x1 * x1
            x22 = x2 * x2
            x32 = x3 * x3
            x13 = x1 * x1 * x1
            x23 = x2 * x2 * x2
            x33 = x3 * x3 * x3
            x14 = x1 * x1 * x1 * x1
            x24 = x2 * x2 * x2 * x2
            x34 = x3 * x3 * x3 * x3
            x15 = x1 * x1 * x1 * x1 * x1
            x25 = x2 * x2 * x2 * x2 * x2
            M = np.asarray ([np.ones((n)),   x1,            x2,             x3,             x12,
                             x1 *x2,         x22,           x1*x3,          x2*x3,          x32,
                             x13,            x12*x2,        x1*x22,         x23,            x12*x3,
                             x1*x2*x3,       x22*x3,        x1*x32,         x2*x32,         x33,
                             x14,            x13*x2,        x12*x22,        x1*x23,         x24,
                             x13*x3,         x12*x2*x3,     x1*x22*x3,      x23*x3,         x12*x32,
                             x1*x2*x32,      x22*x32,       x1*x33,         x2*x33,         x34,
                             x15,            x14*x2,        x13*x22,        x12*x23,        x1*x24,
                             x25,            x14*x3,        x13*x2*x3,      x12*x22*x3,     x1*x23*x3, 
                             x24*x3,         x13*x32,       x12*x2*x32,     x1*x22*x32,     x24*x32,   
                             x12*x33,        x1*x2*x33,     x22*x33,        x1*x34,         x2*x34])   
        elif polynomial_form == 555 :
            x12 = x1 * x1
            x22 = x2 * x2
            x32 = x3 * x3
            x13 = x1 * x1 * x1
            x23 = x2 * x2 * x2
            x33 = x3 * x3 * x3
            x14 = x1 * x1 * x1 * x1
            x24 = x2 * x2 * x2 * x2
            x34 = x3 * x3 * x3 * x3
            x15 = x1 * x1 * x1 * x1 * x1
            x25 = x2 * x2 * x2 * x2 * x2
            x35 = x3 * x3 * x3 * x3 * x3
            M = np.asarray ([np.ones((n)),   x1,            x2,             x3,             x12,
                             x1 *x2,         x22,           x1*x3,          x2*x3,          x32,
                             x13,            x12*x2,        x1*x22,         x23,            x12*x3,
                             x1*x2*x3,       x22*x3,        x1*x32,         x2*x32,         x33,
                             x14,            x13*x2,        x12*x22,        x1*x23,         x24,
                             x13*x3,         x12*x2*x3,     x1*x22*x3,      x23*x3,         x12*x32,
                             x1*x2*x32,      x22*x32,       x1*x33,         x2*x33,         x34,
                             x15,            x14*x2,        x13*x22,        x12*x23,        x1*x24,
                             x25,            x14*x3,        x13*x2*x3,      x12*x22*x3,     x1*x23*x3, 
                             x24*x3,         x13*x32,       x12*x2*x32,     x1*x22*x32,     x24*x32,   
                             x12*x33,        x1*x2*x33,     x22*x33,        x1*x34,         x2*x34,
                             x35])
        return (M)


    def polynomial_LM_CF (self, a, *x) :
        """Definition of the functionnal F (for curve_fit method)
        
        Args:
           x : numpy.ndarray
               Real points x(x1, x2, x3)
           a : numpy.ndarray
               cst of the polynomial function M = f(x)
           
        Returns:
           Xc : numpy.ndarray
               Calculted position
        """
        polynomial_form = self.polynomial_form
        x = np.array ([x])
        x = x.reshape((3,len(x[0])//3))
        M = Soloff_Polynome({'polynomial_form' : polynomial_form}).pol_form(x)    
        Xc = np.matmul(a, M)
        Xc = Xc.reshape(4*len(x[0]))
        return (Xc)
    
    def polynomial_LM_LS (self, x, X, a) :
        """Definition of the functionnal F (for least_squares method)
        
        Args:
           x : numpy.ndarray
               Real points x(x1, x2, x3)
           X : numpy.ndarray
               Measured points X(Xl1, Xl2, Xr1, Xr2)
           a : numpy.ndarray
               cst of the polynomial function M = f(x)
           
        Returns:
           X-Xc : numpy.ndarray
               Functional calculation
        """
        polynomial_form = self.polynomial_form
        x = np.array ([x])
        x = x.reshape((3,len(x[0])//3))
        M = Soloff_Polynome({'polynomial_form' : polynomial_form}).pol_form(x) 
        Xc = np.matmul(a, M)
        Xc = Xc.reshape(4*len(x[0]))
        F = X-Xc
        return (F)
    
    def polynomial_system (self, x, a) :
        """Create the matrix M = f(x) with f the polynomial function of degree 
        (aab : a for x1, x2 and b for x3)
        
        Args:
           x : numpy.ndarray
               Real points x(x1, x2, x3)
           a : numpy.ndarray
               cst of the polynomial function M = f(x)
           
        Returns:
           M : numpy.ndarray
               M = f(x)
        """
        polynomial_form = self.polynomial_form
        M = Soloff_Polynome({'polynomial_form' : polynomial_form}).pol_form(x)   
        X = np.matmul(a, M)
            
        return(X)    


def fit_plan_to_points(point,
                       title = 'no title'):
    """Plot the median plan from a serie of points
    
    Args:
       point : numpy.ndarray (shape = m,3)
           Real points x(x1, x2, x3)       
       title : str
           Title of the plotted figure
            
    Returns:
       plot points + associated plan
    """
    xs, ys, zs = point 
    ax = plt.subplot(111, projection='3d')
    ax.scatter(xs, ys, zs, color='b')
    
    # do fit
    tmp_A = []
    tmp_b = []
    for i in range(len(xs)):
        tmp_A.append([xs[i], ys[i], 1])
        tmp_b.append(zs[i])
    b = np.matrix(tmp_b).T
    A = np.matrix(tmp_A)
    
    # Manual solution
    fit = (A.T * A).I * A.T * b
    errors = b - A * fit
    residual = np.linalg.norm(errors)
    mean_error = np.mean (abs(errors))
    errors = np.reshape(errors, (len(errors)))
    
    # plot plan
    X,Y = np.meshgrid(np.linspace(np.min(xs), np.max(xs), 10),
                      np.linspace(np.min(ys), np.max(ys), 10))
    Z = np.zeros(X.shape)
    for r in range(X.shape[0]):
        for c in range(X.shape[1]):
            Z[r,c] = fit[0] * X[r,c] + fit[1] * Y[r,c] + fit[2]
    ax.plot_wireframe(X,Y,Z, color='k')
        
    ax.set_title(title)
    ax.set_xlabel('x (mm)')
    ax.set_ylabel('y (mm)')
    ax.set_zlabel('z (mm)')
    
    fit = np.transpose(np.array(fit))[0]
    
    return (fit, errors, mean_error, residual)

def fit_plans_to_points(points, 
                        title = 'no title'):
    """Plot the medians plans from series of points
    
    Args:
       points : numpy.ndarray (shape = l,m,3)
           Real points x(x1, x2, x3)       
       title : str
           Title of the plotted figures
            
    Returns:
       plot points + associated plans
    """
    # plot raw data
    l = len (points)
    fit = np.zeros((l, 3))
    errors = []
    mean_error = np.zeros(l)
    residual = np.zeros(l)
    maxerror = []
    for i in range (len(points)) :
        point = points[i]
        fit[i], errori, mean_error[i], residual[i] = fit_plan_to_points(point, 
                                                                        title = title)
        maxerror.append(np.max(abs(errori)))
        errors.append(errori)
    plt.figure()
    plt.show()    
    print('Plan square max error = ', sgf.round((max(maxerror)), sigfigs =3), ' mm')
    print('Plan square mean error = ', sgf.round((np.mean(mean_error**2))**(1/2), sigfigs = 3), ' mm')
    print('Plan square mean residual = ', sgf.round((np.mean(residual**2))**(1/2), sigfigs = 3))

    return (fit, errors, mean_error, residual)

def refplans(xc1, x3_list) :
    """Plot the medians plans from references points
    
    Args:
       xc1 : numpy.ndarray (shape = 3,n)
           Real points x(x1, x2, x3)       
       x3_list : numpy.ndarray
           List of the different plans coordinates
            
    Returns:
       plot points + associated plans
    """
    m, n = xc1.shape
    x,y,z = xc1
    xcons = []
    p0, pf = 0, 0
    for z_i in x3_list :
        while z[pf] == z_i :
            pf += 1
            if pf > n-1 :
                break
        plan = np.array ([x[p0:pf], y[p0:pf], z[p0:pf]])
        p0 = pf
        xcons.append (plan)

    fit_plans_to_points(xcons, 
                        title = 'Calibration plans')

def least_square_method (Xc1_identified, 
                         Xc2_identified, 
                         A111) :
    """Resolve by least square method the system A . x = X for each points 
    detected and both cameras
    
    Args:
       Xc1_identified : numpy.ndarray
           Real positions of camera 1
       Xc2_identified : numpy.ndarray
           Real positions of camera 2
       A111 : numpy.ndarray
           Constants of the first order calibration polynome
           
    Returns:
       x0 : numpy.ndarray
           Solution x = xsol of the system 
    """
    N = len (Xc1_identified)
    x0 = np.zeros((3, N))
    for i in range (N) :
        X1c1, X2c1 = Xc1_identified[i,0], Xc1_identified[i,1]
        X1c2, X2c2 = Xc2_identified[i,0], Xc2_identified[i,1]
        a1c1, a2c1 = A111[0,0,:], A111[0,1,:]
        a1c2, a2c2 = A111[1,0,:], A111[1,1,:]
    
        A = np.array([a1c1, a2c1, a1c2, a2c2])
        X = np.array([X1c1-a1c1[0], X2c1-a2c1[0], X1c2-a1c2[0], X2c2-a2c2[0]])
        
        A = A[:,1:4]
        At = np.transpose (A)
        J = np.matmul(At, A)
        J_ = np.linalg.inv(J)
        XA = np.matmul(X, A)
        
        x0[:, i] = np.matmul(J_, XA)
    
    return (x0)    


def Levenberg_Marquardt_solving (Xc1_identified, 
                                 Xc2_identified, 
                                 A, 
                                 x0, 
                                 polynomial_form, 
                                 method = 'curve_fit') :
    """Resolve by Levenberg-Marcquardt method the system A . x = X for each 
    points detected and both cameras
    
    Args:
        Xc1_identified : numpy.ndarray
            Real positions of camera 1
        Xc2_identified : numpy.ndarray
            Real positions of camera 2
        A : numpy.ndarray
            Constants of the calibration polynome
        x0 : numpy.ndarray
            Initial guess
        polynomial_form : int
            Polynomial form
        method : str
            Chosen method of resolution. Can take 'curve_fit' or 'least_squares'
           
    Returns:
        xopt : numpy.ndarray
            Solution of the LM resolution
        Xcalculated : numpy.ndarray
            Solution calculated
        Xdetected : numpy.ndarray
            Solution detected (Xc1_identified, Xc2_identified)
    """   

    from joblib import Parallel, delayed, dump, load
    import os
    core_number = os.cpu_count()
    # folder = './joblib_memmap'
    # try:
    #     os.mkdir(folder)
    # except FileExistsError:
    #     pass  

    N = len(x0[0])    
    Xdetected = np.array([Xc1_identified[:,0], 
                          Xc1_identified[:,1], 
                          Xc2_identified[:,0], 
                          Xc2_identified[:,1]])
    A0 = np.array([A[0,0], A[0,1], A[1,0], A[1,1]])
    xopt = np.zeros((3,N))
    # data_filename_memmap = os.path.join(folder, 'data_memmap')
    # dump(Xdetected, data_filename_memmap)
    # Xdetected = load(data_filename_memmap, mmap_mode='r')
    
    win_size = Xdetected.shape[1]/core_number
    slices = []
    for i in range (core_number) :
        start = i*win_size
        slices.append(slice(round(start), round(start + win_size)))
    
    def xopt_solve (X, sl) :
        Ns = sl.stop - sl.start
        xopt = np.zeros((3*Ns))
        Xdetected_part = X[:,sl]
        x0_part = x0[:,sl]
        for i in range (Xdetected_part.shape[1]) :
            X0i = Xdetected_part[:,i]
            x0i = x0_part[:,i]
            xopti, pcov = sopt.curve_fit(Soloff_Polynome({'polynomial_form' : polynomial_form}).polynomial_LM_CF, 
                                        A0, 
                                        X0i, 
                                        p0 = x0i, 
                                        method ='lm')
            xopt[i], xopt[Ns + i], xopt[2*Ns + i] = xopti
        return (xopt)

    xopt_parallel = Parallel(n_jobs=8)(delayed(xopt_solve)(Xdetected, sl) for sl in slices)

    for part in range (len(xopt_parallel)) :
        sl = slices[part]
        xopt_part = xopt_parallel[part]
        xopt[:,sl] = xopt_part.reshape((3,sl.stop - sl.start))
        
    
    Xcalculated = Soloff_Polynome({'polynomial_form' : polynomial_form}).polynomial_system(xopt, A0)
    Xdiff = np.absolute(Xcalculated - Xdetected)
    print(str(polynomial_form), ' : The max error between detected and calculated points is ', np.max(Xdiff), ' pixels.')
    
    return (xopt, Xcalculated, Xdetected)

