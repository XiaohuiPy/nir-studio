import json, io, base64, pickle
import numpy as np
import pandas as pd
from scipy.signal import savgol_filter
from sklearn.base import BaseEstimator, TransformerMixin, clone
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.cross_decomposition import PLSRegression
from sklearn.decomposition import PCA
from sklearn.linear_model import Ridge, LinearRegression
from sklearn.svm import SVR
from sklearn.ensemble import RandomForestRegressor, ExtraTreesRegressor, GradientBoostingRegressor
from sklearn.neighbors import KNeighborsRegressor
from sklearn.feature_selection import SelectKBest, f_regression
from sklearn.model_selection import train_test_split, KFold, GridSearchCV, cross_val_predict
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score

DATA=None
BUNDLE=None
LAST=None

class Preprocess(BaseEstimator,TransformerMixin):
    def __init__(self,method="SNV",window=11,poly=2):
        self.method=method;self.window=window;self.poly=poly
    def fit(self,X,y=None):
        X=np.asarray(X,float)
        if self.method=="MSC": self.reference_=X.mean(axis=0)
        return self
    def transform(self,X):
        X=np.asarray(X,float)
        if self.method=="None":return X.copy()
        if self.method=="SNV":
            return (X-X.mean(axis=1,keepdims=True))/np.maximum(X.std(axis=1,keepdims=True),1e-12)
        if self.method=="MSC":
            out=[]
            for row in X:
                slope,offset=np.polyfit(self.reference_,row,1)
                if abs(slope)<1e-12:raise ValueError("MSC slope near zero")
                out.append((row-offset)/slope)
            return np.array(out)
        if self.method=="Detrend":
            t=np.linspace(-1,1,X.shape[1])
            return np.array([r-np.polyval(np.polyfit(t,r,1),t) for r in X])
        orders={"SG smooth":0,"SG 1st derivative":1,"SG 2nd derivative":2}
        if self.method in orders:
            if self.window%2!=1 or self.window>X.shape[1] or self.window<=self.poly:
                raise ValueError("SG window must be odd, <= wavelength count and > polynomial order")
            return savgol_filter(X,self.window,self.poly,deriv=orders[self.method],axis=1)
        raise ValueError("Invalid preprocessing method")

class VIP(BaseEstimator,TransformerMixin):
    def __init__(self,k=30,n_components=3):
        self.k=k;self.n_components=n_components
    def fit(self,X,y):
        X=np.asarray(X);y=np.asarray(y).ravel()
        n=min(self.n_components,X.shape[0]-1,X.shape[1])
        pls=PLSRegression(n_components=n).fit(X,y)
        t=pls.x_scores_;w=pls.x_weights_;q=pls.y_loadings_.ravel()
        s=(t*t).sum(axis=0)*q*q
        wn=w/np.maximum(np.linalg.norm(w,axis=0),1e-12)
        self.scores_=np.sqrt(X.shape[1]*((wn*wn)@s)/max(s.sum(),1e-12))
        self.indices_=np.sort(np.argsort(self.scores_)[-min(self.k,X.shape[1]):])
        return self
    def transform(self,X):return np.asarray(X)[:,self.indices_]
    def get_support(self):return self.indices_

def pipeline(algo,pre,selection,k,comp,window):
    models={
      "PLSR":lambda:PLSRegression(n_components=comp),
      "PCR":lambda:Pipeline([("pca",PCA(n_components=comp)),("linear",LinearRegression())]),
      "SVR":lambda:SVR(C=10,epsilon=.1),
      "Random Forest":lambda:RandomForestRegressor(n_estimators=100,random_state=42,n_jobs=1),
      "Ridge":lambda:Ridge(alpha=1),
      "KNN":lambda:KNeighborsRegressor(n_neighbors=5),
      "Extra Trees":lambda:ExtraTreesRegressor(n_estimators=100,random_state=42,n_jobs=1),
      "Gradient Boosting":lambda:GradientBoostingRegressor(random_state=42)}
    steps=[("pre",Preprocess(pre,window))]
    if selection=="SelectKBest":steps.append(("select",SelectKBest(f_regression,k=k)))
    if selection=="PLS-VIP":steps.append(("select",VIP(k,min(comp,5))))
    if algo in ("PCR","SVR","Ridge","KNN"):steps.append(("scale",StandardScaler()))
    steps.append(("model",models[algo]()))
    return Pipeline(steps)

def scores(y,p):
    y=np.asarray(y).ravel();p=np.asarray(p).ravel()
    rmse=float(np.sqrt(mean_squared_error(y,p)))
    return {"r2":float(r2_score(y,p)),"rmse":rmse,"mae":float(mean_absolute_error(y,p)),
            "bias":float(np.mean(p-y)),"rpd":float(np.std(y,ddof=1)/rmse) if rmse>1e-12 else None}

def demo():
    rng=np.random.default_rng(42);n=120;p=160
    w=np.linspace(1000,2500,p);y=rng.uniform(5,25,n)
    peak=np.exp(-.5*((w-1450)/65)**2)+.7*np.exp(-.5*((w-1940)/95)**2)
    X=.32+.035*np.sin(w/180)+.013*y[:,None]*peak[None,:]+rng.normal(0,.012,(n,p))+rng.normal(0,.018,(n,1))
    d=pd.DataFrame(X,columns=[f"{v:.2f}" for v in w])
    d.insert(0,"Sample ID",[f"S{i+1:03d}" for i in range(n)]);d["Reference"]=y
    return d

def load_csv(text):
    global DATA,BUNDLE,LAST
    DATA=pd.read_csv(io.StringIO(text),sep=None,engine="python")
    BUNDLE=None;LAST=None
    return describe()

def load_excel(encoded):
    global DATA,BUNDLE,LAST
    DATA=pd.read_excel(io.BytesIO(base64.b64decode(encoded)))
    BUNDLE=None;LAST=None
    return describe()

def load_demo():
    global DATA,BUNDLE,LAST
    DATA=demo();BUNDLE=None;LAST=None
    return describe()

def describe():
    d=DATA
    return json.dumps({"rows":len(d),"columns":list(map(str,d.columns)),
        "preview":d.head(6).fillna("").astype(str).to_dict("records")},allow_nan=False)

def extract(target,ident,low=None,high=None):
    if DATA is None:raise ValueError("Load data first")
    if target not in DATA.columns:raise ValueError("Reference column missing")
    excluded={target}
    if ident and ident!="(none)":excluded.add(ident)
    pairs=[]
    for c in DATA.columns:
        if c in excluded:continue
        try:pairs.append((float(str(c).strip().replace("nm","")),c))
        except ValueError:pass
    pairs.sort()
    if low is not None:pairs=[p for p in pairs if low<=p[0]<=high]
    if len(pairs)<5:raise ValueError("Need at least 5 wavelength columns")
    cols=[c for _,c in pairs];w=np.array([a for a,_ in pairs])
    X=DATA[cols].apply(pd.to_numeric,errors="raise").to_numpy(float)
    y=pd.to_numeric(DATA[target],errors="raise").to_numpy(float)
    if len(y)<20:raise ValueError("At least 20 reference samples required")
    if not np.isfinite(X).all() or not np.isfinite(y).all():raise ValueError("Missing or non-finite values")
    if np.std(y)<1e-12:raise ValueError("Reference values must vary")
    return X,y,w,cols

def spectrum(target,ident,pre="None",window=11,low=None,high=None):
    X,y,w,cols=extract(target,ident,low,high)
    z=Preprocess(pre,window).fit_transform(X)
    ids=np.linspace(0,len(z)-1,min(35,len(z)),dtype=int)
    return json.dumps({"w":w.tolist(),"curves":[z[i].tolist() for i in ids],"count":len(X),
                       "features":len(w),"range":[float(w.min()),float(w.max())]},allow_nan=False)

def grids(algo,n,p,folds,selection,k):
    cap=max(1,min(10,n-int(np.ceil(n/folds))-1,p if selection=="None" else k))
    if algo=="PLSR":return {"model__n_components":[x for x in (1,2,3,5,8,10) if x<=cap]}
    if algo=="PCR":return {"model__pca__n_components":[x for x in (1,2,3,5,8,10) if x<=cap]}
    if algo=="SVR":return {"model__C":[1,10,100],"model__epsilon":[.01,.1],"model__gamma":["scale",.01]}
    if algo=="Ridge":return {"model__alpha":[.01,.1,1,10,100]}
    if algo=="KNN":return {"model__n_neighbors":[x for x in (3,5,7,11) if x<=n-int(np.ceil(n/folds))]}
    if algo in ("Random Forest","Extra Trees"):return {"model__min_samples_leaf":[1,3],"model__max_features":[.5,1.]}
    return {"model__n_estimators":[100,200],"model__learning_rate":[.05,.1]}

def fit_model(target,ident,algo,pre,selection,k,comp,window,test_ratio,folds,optimize,low=None,high=None):
    global BUNDLE,LAST
    X,y,w,cols=extract(target,ident,low,high)
    if not (0.1<=test_ratio<=0.4):raise ValueError("Test ratio outside range")
    Xtr,Xte,ytr,yte=train_test_split(X,y,test_size=test_ratio,random_state=42)
    mintrain=len(Xtr)-int(np.ceil(len(Xtr)/folds))
    if mintrain<6:raise ValueError("Too few samples for cross-validation")
    if comp>min(mintrain-1,X.shape[1] if selection=="None" else k) and algo in ("PLSR","PCR"):
        raise ValueError("Too many latent variables for CV")
    if selection=="PLS-VIP" and min(comp,5)>mintrain-1:raise ValueError("Too many VIP components")
    if algo=="KNN" and mintrain<5:raise ValueError("Not enough training samples for KNN")
    model=pipeline(algo,pre,selection,k,comp,window)
    cv=KFold(n_splits=folds,shuffle=True,random_state=42)
    best={}
    if optimize:
        gs=GridSearchCV(model,grids(algo,len(Xtr),X.shape[1],folds,selection,k),cv=cv,
                        scoring="neg_root_mean_squared_error",n_jobs=1,error_score="raise")
        gs.fit(Xtr,ytr);model=gs.best_estimator_;best=gs.best_params_
    else:model.fit(Xtr,ytr)
    pcv=np.asarray(cross_val_predict(clone(model),Xtr,ytr,cv=cv,n_jobs=1)).ravel()
    ptr=np.asarray(model.predict(Xtr)).ravel()
    pte=np.asarray(model.predict(Xte)).ravel()
    selection_info=None
    if "select" in model.named_steps:
        s=model.named_steps["select"]
        support=s.get_support()
        idx=np.where(support)[0] if np.asarray(support).dtype==bool else np.asarray(support)
        selection_info={"wavelengths":w[idx].tolist(),"scores":s.scores_.tolist() if hasattr(s,"scores_") else None}
    LAST={"train":scores(ytr,ptr),"cv":scores(ytr,pcv),"test":scores(yte,pte),
          "points":{"train":{"actual":ytr.tolist(),"pred":ptr.tolist()},
                    "cv":{"actual":ytr.tolist(),"pred":pcv.tolist()},
                    "test":{"actual":yte.tolist(),"pred":pte.tolist()}},
          "best":best,"selection":selection_info,"algorithm":algo}
    BUNDLE={"model":model,"columns":cols,"wavelengths":w.tolist(),"target":target,
            "algorithm":algo,"preprocess":pre,"selection":selection,"metrics":LAST["test"]}
    return json.dumps(LAST,allow_nan=False)

def predict_csv(text):
    if BUNDLE is None:raise ValueError("Train or import a model first")
    d=pd.read_csv(io.StringIO(text),sep=None,engine="python")
    return predict_df(d)

def predict_excel(encoded):
    if BUNDLE is None:raise ValueError("Train or import a model first")
    return predict_df(pd.read_excel(io.BytesIO(base64.b64decode(encoded))))

def predict_df(d):
    missing=[c for c in BUNDLE["columns"] if c not in d.columns]
    if missing:raise ValueError("Missing wavelength columns: "+str(missing[:8]))
    X=d[BUNDLE["columns"]].apply(pd.to_numeric,errors="raise").to_numpy(float)
    if not np.isfinite(X).all():raise ValueError("Non-finite spectral values")
    p=np.asarray(BUNDLE["model"].predict(X)).ravel()
    ids=d["Sample ID"].astype(str).tolist() if "Sample ID" in d else [f"U{i+1:03d}" for i in range(len(d))]
    return json.dumps({"rows":[{"Sample ID":i,"Prediction":float(v)} for i,v in zip(ids,p)]},allow_nan=False)

def export_model():
    if BUNDLE is None:raise ValueError("No model trained")
    return base64.b64encode(pickle.dumps(BUNDLE,protocol=4)).decode("ascii")

def import_model(encoded):
    global BUNDLE,LAST
    # Pickle is executable: NEVER import untrusted model files.
    b=pickle.loads(base64.b64decode(encoded))
    if not isinstance(b,dict) or not all(x in b for x in ("model","columns","target","algorithm")):
        raise ValueError("Invalid model")
    BUNDLE=b;LAST=None
    return json.dumps({"algorithm":b["algorithm"],"target":b["target"],"features":len(b["columns"])})

def demo_csv():
    return demo().to_csv(index=False)
