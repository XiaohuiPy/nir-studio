# NIR Studio Web — 纯前端近红外定量分析

## 部署（用户无需安装任何软件）
将 `index.html`、`app.js`、`worker.js`、`engine.py` 四个文件上传到 GitHub Pages、Cloudflare Pages 或 Netlify 的静态站点根目录。
使用发布后的 HTTPS 网址访问。无需构建命令、Python 后端或 Node.js。
注意：直接通过 `file://` 双击打开 HTML 可能因为 Worker / fetch 限制而无法运行。

首次访问需要联网下载 Pyodide v0.29.2、NumPy、pandas、SciPy、scikit-learn、openpyxl 和 Plotly。光谱计算在浏览器 Web Worker 中进行，不发送至应用服务器。

## 使用方法
1. 打开页面，等待“计算引擎就绪”，自动加载 120 个模拟样品。
2. “数据与光谱”上传 CSV/XLSX。每行一个样品，波长列标题是数值（单位 nm），参考值列如 Reference，可选 Sample ID。
3. “预处理与建模”选择参考值列、算法、预处理、特征筛选，训练。
4. “模型评价”查看 R²、RMSE、MAE、Bias、RPD、预测散点图、残差图。
5. “未知样品预测”上传波长列标题完全一致的 CSV/XLSX。
6. “模型管理”保存或加载 `.nir` 模型（pickle 格式，只能加载可信文件）。

## 科研边界
- 8 种回归算法：PLSR、PCR、SVR、Random Forest、Ridge、KNN、Extra Trees、Gradient Boosting。
- SNV、MSC、SG 平滑与导数、Detrend；波段范围、SelectKBest、PLS-VIP；网格搜索、交叉验证、独立测试。
- 默认随机划分 seed=42；重复扫描或批次样品应使用分组验证，当前版本尚未实现。
- 网格搜索后的交叉验证并非嵌套交叉验证；独立测试集不应反复用于调参。
- SG 导数未按实际 nm 间距缩放，适用于近似等间距光谱的相对特征建模。
- RPD 使用当前评价子集参考值样本标准差 / RMSE。
- 模拟数据不可作为真实检测精度依据。
- 浏览器内存与 CPU 限制大型模型训练；首次加载依赖 CDN，需要网络。
- **安全**：pickle 模型文件可能执行任意代码，绝不导入来源不明的文件。

## 文件
- `index.html`：完整界面
- `app.js`：交互与 Plotly 图表
- `worker.js`：Pyodide Worker 加载
- `engine.py`：Python 回归建模与预处理
- `demo_spectra.csv`：合成光谱示例
- `test_engine.py`：Python 核心算法验证脚本

## GitHub Pages
新建仓库 → 上传上述文件 → Settings → Pages → Deploy from branch → main / root → 使用生成的 HTTPS 地址。
Netlify / Cloudflare Pages 可直接上传文件夹并选择静态部署，无需构建。
