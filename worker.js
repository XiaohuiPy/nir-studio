importScripts("https://cdn.jsdelivr.net/pyodide/v0.29.2/full/pyodide.js");
let py;
(async()=>{
 try{
 postMessage({type:"status",text:"正在下载 Python 科学计算依赖…"});
 py=await loadPyodide({indexURL:"https://cdn.jsdelivr.net/pyodide/v0.29.2/full/"});
 await py.loadPackage(["numpy","pandas","scipy","scikit-learn","openpyxl"]);
 let response=await fetch("engine.py");
 if(!response.ok)throw Error("Unable to load engine.py");
 py.FS.writeFile("/home/pyodide/engine.py",await response.text());
 py.runPython("import sys;sys.path.insert(0,'/home/pyodide');import engine");
 postMessage({type:"ready"});
 }catch(e){postMessage({type:"fatal",error:String(e)})}
})();
self.onmessage=async e=>{
 const {id,fn,args}=e.data;
 try{
 if(!py)throw Error("Python runtime not ready");
 const mod=py.pyimport("engine"),method=mod[fn];
 if(!method)throw Error("Unknown engine function");
 const result=method(...args);
 postMessage({id,result:result?.toJs?result.toJs():result});
 }catch(e){postMessage({id,error:String(e)})}
};
