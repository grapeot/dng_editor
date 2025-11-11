# DNG 像素值处理工具

## 功能说明

这些脚本用于处理 DNG 文件，将所有像素值减 1。

## 安装依赖

首先创建虚拟环境并安装依赖：

```bash
# 使用 uv 创建虚拟环境（推荐）
uv venv

# 激活虚拟环境
source .venv/bin/activate

# 安装依赖
uv pip install -r requirements.txt
```

或者使用 pip：

```bash
pip install -r requirements.txt
```

## 使用方法

### 完整工作流程

1. **处理 DNG 文件** → 生成 TIFF
2. **转换 TIFF 回 DNG** → 生成修改后的 DNG 文件
3. **验证结果** → 确认像素值正确修改

### 1. 处理 DNG 文件

运行处理脚本，会自动处理当前文件夹下所有 DNG 文件：

```bash
source .venv/bin/activate
python process_dng.py
```

脚本会：
- 自动创建备份文件（`.dng.backup`）
- 读取 DNG 文件的原始像素数据
- 将所有像素值减 1（最小值不低于 0）
- 将修改后的数据保存为 TIFF 格式（`.tiff`）

### 2. 将 TIFF 转换回 DNG

如果要将修改后的 TIFF 文件转换回 DNG 格式，可以使用 `tiff_to_dng.py` 脚本：

```bash
python tiff_to_dng.py L1002757.tiff L1002757.DNG L1002757_modified.DNG
```

或者不指定输出文件名（会自动生成，输出为 `L1002757.dng`）：

```bash
python tiff_to_dng.py L1002757.tiff L1002757.DNG
```

这个脚本会：
- 复制原始 DNG 文件的结构和元数据
- 用修改后的 TIFF 像素数据替换原始像素数据
- 保留所有 EXIF、颜色矩阵等元数据

### 3. 验证修改结果

#### 方法一：验证单个文件

```bash
python verify_dng.py L1002757.DNG
```

#### 方法二：比较原始文件和修改后的文件

可以比较原始 DNG 和修改后的 DNG：

```bash
python verify_dng.py L1002757.DNG L1002757_modified.DNG
```

或者比较原始 DNG 和中间 TIFF 文件：

```bash
python verify_dng.py L1002757.DNG L1002757.tiff
```

这会显示：
- 像素差值统计（应该全部为 -1）
- 差值为 -1 的像素百分比（应该为 100%）

## 文件说明

- `process_dng.py`: 处理脚本，将所有 DNG 文件的像素值减 1，输出为 TIFF 格式
- `tiff_to_dng.py`: 转换脚本，将修改后的 TIFF 文件转换回 DNG 格式
- `verify_dng.py`: 验证脚本，可以验证单个文件或比较两个文件
- `requirements.txt`: Python 依赖包列表

## 注意事项

1. 脚本会自动创建备份文件，原始 DNG 文件不会被修改
2. 修改后的数据保存为 TIFF 格式，保持原始像素值（16位）
3. 如果原始像素值为 0，减 1 后仍为 0（不会出现负值）
4. 可以使用 `tiff_to_dng.py` 将 TIFF 转换回 DNG 格式

## 验证结果示例

成功的验证结果应该显示：
```
像素差值统计:
  最小值: -1
  最大值: -1
  平均值: -1.00
  中位数: -1.00
  差值为 -1 的像素数: 60420096 / 60420096 (100.00%)
  所有唯一差值: [-1]
```

这表明所有像素值都正确减了 1。
