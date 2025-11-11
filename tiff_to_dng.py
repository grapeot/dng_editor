#!/usr/bin/env python3
"""
将修改后的 TIFF 文件转换回 DNG 格式
使用原始 DNG 文件的元数据，替换像素数据
"""
import shutil
import rawpy
import numpy as np
from pathlib import Path
import struct

def tiff_to_dng(tiff_path, original_dng_path, output_dng_path=None):
    """
    将 TIFF 文件转换回 DNG 格式
    
    这个方法通过复制原始 DNG 文件的结构，然后替换像素数据来实现
    这样可以保留所有元数据（EXIF、颜色矩阵等）
    
    Args:
        tiff_path: TIFF 文件路径
        original_dng_path: 原始 DNG 文件路径（用于获取元数据）
        output_dng_path: 输出 DNG 文件路径，如果为 None 则自动生成
    """
    tiff_path = Path(tiff_path)
    original_dng_path = Path(original_dng_path)
    
    if output_dng_path is None:
        output_dng_path = tiff_path.with_suffix('.dng')
    else:
        output_dng_path = Path(output_dng_path)
    
    print(f"转换文件:")
    print(f"  TIFF: {tiff_path}")
    print(f"  原始 DNG: {original_dng_path}")
    print(f"  输出 DNG: {output_dng_path}\n")
    
    # 读取 TIFF 文件的像素数据
    import tifffile
    tiff_data = tifffile.imread(str(tiff_path))
    print(f"  TIFF 像素值范围: {tiff_data.min()} - {tiff_data.max()}")
    print(f"  TIFF 图像尺寸: {tiff_data.shape}")
    
    # 读取原始 DNG 文件获取元数据
    with rawpy.imread(str(original_dng_path)) as raw:
        original_data = raw.raw_image.copy()
        print(f"  原始 DNG 像素值范围: {original_data.min()} - {original_data.max()}")
        print(f"  原始 DNG 图像尺寸: {original_data.shape}")
        
        if tiff_data.shape != original_data.shape:
            raise ValueError(f"图像尺寸不匹配: TIFF {tiff_data.shape} vs DNG {original_data.shape}")
    
    # 复制原始 DNG 文件作为模板
    print(f"\n复制原始 DNG 文件结构...")
    shutil.copy2(original_dng_path, output_dng_path)
    
    # 现在修改输出文件中的像素数据
    print(f"替换像素数据...")
    modify_dng_pixels(output_dng_path, tiff_data)
    
    print(f"\n✓ 转换完成: {output_dng_path}")

def modify_dng_pixels(dng_path, new_pixel_data):
    """
    在 DNG 文件中替换像素数据
    """
    with open(dng_path, 'r+b') as f:
        # 读取 TIFF 头
        byte_order_bytes = f.read(2)
        if byte_order_bytes == b'II':
            endian = '<'
        elif byte_order_bytes == b'MM':
            endian = '>'
        else:
            raise ValueError("不是有效的 TIFF/DNG 文件")
        
        tiff_id = struct.unpack(endian + 'H', f.read(2))[0]
        if tiff_id != 42:
            raise ValueError("不是有效的 TIFF/DNG 文件")
        
        ifd_offset = struct.unpack(endian + 'I', f.read(4))[0]
        f.seek(ifd_offset)
        num_entries = struct.unpack(endian + 'H', f.read(2))[0]
        
        # 查找 StripOffsets 和 StripByteCounts
        strip_offsets_tag = None
        strip_byte_counts_tag = None
        compression = 1
        
        for i in range(num_entries):
            tag = struct.unpack(endian + 'H', f.read(2))[0]
            data_type = struct.unpack(endian + 'H', f.read(2))[0]
            count = struct.unpack(endian + 'I', f.read(4))[0]
            value_offset = f.read(4)
            
            if tag == 273:  # StripOffsets
                strip_offsets_tag = (data_type, count, value_offset)
            elif tag == 279:  # StripByteCounts
                strip_byte_counts_tag = (data_type, count, value_offset)
            elif tag == 259:  # Compression
                if data_type == 3:
                    compression = struct.unpack(endian + 'H', value_offset[:2])[0]
                else:
                    compression = struct.unpack(endian + 'I', value_offset)[0]
        
        if not strip_offsets_tag or not strip_byte_counts_tag:
            raise ValueError("无法找到像素数据位置")
        
        # 解析 StripOffsets
        data_type, count, value_offset = strip_offsets_tag
        if count == 1:
            if data_type == 3:
                strip_offset = struct.unpack(endian + 'H', value_offset[:2])[0]
            else:
                strip_offset = struct.unpack(endian + 'I', value_offset)[0]
            strip_offsets = [strip_offset]
        else:
            offset_to_data = struct.unpack(endian + 'I', value_offset)[0]
            current_pos = f.tell()
            f.seek(offset_to_data)
            if data_type == 3:
                strip_offsets = list(struct.unpack(endian + 'H' * count, f.read(2 * count)))
            else:
                strip_offsets = list(struct.unpack(endian + 'I' * count, f.read(4 * count)))
            f.seek(current_pos)
        
        # 解析 StripByteCounts
        data_type, count, value_offset = strip_byte_counts_tag
        if count == 1:
            if data_type == 3:
                strip_byte_count = struct.unpack(endian + 'H', value_offset[:2])[0]
            else:
                strip_byte_count = struct.unpack(endian + 'I', value_offset)[0]
            strip_byte_counts = [strip_byte_count]
        else:
            offset_to_data = struct.unpack(endian + 'I', value_offset)[0]
            current_pos = f.tell()
            f.seek(offset_to_data)
            if data_type == 3:
                strip_byte_counts = list(struct.unpack(endian + 'H' * count, f.read(2 * count)))
            else:
                strip_byte_counts = list(struct.unpack(endian + 'I' * count, f.read(4 * count)))
            f.seek(current_pos)
        
        # 准备新的像素数据
        if new_pixel_data.dtype == np.uint16:
            pixel_bytes = new_pixel_data.tobytes()
        else:
            pixel_bytes = new_pixel_data.astype(np.uint16).tobytes()
        
        expected_bytes = new_pixel_data.size * 2  # 16位 = 2字节
        
        # 如果数据是压缩的，我们需要扩展文件
        is_compressed = compression != 1 and strip_byte_counts[0] < expected_bytes
        
        if is_compressed:
            # 读取整个文件
            f.seek(0)
            file_data = bytearray(f.read())
            
            bytes_to_insert = len(pixel_bytes) - strip_byte_counts[0]
            strip_start = strip_offsets[0]
            strip_end = strip_start + strip_byte_counts[0]
            
            # 替换像素数据
            file_data[strip_start:strip_end] = pixel_bytes
            
            # 更新后续偏移量
            for i, offset in enumerate(strip_offsets):
                if offset > strip_start:
                    strip_offsets[i] += bytes_to_insert
            
            f.seek(0)
            f.write(file_data)
            f.truncate()
        else:
            # 直接写入
            f.seek(strip_offsets[0])
            f.write(pixel_bytes)
        
        # 更新 StripByteCounts 和 Compression
        if strip_byte_counts[0] != len(pixel_bytes) or compression != 1:
            f.seek(ifd_offset + 2)
            for i in range(num_entries):
                tag = struct.unpack(endian + 'H', f.read(2))[0]
                data_type = struct.unpack(endian + 'H', f.read(2))[0]
                count = struct.unpack(endian + 'I', f.read(4))[0]
                value_pos = f.tell()
                value_offset = f.read(4)
                
                if tag == 279:  # StripByteCounts
                    if count == 1:
                        f.seek(value_pos)
                        if data_type == 3:
                            f.write(struct.pack(endian + 'H', len(pixel_bytes)))
                        else:
                            f.write(struct.pack(endian + 'I', len(pixel_bytes)))
                elif tag == 259 and compression != 1:  # Compression
                    f.seek(value_pos)
                    if data_type == 3:
                        f.write(struct.pack(endian + 'H', 1))
                    else:
                        f.write(struct.pack(endian + 'I', 1))

def main():
    """主函数"""
    import sys
    
    if len(sys.argv) < 3:
        print("用法: python tiff_to_dng.py <TIFF文件> <原始DNG文件> [输出DNG文件]")
        print("\n示例:")
        print("  python tiff_to_dng.py L1002757.tiff L1002757.DNG L1002757_modified.DNG")
        print("  python tiff_to_dng.py L1002757.tiff L1002757.DNG  # 自动生成输出文件名")
        return
    
    tiff_file = Path(sys.argv[1])
    original_dng = Path(sys.argv[2])
    output_dng = Path(sys.argv[3]) if len(sys.argv) > 3 else None
    
    if not tiff_file.exists():
        print(f"错误: TIFF 文件不存在: {tiff_file}")
        return
    
    if not original_dng.exists():
        print(f"错误: 原始 DNG 文件不存在: {original_dng}")
        return
    
    try:
        tiff_to_dng(tiff_file, original_dng, output_dng)
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()

