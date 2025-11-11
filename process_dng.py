#!/usr/bin/env python3
"""
处理当前文件夹下所有 DNG 文件，将所有像素值减1
使用 rawpy 读取，修改后保存为线性 TIFF 格式（保持原始像素值）
"""
import os
import shutil
import rawpy
import numpy as np
from pathlib import Path
import tifffile

def process_dng_file(input_path, backup=True):
    """
    读取 DNG 文件，将所有像素值减1，然后保存为 TIFF
    
    Args:
        input_path: 输入 DNG 文件路径
        backup: 是否创建备份文件
    """
    input_path = Path(input_path)
    
    # 创建备份
    if backup:
        backup_path = input_path.with_suffix('.dng.backup')
        if not backup_path.exists():
            print(f"创建备份: {backup_path}")
            shutil.copy2(input_path, backup_path)
    
    print(f"处理文件: {input_path}")
    
    # 读取 DNG 文件
    with rawpy.imread(str(input_path)) as raw:
        # 获取原始像素数据
        raw_array = raw.raw_image.copy()
        
        print(f"  原始像素值范围: {raw_array.min()} - {raw_array.max()}")
        print(f"  图像尺寸: {raw_array.shape}")
        print(f"  数据类型: {raw_array.dtype}")
        
        # 将所有像素值减1，确保不低于0
        processed_array = np.maximum(raw_array.astype(np.int32) - 1, 0).astype(raw_array.dtype)
        
        print(f"  处理后像素值范围: {processed_array.min()} - {processed_array.max()}")
        
        # 保存为 TIFF 格式（线性，16位，保持原始 Bayer 模式）
        output_tiff = input_path.with_suffix('.tiff')
        tifffile.imwrite(
            str(output_tiff),
            processed_array,
            photometric='minisblack',  # 灰度图像
            bitspersample=16
        )
        print(f"  ✓ 已保存修改后的数据到: {output_tiff}")
    
    print()

def main():
    """处理当前文件夹下所有 DNG 文件"""
    current_dir = Path(__file__).parent
    
    # 查找所有 DNG 文件
    dng_files = list(current_dir.glob("*.DNG")) + list(current_dir.glob("*.dng"))
    
    if not dng_files:
        print("未找到 DNG 文件")
        return
    
    print(f"找到 {len(dng_files)} 个 DNG 文件\n")
    
    # 处理每个文件
    for dng_file in dng_files:
        try:
            process_dng_file(dng_file)
        except Exception as e:
            print(f"处理 {dng_file} 时出错: {e}\n")
    
    print("处理完成！")
    print("\n提示: 修改后的文件保存为 .tiff 格式")
    print("可以使用以下命令验证:")
    print("  python verify_dng.py <原始DNG文件> <修改后的TIFF文件>")

if __name__ == "__main__":
    main()
