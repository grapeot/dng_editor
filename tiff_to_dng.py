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
    modify_dng_pixels(output_dng_path, tiff_data, original_dng_path)
    
    print(f"\n✓ 转换完成: {output_dng_path}")

def pack_14bit_data(data, endian='<'):
    """
    将 14 位像素数据打包成 DNG 格式
    格式：每 7 字节存储 4 个 14 位像素
    
    解包格式（反向推导）：
    p0 = (b0 << 6) | ((b1 >> 2) & 0x3F)
    p1 = ((b1 & 0x03) << 12) | (b2 << 4) | ((b3 >> 4) & 0x0F)
    p2 = ((b3 & 0x0F) << 10) | (b4 << 2) | ((b5 >> 6) & 0x03)
    p3 = ((b5 & 0x3F) << 8) | b6
    """
    data_flat = data.flatten()
    num_pixels = len(data_flat)
    num_groups = (num_pixels + 3) // 4  # 每组 4 个像素
    packed = bytearray()
    
    for i in range(num_groups):
        start_idx = i * 4
        end_idx = min(start_idx + 4, num_pixels)
        pixels = data_flat[start_idx:end_idx]
        
        # 如果不足 4 个像素，用 0 填充
        if len(pixels) < 4:
            pixels = np.append(pixels, [0] * (4 - len(pixels)))
        
        p0, p1, p2, p3 = pixels.astype(np.uint16)
        
        # 根据解包格式反向推导打包格式
        byte0 = (p0 >> 6) & 0xFF
        byte1 = ((p0 & 0x3F) << 2) | ((p1 >> 12) & 0x03)
        byte2 = (p1 >> 4) & 0xFF
        byte3 = ((p1 & 0x0F) << 4) | ((p2 >> 10) & 0x0F)
        byte4 = (p2 >> 2) & 0xFF
        byte5 = ((p2 & 0x03) << 6) | ((p3 >> 8) & 0x3F)
        byte6 = p3 & 0xFF
        
        packed.extend([byte0, byte1, byte2, byte3, byte4, byte5, byte6])
    
    return bytes(packed)

def modify_dng_pixels(dng_path, new_pixel_data, original_dng_path=None):
    """
    在 DNG 文件中替换像素数据
    优先查找 SubIFD（标签 330），因为 rawpy 通常读取 SubIFD 中的数据
    
    Args:
        dng_path: 要修改的 DNG 文件路径（输出文件）
        new_pixel_data: 新的像素数据
        original_dng_path: 原始 DNG 文件路径（未使用，保留以兼容接口）
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
        
        # 智能选择目标 IFD：优先 SubIFD，如果无效则检查主 IFD 是否是 RAW 数据
        target_ifd_offset = None
        target_ifd_type = None
        
        # 1. 检查 SubIFD 是否有效
        if subifd_offset:
            f.seek(subifd_offset)
            try:
                subifd_num_entries = struct.unpack(endian + 'H', f.read(2))[0]
                if subifd_num_entries > 0 and subifd_num_entries < 1000:
                    # 检查是否有 StripOffsets 和 StripByteCounts
                    has_strip_offsets = False
                    has_strip_byte_counts = False
                    for j in range(min(subifd_num_entries, 100)):
                        stag = struct.unpack(endian + 'H', f.read(2))[0]
                        sdt = struct.unpack(endian + 'H', f.read(2))[0]
                        scount = struct.unpack(endian + 'I', f.read(4))[0]
                        sval = f.read(4)
                        if stag == 273:  # StripOffsets
                            has_strip_offsets = True
                        elif stag == 279:  # StripByteCounts
                            has_strip_byte_counts = True
                    
                    if has_strip_offsets and has_strip_byte_counts:
                        target_ifd_offset = subifd_offset
                        target_ifd_type = "SubIFD"
                        print(f"  使用 SubIFD (偏移: {subifd_offset}, 条目数: {subifd_num_entries})")
            except:
                pass
        
        # 2. 如果 SubIFD 无效，检查主 IFD 是否是 RAW 数据
        if target_ifd_offset is None:
            f.seek(first_ifd_offset)
            num_entries = struct.unpack(endian + 'H', f.read(2))[0]
            
            main_strip_bytes = None
            main_bits = None
            main_samples = None
            main_compression = None
            
            for i in range(num_entries):
                tag = struct.unpack(endian + 'H', f.read(2))[0]
                dt = struct.unpack(endian + 'H', f.read(2))[0]
                count = struct.unpack(endian + 'I', f.read(4))[0]
                val = f.read(4)
                
                if tag == 279:  # StripByteCounts
                    if count == 1:
                        main_strip_bytes = struct.unpack(endian + 'I', val)[0]
                elif tag == 258:  # BitsPerSample
                    if count == 1:
                        main_bits = struct.unpack(endian + ('H' if dt == 3 else 'I'), val[:2 if dt == 3 else 4])[0]
                    else:
                        offset_to_data = struct.unpack(endian + 'I', val)[0]
                        current_pos = f.tell()
                        f.seek(offset_to_data)
                        if dt == 3:
                            bits_array = list(struct.unpack(endian + 'H' * count, f.read(2 * count)))
                            main_bits = bits_array[0] if bits_array else None
                        f.seek(current_pos)
                elif tag == 277:  # SamplesPerPixel
                    main_samples = struct.unpack(endian + ('H' if dt == 3 else 'I'), val[:2 if dt == 3 else 4])[0]
                elif tag == 259:  # Compression
                    main_compression = struct.unpack(endian + ('H' if dt == 3 else 'I'), val[:2 if dt == 3 else 4])[0]
            
            # 判断主 IFD 是否是 RAW 数据
            # RAW 数据特征：单通道（SamplesPerPixel=1），BitsPerSample 在合理范围（12-16）
            # 数据大小接近预期的 RAW 数据大小
            is_raw_data = False
            if main_samples == 1 and main_bits and 12 <= main_bits <= 16:
                # 计算预期的 RAW 数据大小
                expected_bytes_16 = new_pixel_data.size * 2
                expected_bytes_14 = new_pixel_data.size * 14 // 8
                if main_bits == 16:
                    expected_bytes = expected_bytes_16
                else:
                    expected_bytes = expected_bytes_14
                
                # 允许一定的误差（压缩、对齐等）
                if main_strip_bytes and main_strip_bytes >= expected_bytes * 0.8:
                    is_raw_data = True
            
            if is_raw_data:
                target_ifd_offset = first_ifd_offset
                target_ifd_type = "主 IFD (RAW)"
                print(f"  使用主 IFD (RAW 数据, BitsPerSample={main_bits}, SamplesPerPixel={main_samples})")
            else:
                # 主 IFD 不是 RAW 数据，可能是预览图
                # 尝试查找下一个 IFD
                f.seek(first_ifd_offset)
                num_entries = struct.unpack(endian + 'H', f.read(2))[0]
                # 跳过所有条目，找到 next IFD 指针
                f.seek(first_ifd_offset + 2 + num_entries * 12)
                next_ifd = struct.unpack(endian + 'I', f.read(4))[0]
                
                if next_ifd != 0:
                    print(f"  尝试查找下一个 IFD (偏移: {next_ifd})")
                    # 这里可以继续查找，但为了简化，先使用主 IFD
                    target_ifd_offset = first_ifd_offset
                    target_ifd_type = "主 IFD"
                    print(f"  使用主 IFD (偏移: {first_ifd_offset})")
                    if main_samples == 3:
                        print(f"    警告: 主 IFD 是预览图 (SamplesPerPixel=3)，转换可能不会影响 rawpy 读取的数据")
                        print(f"    提示: 此文件可能需要特殊处理，RAW 数据可能以压缩格式存储")
                else:
                    # 主 IFD 是预览图，RAW 数据可能被压缩存储
                    target_ifd_offset = first_ifd_offset
                    target_ifd_type = "主 IFD"
                    print(f"  使用主 IFD (偏移: {first_ifd_offset})")
                    if main_samples == 3:
                        print(f"    警告: 主 IFD 是预览图 (SamplesPerPixel=3)，转换可能不会影响 rawpy 读取的数据")
                        print(f"    提示: 此文件可能需要特殊处理，RAW 数据可能以压缩格式存储")
        
        if target_ifd_offset is None:
            raise ValueError("无法找到有效的 RAW 数据 IFD")
        
        f.seek(target_ifd_offset)
        num_entries = struct.unpack(endian + 'H', f.read(2))[0]
        
        # 查找 StripOffsets、StripByteCounts、BitsPerSample 和 Compression
        strip_offsets_tag = None
        strip_byte_counts_tag = None
        bits_per_sample_tag = None
        compression = 1
        bits_per_sample = 16  # 默认值
        
        for i in range(num_entries):
            tag = struct.unpack(endian + 'H', f.read(2))[0]
            data_type = struct.unpack(endian + 'H', f.read(2))[0]
            count = struct.unpack(endian + 'I', f.read(4))[0]
            value_offset = f.read(4)
            
            if tag == 273:  # StripOffsets
                strip_offsets_tag = (data_type, count, value_offset)
            elif tag == 279:  # StripByteCounts
                strip_byte_counts_tag = (data_type, count, value_offset)
            elif tag == 258:  # BitsPerSample
                bits_per_sample_tag = (data_type, count, value_offset)
                # 读取 BitsPerSample 值
                if count == 1:
                    if data_type == 3:  # SHORT
                        bits_per_sample = struct.unpack(endian + 'H', value_offset[:2])[0]
                    else:
                        bits_per_sample = struct.unpack(endian + 'I', value_offset)[0]
                else:
                    # 多个值，读取第一个
                    offset_to_data = struct.unpack(endian + 'I', value_offset)[0]
                    current_pos = f.tell()
                    f.seek(offset_to_data)
                    if data_type == 3:
                        bits_per_sample = struct.unpack(endian + 'H', f.read(2))[0]
                    else:
                        bits_per_sample = struct.unpack(endian + 'I', f.read(4))[0]
                    f.seek(current_pos)
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
        
        # 准备新的像素数据，根据原始 BitsPerSample 转换格式
        if bits_per_sample == 16:
            # 16 位：直接使用
            if new_pixel_data.dtype == np.uint16:
                pixel_bytes = new_pixel_data.tobytes()
            else:
                pixel_bytes = new_pixel_data.astype(np.uint16).tobytes()
        elif bits_per_sample == 14:
            # 14 位：需要打包成特殊格式
            # 14 位数据格式：每 7 字节存储 4 个像素
            # 像素值需要限制在 14 位范围内 (0-16383)
            data_14bit = np.clip(new_pixel_data, 0, 16383).astype(np.uint16)
            pixel_bytes = pack_14bit_data(data_14bit, endian)
        else:
            # 其他位数：暂时不支持，使用 16 位
            print(f"警告: BitsPerSample={bits_per_sample}，暂不支持，使用 16 位格式")
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

