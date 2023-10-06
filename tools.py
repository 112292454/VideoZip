import argparse
import json
import os
import pprint
import shutil
import subprocess
import sys
from mutagen.mp4 import MP4, MP4Cover, MP4FreeForm

from loguru import logger

COMPRESSED_FLAG = "COMP" # 标识是否已经压缩过的tag key
# !!注意，tag只支持4字母识别  我看mutagen官网说有自由tag，但是没成功
# https://mutagen.readthedocs.io/en/latest/api/mp4.html#module-mutagen.mp4

ffprobe="ffprobe"


def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('-d', '--dir', type=str, required=True,
                        help='to processed video dir')
    parser.add_argument('-t', '--types', type=str, default='mp4,avi,webm,mov,mpg,m4a,m4v,mpeg,wmv',
                        help='to processed video type')
    parser.add_argument('-thread', '--thread_num', type=int, default='2',
                        help='thread num, default is 2')
    parser.add_argument('-crf', '--crf', type=int, default='28',
                        help='crf level; no loss in {h264-19,h265-22,av1-22}, default in {h264-23,h265-28,av1-30}')
    parser.add_argument('-O', '--overwrite', action='store_true',
                        help='overwrite compressed file on source file, default is not, and named it as "compressed_xx"')
    parser.add_argument('-F', '--force', action='store_true',
                        help='process video , no matter it has processed')
    parser.add_argument('-C', '--clear', action='store_true',
                        help='clear middle files. if with -O, will replace source file with compressed_file. (not '
                             'implement)')
    args = parser.parse_args()
    return args

# 获取文件夹内所有非目录文件
def walk_files(root_dir):
    file_list = []
    if not os.path.isdir(root_dir):
        file_list.append(root_dir)
    else:
        for root, dirs, files in os.walk(root_dir):
            for file in files:
                file_path = os.path.join(root, file)
                if os.path.isfile(file_path):
                    file_list.append(file_path)

    return file_list


# 返回列表中，文件类型在types中的部分
def filter_files_by_types(file_list, file_types):
    filtered_files = []

    for file_path in file_list:
        file_extension = os.path.splitext(file_path)[1].lower().replace(".", "")
        if file_extension in file_types:
            filtered_files.append(file_path)

    return filtered_files


def get_os_program_name(name):
    if sys.platform.startswith('win'):
        try:
            output = subprocess.check_output(["whereis", name], universal_newlines=True)
            exe_location = output[output.index(":") + 1:].strip().split(" ")[0]  # 如有多个，获取第一个结果
            if exe_location.startswith("/"):
                # 处理形如 /e/tool/ffmpeg-master-latest-win64-gpl/bin/ffmpeg.exe
                exe_location = exe_location[1:]
                exe_location = exe_location.replace("/", ":/", 1)
            logger.debug(f"{name} 的位置: {exe_location}")
            name = exe_location
        except subprocess.CalledProcessError:
            logger.warning(f"找不到 {name}")
    elif sys.platform.startswith('linux'):
        name = name
    else:
        name = name
        logger.warning("warn: unknown os")
    return name

def get_video_info(video_path):
    # pprint.pp(video_path)
    ffprobe_cmd = [ffprobe, '-v', 'error', '-show_entries',
                       'stream=duration,r_frame_rate,bit_rate,width,height,codec_name:stream=codec_name,bit_rate:stream=sample_rate',
                       '-of', 'json', video_path]
    result = subprocess.run(ffprobe_cmd, capture_output=True, text=True)
    info_json = result.stdout
    # pprint.pp(info_json)

    info_dict = json.loads(info_json)  # 使用json.loads来解析JSON字符串成字典


    video_stream = info_dict['streams'][0]
    audio_stream = info_dict['streams'][1]if len(info_dict['streams'])>1 else {}

    if 'width' in audio_stream:
        audio_stream,video_stream=(video_stream,audio_stream)
    # frame_rate = eval(video_stream['r_frame_rate'])  # 视频帧率
    # video_bit_rate = int(video_stream['bit_rate'])  # 视频码率
    # width = int(video_stream['width'])  # 视频帧宽度
    # height = int(video_stream['height'])  # 视频帧高度
    # duration = float(video_stream['duration'])  # 视频时长
    # video_codec_name = video_stream['codec_name']  # 视频编码方式
    #
    # audio_bit_rate = int(audio_stream['bit_rate'])  # 音频比特率
    # audio_sample_rate = int(audio_stream['sample_rate'])  # 音频采样率
    # audio_codec_name = audio_stream['codec_name']  # 音频编码方式

    # =============================由于一些wmv可能缺属性、或者有的视频没有音轨，因此设定默认值，可能会有bug======================

    frame_rate = float(video_stream.get('frame_rate', 30.0))  # 视频帧率，默认值为30.0
    video_bit_rate = int(video_stream.get('video_bit_rate', 2521927))  # 视频码率，默认值为2521927
    width = int(video_stream.get('width', 1080))  # 视频帧宽度，默认值为1080
    height = int(video_stream.get('height', 720))  # 视频帧高度，默认值为1920
    duration = float(video_stream.get('duration', 61))  # 视频时长，默认值为61
    video_codec_name = video_stream.get('video_codec_name', 'h264')  # 视频编码方式，默认值为'h264'

    audio_bit_rate = int(audio_stream.get('audio_bit_rate', 321199))  # 音频比特率，默认值为321199
    audio_sample_rate = int(audio_stream.get('audio_sample_rate', 48000))  # 音频采样率，默认值为48000
    audio_codec_name = audio_stream.get('audio_codec_name', 'aac')  # 音频编码方式，默认值为'aac'

    file_size = os.path.getsize(video_path)  # 获取文件大小（以字节为单位）
    file_name = os.path.basename(video_path)  # 获取文件名（不包括路径）
    file_path = os.path.abspath(video_path)

    video_info = {
        'frame_rate': frame_rate,
        'video_bit_rate': video_bit_rate,
        'width': width,
        'height': height,
        'duration': duration,
        'video_codec_name': video_codec_name,
        'audio_bit_rate': audio_bit_rate,
        'audio_sample_rate': audio_sample_rate,
        'audio_codec_name': audio_codec_name,
        'file_size': file_size,
        'file_name': file_name,
        'file_path': file_path,
        'should_be_modify': True

    }

    return video_info


def delete_file(file_path):
    """删除指定路径的文件（如果存在）"""
    if os.path.exists(file_path):
        os.remove(file_path)
        return True
    else:
        return False

def rename_file_remove_prefix(file_path, prefix):
    """重命名文件并去除文件名中的指定前缀"""
    if os.path.exists(file_path):
        # 获取文件名（包括扩展名）
        base_name = os.path.basename(file_path)

        # 检查文件名是否以指定前缀开头
        if base_name.startswith(prefix):
            # 去除前缀并重命名文件
            new_base_name = base_name.replace(prefix, "", 1)
            new_file_path = os.path.join(os.path.dirname(file_path), new_base_name)
            os.rename(file_path, new_file_path)
            return True
        else:
            return False
    else:
        return False

def write_mp4_tag(file_path, tag_name, tag_value):
    try:
        mp4_file = MP4(file_path)
        mp4_file[tag_name] = [tag_value]
        mp4_file.save()
        # print(f"成功将标签'{tag_name}'设置为'{tag_value}'")
    except Exception as e:
        # print(f"{file_path}写入标签时出错：{e}")
        return

def read_mp4_tag(file_path, tag_name):
    try:
        mp4_file = MP4(file_path)
        if tag_name in mp4_file:
            tag_value = mp4_file[tag_name][0]
            # print(f"标签'{tag_name}'的值为: {tag_value}")
            return tag_value
        else:
            # print(f"标签'{tag_name}'不存在于文件{file_path}中")
            return "{}"
    except Exception as e:
        # print(f"{file_path}读取标签时出错：{e}")
        return "{}"


# pprint.pprint(filter_files_by_types(walk_files("D:/资源/nano"),["mp3"]))

def init():
    global ffprobe
    ffprobe=get_os_program_name(ffprobe)

init()