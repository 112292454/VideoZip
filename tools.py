import argparse
import json
import os
import pprint
import subprocess
import sys

ffprobe="ffprobe"



# 获取文件夹内所有非目录文件
def walk_files(root_dir):
    file_list = []

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

def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('-d', '--dir', type=str, required=False,
                        help='to processed video dir')
    parser.add_argument('-t', '--types', type=str, default='mp4,avi,webm,mov,mpg,m4a,m4v,mpeg,wmv ',
                        help='to processed video type')
    parser.add_argument('-thread', '--thread_num', type=int, default='4',
                        help='thread num')
    args = parser.parse_args()
    return args

def get_os_program_name(name):
    if sys.platform.startswith('win'):
        try:
            output = subprocess.check_output(["whereis", name], universal_newlines=True)
            exe_location = output[output.index(":") + 1:].strip().split(" ")[0]  # 如有多个，获取第一个结果
            if exe_location.startswith("/"):
                # 处理形如 /e/tool/ffmpeg-master-latest-win64-gpl/bin/ffmpeg.exe
                exe_location = exe_location[1:]
                exe_location = exe_location.replace("/", ":/", 1)
            print(f"{name} 的位置: {exe_location}")
            name = exe_location
        except subprocess.CalledProcessError:
            print(f"找不到 {name}")
    elif sys.platform.startswith('linux'):
        name = name
    else:
        name = name
        print("warn: unknown os")
    return name

def get_video_info(video_path):
    pprint.pp(video_path)
    ffprobe_cmd = [ffprobe, '-v', 'error', '-show_entries',
                       'stream=duration,r_frame_rate,bit_rate,width,height,codec_name:stream=codec_name,bit_rate:stream=sample_rate',
                       '-of', 'json', video_path]
    result = subprocess.run(ffprobe_cmd, capture_output=True, text=True)
    info_json = result.stdout
    # pprint.pp(info_json)

    info_dict = json.loads(info_json)  # 使用json.loads来解析JSON字符串成字典


    video_stream = info_dict['streams'][0]
    audio_stream = info_dict['streams'][1]

    frame_rate = eval(video_stream['r_frame_rate'])  # 视频帧率
    video_bit_rate = int(video_stream['bit_rate'])  # 视频码率
    width = int(video_stream['width'])  # 视频帧宽度
    height = int(video_stream['height'])  # 视频帧高度
    duration = float(video_stream['duration'])  # 视频时长
    video_codec_name = video_stream['codec_name']  # 视频编码方式

    audio_bit_rate = int(audio_stream['bit_rate'])  # 音频比特率
    audio_sample_rate = int(audio_stream['sample_rate'])  # 音频采样率
    audio_codec_name = audio_stream['codec_name']  # 音频编码方式

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

# pprint.pp(get_video_info("D:\\资源\\糖心VLOG\\[小晗喵]\\猫耳女仆让我来品尝主人的肉棒吧_幻想主人 肉棒入侵_AV棒蹂躏嫩穴1.mp4"))

# pprint.pprint(filter_files_by_types(walk_files("D:/资源/nano"),["mp3"]))

def init():
    global ffprobe
    ffprobe=get_os_program_name(ffprobe)

init()