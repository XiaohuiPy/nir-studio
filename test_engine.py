import json
import engine
engine.load_demo()
for a in ['PLSR','PCR','SVR','Random Forest','Ridge','KNN','Extra Trees','Gradient Boosting']:
    r=json.loads(engine.fit_model('Reference','Sample ID',a,'SNV','None',20,3,11,.2,3,False))
    assert r['test']['rmse']>=0
r=json.loads(engine.fit_model('Reference','Sample ID','PLSR','MSC','PLS-VIP',20,3,11,.2,3,True))
assert len(r['selection']['wavelengths'])==20
b=engine.export_model()
engine.import_model(b)
print('PASS: eight algorithms, VIP, grid search, model export/import')
