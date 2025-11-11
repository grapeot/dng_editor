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
    优先查找 SubIFD（标签 330），因为 rawpy 通常读取 SubIFD 中的数据
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
        
        first_ifd_offset = struct.unpack(endian + 'I', f.read(4))[0]
        
        # 查找 SubIFD（标签 330）
        f.seek(first_ifd_offset)
        num_entries = struct.unpack(endian + 'H', f.read(2))[0]
        
        subifd_offset = None
        for i in range(num_entries):
            tag = struct.unpack(endian + 'H', f.read(2))[0]
            data_type = struct.unpack(endian + 'H', f.read(2))[0]
            count = struct.unpack(endian + 'I', f.read(4))[0]
            value_offset = f.read(4)
            
            if tag == 330:  # SubIFDs
                if count > 0:
                    subifd_offset = struct.unpack(endian + 'I', value_offset)[0]
                    break
        
        # 使用 SubIFD 如果存在，否则使用主 IFD
        target_ifd_offset = subifd_offset if subifd_offset else first_ifd_offset
        
        f.seek(target_ifd_offset)
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
        
        # 准备新的像素数据（未压缩）
        if new_pixel_data.dtype == np.uint16:
            pixel_bytes = new_pixel_data.tobytes()
        else:
            pixel_bytes = new_pixel_data.astype(np.uint16).tobytes()
        
        expected_bytes = new_pixel_data.size * 2  # 16位 = 2字节
        
        # 记录标签位置以便后续更新
        compression_tag_pos = None
        strip_offsets_tag_pos = None
        strip_byte_counts_tag_pos = None
        compression_tag_data_type = None
        strip_offsets_tag_data_type = None
        strip_byte_counts_tag_data_type = None
        
        # 重新读取 IFD 以记录标签位置
        f.seek(target_ifd_offset + 2)
        for i in range(num_entries):
            tag = struct.unpack(endian + 'H', f.read(2))[0]
            data_type = struct.unpack(endian + 'H', f.read(2))[0]
            count = struct.unpack(endian + 'I', f.read(4))[0]
            value_pos = f.tell()
            value_offset = f.read(4)
            
            if tag == 259:  # Compression
                compression_tag_pos = value_pos
                compression_tag_data_type = data_type
            elif tag == 273:  # StripOffsets
                strip_offsets_tag_pos = value_pos
                strip_offsets_tag_data_type = data_type
            elif tag == 279:  # StripByteCounts
                strip_byte_counts_tag_pos = value_pos
                strip_byte_counts_tag_data_type = data_type
        
        # 准备新的像素数据（未压缩）
        if new_pixel_data.dtype == np.uint16:
            pixel_bytes = new_pixel_data.tobytes()
        else:
            pixel_bytes = new_pixel_data.astype(np.uint16).tobytes()
        
        # 总是将未压缩数据写入文件末尾，避免覆盖现有数据
        f.seek(0, 2)  # 移动到文件末尾
        new_strip_offset = f.tell()
        f.write(pixel_bytes)
        
        # 更新 StripOffsets
        if strip_offsets_tag_pos:
            f.seek(strip_offsets_tag_pos)
            if strip_offsets_tag_data_type == 3:  # SHORT
                f.write(struct.pack(endian + 'H', new_strip_offset & 0xFFFF))
                # 如果偏移量超过 16 位，需要更新为 LONG 类型
                if new_strip_offset > 0xFFFF:
                    # 这需要更复杂的处理，暂时跳过
                    pass
            else:  # LONG
                f.write(struct.pack(endian + 'I', new_strip_offset))
        
        # 更新 StripByteCounts
        if strip_byte_counts_tag_pos:
            f.seek(strip_byte_counts_tag_pos)
            if strip_byte_counts_tag_data_type == 3:  # SHORT
                f.write(struct.pack(endian + 'H', len(pixel_bytes) & 0xFFFF))
            else:  # LONG
                f.write(struct.pack(endian + 'I', len(pixel_bytes)))
        
        # 更新 Compression 为 1 (未压缩)
        if compression_tag_pos and compression != 1:
            f.seek(compression_tag_pos)
            if compression_tag_data_type == 3:  # SHORT
                f.write(struct.pack(endian + 'H', 1))
            else:  # LONG
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

