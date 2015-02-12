from ..FeatureExtractor import FeatureExtractor, InterExtractor

import numpy
import scipy.integrate

class lcmodel_extractor(InterExtractor):
    """ Base class for the unfolded lightcurve model features.
    dstarr coded 2012-07-20

    Gaussian Kernel smoothing adapted from I.Shivvers' delta_hase_2minima_extractor.py
    """
    internal_use_only = False # if set True, then seems to run all X code for each sub-feature
    active = True # if set False, then seems to run all X code for each sub-feature
    extname = 'lcmodel' #extractor's name

    def debug_compare_gp_and_shivv_models(self, X, y, dy, shivv_model, debug_x=[], debug_y=[], pos_delta_mag=None, neg_delta_mag=None):
        """ Compare & Plot the fit generated by Shivver's code and the
        scikits GaussianProcess function

        For debugging only.
        """
        #####
        import numpy as np
        from sklearn.gaussian_process import GaussianProcess
        from matplotlib import pyplot as pl

        t_min = numpy.min(X)
        t_max = numpy.max(X)
        x = np.atleast_2d(np.linspace(t_min, t_max, 10000)).T

        X = np.atleast_2d(X).T

        ### Instanciate a Gaussian Process model
        #gp = GaussianProcess(corr='squared_exponential', theta0=1e-3,
        #                     thetaL=1e-3, thetaU=1,
        #                     nugget=(dy / y) ** 2,
        #                     random_start=20)
        gp = GaussianProcess(corr='absolute_exponential', theta0=1e-3,
                             nugget=(dy / y) ** 2,
                             random_start=10)
        # Fit to data using Maximum Likelihood Estimation of the parameters
        gp.fit(X, y)

        # Make the prediction on the meshed x-axis (ask for MSE as well)
        y_pred, MSE = gp.predict(x, eval_MSE=True)
        sigma = np.sqrt(MSE)
        # Plot the function, the prediction and the 95% confidence interval based on
        # the MSE
        from matplotlib import rcParams
        rcParams.update({'legend.fontsize':8})
        ms = 4
        fig = pl.figure()
        pl.plot(x, [numpy.median(y)]*len(x), 'c', label='median')
        #pl.plot(x, [numpy.mean(y)]*len(x), 'm', label=u'mean')
        #pl.plot(X, y, 'r:', label=u'orig $m(t)$')
        pl.errorbar(X.ravel(), y, dy, fmt='ro', ms=5, label='Observations')
        pl.plot(X, shivv_model, 'g', ms=ms, label='Shivvers model')
        pl.plot(X, shivv_model, 'go', ms=ms)
        pl.plot(x, y_pred, 'b-', ms=ms, label='exp corr prediction')
        pl.fill(np.concatenate([x, x[::-1]]), \
                np.concatenate([y_pred - 1.9600 * sigma,
                               (y_pred + 1.9600 * sigma)[::-1]]), \
                alpha=.5, fc='b', ec='None', label='95% confidence interval')
        if len(debug_x) > 0:
            pl.plot(debug_x, debug_y, 'y*', ms=10, label='cross threshhold')
        if pos_delta_mag != None:
            pl.plot(x, [pos_delta_mag]*len(x), 'y', label='median delta thresh')
            pl.plot(x, [neg_delta_mag]*len(x), 'y', label='median delta thresh')
            

        pl.xlabel('$t$')
        pl.ylabel('$m(t)$')
        pl.legend(loc='upper left')
        srcid = 244888
        img_fpath = '/home/dstarr/scratch/lcmodel_feature_asas_examples/%d.png' % (srcid)
        pl.title("Source ID=%d" % (srcid))
        pl.savefig(img_fpath)
        #import os
        #os.system("eog %s" % (img_fpath))
        #pl.show()   
        #import pdb; pdb.set_trace()
        #print
        

    def get_dmag_at_median_threshold(self, sign, normalized_model_mags):
        """
        """
        if sign == 'pos':
            thresh_list = numpy.linspace(0,numpy.max(normalized_model_mags),20)
        elif sign == 'neg':
            thresh_list = numpy.linspace(numpy.min(normalized_model_mags),0,20)
        thresh_passthru = numpy.zeros(len(thresh_list), dtype=numpy.int)
        for i_th, thresh in enumerate(thresh_list):
            if sign == 'pos':
                past_thresh = numpy.where(normalized_model_mags > thresh)[0]
            elif sign == 'neg':
                past_thresh = numpy.where(normalized_model_mags < thresh)[0]#[::-1]
            j_prev = -10 # some value < -1
            for j in past_thresh:
                if j-1 == j_prev:
                    j_prev = j
                    continue # we've already caught this threshold passthrough
                thresh_passthru[i_th] += 1
                j_prev = j

        sum_n_passthru_2 = numpy.sum(thresh_passthru)/2.
        cumul = 0
        delta_mag_median = 0. # This should always get a found value.
        for i, n in enumerate(thresh_passthru):
            cumul += n
            if cumul >= (sum_n_passthru_2):
                delta_mag_median = thresh_list[i]
                break

        """
        from matplotlib import pyplot as pl
        fig = pl.figure()
        pl.plot(thresh_list, thresh_passthru, 'bo')
        pl.xlabel('(threshold mag - median mag)')
        pl.ylabel('N intersects for single direction')

        srcid = 244888
        pl.title("Source ID=%d" % (srcid))
        img_fpath = '/home/dstarr/scratch/lcmodel_feature_asas_examples/%d_%s_thresh.png' % (srcid, sign)
        pl.savefig(img_fpath)
        #pl.show()   
        pl.clf()
        """

        return {'delta_mag_median':delta_mag_median,
                'n_thresh_median':n}
                

    def get_n_passing_median(self, normalized_model_mags):
        """ Get number of positive slope intersections of delta_mag=0.0 median
        """
        past_thresh = numpy.where(normalized_model_mags > 0.0)[0]
        n_thresh_at_median = 0
        j_prev = -10 # some value < -1
        for j in past_thresh:
            if j-1 == j_prev:
                j_prev = j
                continue # we've already caught this threshold passthrough
            n_thresh_at_median += 1
            j_prev = j
        return n_thresh_at_median


    def get_area(self, sign, m, t):
        """ Get area under model, for the postive (above median) and negative parts.

        I break the ( > median) points into segments which I integrate
        over using trapazoid method.  Otherwise, the interpolation
        over ( < median) gaps would skew the results.
        """
        if sign == 'pos':
            past_thresh = numpy.where(m > 0.0)[0]
        elif sign == 'neg':
            past_thresh = numpy.where(m < 0.0)[0]
        total_area = 0.
        t_segment = [t[past_thresh[0]]]
        m_segment = [m[past_thresh[0]]]
        j_prev = past_thresh[0]
        #import pdb; pdb.set_trace()
        #print
        for j in past_thresh[1:]:
            if j-1 == j_prev:
                j_prev = j
                t_segment.append(t[j])
                m_segment.append(m[j])
            else:
                if len(t_segment) >= 2:
                    total_area += scipy.integrate.trapz(m_segment, t_segment)
                # then we integrate the current segment if long enough
                t_segment = [t[j]]
                m_segment = [m[j]]
                j_prev = j
        if len(t_segment) >= 2:
            total_area += scipy.integrate.trapz(m_segment, t_segment)
        return total_area    
            

    def extract(self):
        """ Base, initial internal extractor for the unfolded lightcurve model features.
        """
        try:
            # get info
            t = self.time_data
            m = self.flux_data

            # find the proper window for the model
            best_GCV, optimal_window = self.minimize_GCV(t, m)
            bandwidth = 500*float(optimal_window)/len(t) # 1000 too smooth, 100 is ok but a little too coupled to orig data.
            shivv_model = self.kernelSmooth(t, m, bandwidth)

            m_median = numpy.median(m)
            normalized_model_mags = shivv_model - m_median

            n_thresh_at_median = self.get_n_passing_median(normalized_model_mags)
            pos_dict = self.get_dmag_at_median_threshold('pos', normalized_model_mags)
            neg_dict = self.get_dmag_at_median_threshold('neg', normalized_model_mags)

            pos_area = self.get_area('pos', normalized_model_mags, t)
            neg_area = self.get_area('neg', normalized_model_mags, t)

            #self.debug_compare_gp_and_shivv_models(t, m, self.rms_data, shivv_model,
            #                                       pos_delta_mag=pos_dict['delta_mag_median'] + m_median,
            #                                       neg_delta_mag=neg_dict['delta_mag_median'] + m_median)

            
            delta_t = numpy.max(t) - numpy.min(t)

            self.lc_feats = {'pos_mag_ratio': pos_dict['delta_mag_median']/(pos_dict['delta_mag_median'] + abs(neg_dict['delta_mag_median'])),
                    'pos_n_ratio': pos_dict['n_thresh_median']/float(pos_dict['n_thresh_median'] + neg_dict['n_thresh_median']),
                    'median_n_per_day': n_thresh_at_median / delta_t,
                    'pos_n_per_day': pos_dict['n_thresh_median'] / delta_t,
                    'neg_n_per_day': neg_dict['n_thresh_median'] / delta_t,
                    'pos_area_ratio': pos_area / (pos_area + abs(neg_area)),
                }
        except:
            self.lc_feats = {}
        return self.lc_feats


    def fold(self, times, period):
        ''' return phases for <times> folded at <period> '''
        t0 = times[0]
        phase = ((times-t0)%period)/period
        return phase

    def rolling_window(self, b, window):
        """ Call: numpy.mean(rolling_window(observations, n), 1)
        """
        # perform smoothing using strides trick
        shape = b.shape[:-1] + (b.shape[-1] - window + 1, window)
        strides = b.strides + (b.strides[-1],)
        return numpy.lib.stride_tricks.as_strided(b, shape=shape, strides=strides)

    def GCV(self, window, X,Y):
        # put in proper order
        zpm = list(zip(X,Y))
        zpm.sort()
        zpm_arr = numpy.array(zpm)
        phs = zpm_arr[:,0]
        mags = zpm_arr[:,1]
        # handle edges properly by extending array in both directions
        if window>1:
            b = numpy.concatenate((mags[-window/2:], mags, mags[:window/2-1]))
        else:
            b = mags
        # calculate smoothed model and corresponding smoothing matrix diagonal value
        model = numpy.mean(self.rolling_window(b, window), 1)
        Lii = 1./window
        # return the Generalized Cross-Validation criterion
        GCV = 1./len(phs) * numpy.sum( ((mags-model)/(1.-Lii))**2 )
        return GCV

    def minimize_GCV(self,X,Y, window_range=(10,50,2)):
        ''' quick way to pick best GCV value '''
        windows = numpy.arange(*window_range)
        GCVs = numpy.array( [self.GCV(window, X,Y) for window in windows] )
        best_GCV = numpy.min(GCVs)
        optimal_window = windows[ numpy.argmin(GCVs) ]
        return best_GCV, optimal_window

    def GaussianKernel(self, x):
        return (1./numpy.sqrt(2.*numpy.pi)) * numpy.exp(-x**2 / 2.)

    def kernelSmooth(self, X, Y, bandwidth):
        ''' slow implementation of gaussian kernel smoothing '''
        L = numpy.zeros([len(Y),len(X)])
        diags = []
        for i in range(len(X)):
            diff = abs(X[i] - X)
            # wrap around X=1; i.e. diff cannot be more than .5
            diff[diff>.5] = 1. - diff[diff>.5]
            # renormalize, and operate on l vector
            l = diff/bandwidth
            # calculate the Gaussian for the values within 4sigma and plug it in
            # anything beyond 4sigma is basically zero
            tmp = self.GaussianKernel(l[l<4])
            diags.append(numpy.max(tmp))
            L[i,l<4] = tmp/numpy.sum(tmp)
        # model is the smoothing matrix dotted into the data
        return numpy.dot(L, Y.T)

    def find_peaks(self, x):
        """ find peaks in <x> """
        xmid = x[1:-1] # orig array with ends removed
        xm1 = x[2:] # orig array shifted one up
        xp1 = x[:-2] # orig array shifted one back
        return numpy.where(numpy.logical_and(xmid > xm1, xmid > xp1))[0] + 1



class lcmodel_pos_mag_ratio_extractor(FeatureExtractor):
    """ this is a ratio of positive threshold's delta magnitude divided
by the sum of both the positive and negative threshold's delta
magnitudes
    """
    active = True
    extname = 'lcmodel_pos_mag_ratio' #extractor's name

    def extract(self):
        lc_feats = self.properties['data'][self.band]['inter']['lcmodel'].result
        return lc_feats.get('pos_mag_ratio', 0.0)


class lcmodel_pos_n_ratio_extractor(FeatureExtractor):
    """  this is the number of intersections through the positive
threshold divided by the sum of both the positive and negative
threshold's number of intersections
    """
    active = True
    extname = 'lcmodel_pos_n_ratio' #extractor's name

    def extract(self):
        lc_feats = self.properties['data'][self.band]['inter']['lcmodel'].result
        return lc_feats.get('pos_n_ratio', 0.0)

class lcmodel_median_n_per_day_extractor(FeatureExtractor):
    """ this is the number of intersections through the median,
 divided by the total time span of observations, so that
short surveys or observations of a source can be compared with longer
baselined sources.
    """
    active = True
    extname = 'lcmodel_median_n_per_day' #extractor's name

    def extract(self):
        lc_feats = self.properties['data'][self.band]['inter']['lcmodel'].result
        return lc_feats.get('median_n_per_day', 0.0)

class lcmodel_pos_n_per_day_extractor(FeatureExtractor):
    """ this is the number of intersections through the positive
threshold, divided by the total time span of observations, so that
short surveys or observations of a source can be compared with longer
baselined sources.
    """
    active = True
    extname = 'lcmodel_pos_n_per_day' #extractor's name

    def extract(self):
        lc_feats = self.properties['data'][self.band]['inter']['lcmodel'].result
        return lc_feats.get('pos_n_per_day', 0.0)

class lcmodel_neg_n_per_day_extractor(FeatureExtractor):
    """ this is the number of intersections through the negative
threshold, divided by the total time span of observations, so that
short surveys or observations of a source can be compared with longer
baselined sources.
    """
    active = True
    extname = 'lcmodel_neg_n_per_day' #extractor's name

    def extract(self):
        lc_feats = self.properties['data'][self.band]['inter']['lcmodel'].result
        return lc_feats.get('neg_n_per_day', 0.0)

class lcmodel_pos_area_ratio_extractor(FeatureExtractor):
    """describes the area above the median in relation to the abs() combined area of
both above and below the median.  In other words, it is
(magnitude-days area above median) / ( (magnitude-days area above
median) + abs(magnitude-days area below median)).
    """
    active = True
    extname = 'lcmodel_pos_area_ratio' #extractor's name

    def extract(self):
        lc_feats = self.properties['data'][self.band]['inter']['lcmodel'].result
        return lc_feats.get('pos_area_ratio', 0.0)