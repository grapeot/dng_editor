#!/usr/bin/env python3
"""
验证 DNG 文件的像素值
"""
import rawpy
import numpy as np
from pathlib import Path

def verify_dng_file(file_path):
    """
    验证 DNG 文件的像素值统计信息
    
    Args:
        file_path: DNG 文件路径
    """
    print(f"验证文件: {file_path}")
    
    try:
        file_path = Path(file_path)
        
        # 如果是 TIFF 文件，直接读取
        if file_path.suffix.lower() in ['.tiff', '.tif']:
            import tifffile
            raw_array = tifffile.imread(str(file_path))
        else:
            # DNG 文件使用 rawpy
            with rawpy.imread(str(file_path)) as raw:
                raw_array = raw.raw_image.copy()
        
        print(f"  图像尺寸: {raw_array.shape}")
        print(f"  像素值范围: {raw_array.min()} - {raw_array.max()}")
        print(f"  平均像素值: {raw_array.mean():.2f}")
        print(f"  中位数像素值: {np.median(raw_array):.2f}")
        print(f"  标准差: {raw_array.std():.2f}")
        
        # 显示一些样本像素值（左上角 5x5 区域）
        sample_region = raw_array[:5, :5]
        print(f"  左上角 5x5 区域像素值:")
        print(f"  {sample_region}")
        print()
            
    except Exception as e:
        print(f"  读取文件时出错: {e}\n")
        import traceback
        traceback.print_exc()

def compare_files(file1_path, file2_path):
    """
    比较两个 DNG 文件的像素值差异
    
    Args:
        file1_path: 第一个 DNG 文件路径
        file2_path: 第二个 DNG 文件路径
    """
    print(f"比较文件:")
    print(f"  文件1: {file1_path}")
    print(f"  文件2: {file2_path}\n")
    
    try:
        file1_path = Path(file1_path)
        file2_path = Path(file2_path)
        
        # 读取第一个文件
        if file1_path.suffix.lower() in ['.tiff', '.tif']:
            import tifffile
            array1 = tifffile.imread(str(file1_path))
        else:
            with rawpy.imread(str(file1_path)) as raw1:
                array1 = raw1.raw_image.copy()
        
        # 读取第二个文件
        if file2_path.suffix.lower() in ['.tiff', '.tif']:
            import tifffile
            array2 = tifffile.imread(str(file2_path))
        else:
            with rawpy.imread(str(file2_path)) as raw2:
                array2 = raw2.raw_image.copy()
        
        if array1.shape != array2.shape:
            print(f"  错误: 两个文件的尺寸不同")
            print(f"  文件1: {array1.shape}, 文件2: {array2.shape}")
            return
        
        # 计算差值
        diff = array2.astype(np.int32) - array1.astype(np.int32)
        
        print(f"  像素差值统计:")
        print(f"    最小值: {diff.min()}")
        print(f"    最大值: {diff.max()}")
        print(f"    平均值: {diff.mean():.2f}")
        print(f"    中位数: {np.median(diff):.2f}")
        
        # 统计差值为 -1 的像素数量
        minus_one_count = np.sum(diff == -1)
        total_pixels = diff.size
        percentage = (minus_one_count / total_pixels) * 100
        
        print(f"    差值为 -1 的像素数: {minus_one_count} / {total_pixels} ({percentage:.2f}%)")
        
        # 检查是否有其他差值
        unique_diffs = np.unique(diff)
        if len(unique_diffs) <= 10:
            print(f"    所有唯一差值: {unique_diffs}")
        else:
            print(f"    前10个唯一差值: {unique_diffs[:10]}")
        
        print()
            
    except Exception as e:
        print(f"  比较文件时出错: {e}\n")

def main():
    """验证当前文件夹下的 DNG 文件"""
    import sys
    
    current_dir = Path(__file__).parent
    
    # 如果提供了两个文件路径，则进行比较
    if len(sys.argv) == 3:
        file1 = Path(sys.argv[1])
        file2 = Path(sys.argv[2])
        if file1.exists() and file2.exists():
            compare_files(file1, file2)
        else:
            print("错误: 指定的文件不存在")
        return
    
    # 否则验证所有 DNG 文件
    dng_files = list(current_dir.glob("*.DNG")) + list(current_dir.glob("*.dng"))
    
    if not dng_files:
        print("未找到 DNG 文件")
        return
    
    print(f"找到 {len(dng_files)} 个 DNG 文件\n")
    
    for dng_file in dng_files:
        verify_dng_file(dng_file)
    
    print("\n提示: 要比较两个文件，使用:")
    print("  python verify_dng.py <文件1> <文件2>")

if __name__ == "__main__":
    main()

