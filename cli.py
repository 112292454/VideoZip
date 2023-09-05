import json
import os
import pprint
import subprocess
import sys
import traceback
import argparse
from concurrent.futures import ThreadPoolExecutor

from tools import *

input_folder = ""
# output_folder = ""
num_threads = 1  # 设置线程数

ffmpeg = "ffmpeg"

process_status={}


def init():
    global ffmpeg
    ffmpeg = get_os_program_name(ffmpeg)


# 定义处理单个视频的函数
def process_video(video_file):
    try:
        video_path = os.path.dirname(video_file)
        video_file = os.path.basename(video_file)
        base_name = os.path.splitext(video_file)[0]
        input_path = os.path.join(video_path, video_file)
        # 新的文件名，将后缀替换为.mp4
        output_path = os.path.join(video_path, f"compressed_{base_name}.mp4")

        tags: dict = json.loads(read_mp4_tag(input_path, COMPRESSED_FLAG))
        if tags.get("has_compressed"):
            print(f'已处理过的文件，跳过:\t{input_path}')
            return

        # 获取视频信息，可以使用 ffprobe 来获取
        source_video_info = get_video_info(input_path)  # 调用获取视频信息函数
        # todo:压缩率、处理变化、log
        video_info = predict_video_info(source_video_info.copy())

        should_be_modify = video_info['should_be_modify']
        if not should_be_modify:
            return
        else:
            result = run_command(input_path, output_path, video_info)
            if result.returncode == 0:
                save_file_logs(source_video_info, video_info, output_path)
                if args.overwrite:
                    if delete_file(input_path) and rename_file_remove_prefix(output_path, "compressed_"):
                        # 不知道应不应该将重命名的换成指定两个文件名的方式，而不是删除前缀
                        process_status[input_path] = "Succeed"
                else:
                    process_status[input_path] = "Succeed"


            else:
                process_status[input_path] = "Failed"

    except Exception as e:
        print('process failed : ' + video_file)
        traceback.print_exc()


def save_file_logs(source_video_info, video_info, video_path):
    logs = {"has_compressed": True}
    logs["source_video_info"] = json.dumps(source_video_info, indent=2)
    logs["video_info"] = json.dumps(video_info, indent=2)
    write_mp4_tag(video_path, COMPRESSED_FLAG, json.dumps(logs, indent=2))


def run_command(input_path, output_path, video_info):
    width = video_info['width']  # 视频帧宽度
    height = video_info['height']  # 视频帧高度
    # 在这里添加判断逻辑，根据帧率、码率、大小等信息来确定压缩参数
    # 根据你的需求，可以调整视频的分辨率、帧率、码率等参数
    compress_command = [
        ffmpeg,  # FFmpeg 命令
        '-i', input_path,  # 输入文件路径
        '-c:v', video_info['video_codec_name'],  # 视频编码器
        # '-preset', 'fast',
        '-crf', str(args.crf),  # 264默认23，265默认28。越低越清晰，越大.每差6，体积翻倍
        '-maxrate', str(video_info['video_bit_rate']),  # 视频比特率
        '-bufsize', str(video_info['video_bit_rate'] * 8),
        '-vf', f'scale={width}:{height}',  # 调整分辨率
        '-r', str(video_info['frame_rate']),  # 输出帧率
        '-c:a', 'aac',  # 音频编码器为 AAC
        '-b:a', str(video_info['audio_bit_rate']),  # 音频比特率
        '-ar', str(video_info['audio_sample_rate']),  # 音频采样率
        '-y',
        output_path  # 输出文件路径
        # input_path
        # !!warn：此处直接覆盖源文件！使用之前最好做有备份，如果发现哪里有问题立刻停止。我目前测试了30g的视频没啥问题
        # 如果保险一点可以使用上面注释掉的的output path，不直接使用input path来覆盖源文件
        # 哦没事了，ffmpeg不允许覆盖源文件，只能py代码里手动删原本的，
    ]
    # 举例：调整分辨率为 720p，并降低码率
    # 执行压缩命令
    return subprocess.run(compress_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def predict_video_info(video_info):
    M = 1024 * 1024
    # 从返回的字典中逐个声明变量
    frame_rate = video_info['frame_rate']  # 视频帧率
    video_bit_rate = video_info['video_bit_rate']  # 视频码率
    width = video_info['width']  # 视频帧宽度
    height = video_info['height']  # 视频帧高度
    duration = video_info['duration']  # 视频时长
    video_codec_name = video_info['video_codec_name']  # 视频编码方式

    audio_bit_rate = video_info['audio_bit_rate']  # 音频比特率
    audio_sample_rate = video_info['audio_sample_rate']  # 音频采样率
    audio_codec_name = video_info['audio_codec_name']  # 音频编码方式

    should_be_modify = video_info['should_be_modify']
    file_size = video_info['file_size']
    file_name: str = video_info['file_name']
    file_p: str = video_info['file_path']

    if file_name.startswith("compressed_"):
        video_info['should_be_modify'] = False
        return

    # VR不作调整
    if 'vr' in file_p.lower():
        video_info['should_be_modify'] = False
        return video_info

    # 初音演唱会不作调整
    if 'miku' in file_p.lower():
        video_info['should_be_modify'] = False
        return video_info

    # 分辨率调整。8k、4k均降一档；2k待定要不要变1080p；720p以下的均提升到720p
    shape = {
        '8k': (7680, 4320),
        '4k': (3840, 2160),
        '2k': (2560, 1440),
        "1080p": (1920, 1080),
        "720p": (1280, 720)
    }

    def size_judge(w, h, v1, v2):
        return (v1 * 0.99 < w < v1 * 1.01 and v2 * 0.99 < h < v2 * 1.01) or (
                v1 * 0.99 < h < v1 * 1.01 and v2 * 0.99 < w < v2 * 1.01)

    def adjust_trans(a, b, v1, v2):
        if a > b:
            return v1, v2
        else:
            return v2, v1

    video_size: str = '1080p'
    if size_judge(width, height, *shape['8k']):  # 8K
        (video_info['width'], video_info['height']) = adjust_trans(width, height, *shape['4k'])
        video_size = '4k'
    elif size_judge(width, height, *shape['4k']):
        (video_info['width'], video_info['height']) = adjust_trans(width, height, *shape['2k'])
        video_size = '2k'
    # elif size_judge(width,height,*shape['2k']):
    #     (video_info['width'],video_info['height'])=adjust_trans(width,height,*shape['1080p'])
    #     video_size='1080p'
    elif width < 720 or height < 720:
        (video_info['width'], video_info['height']) = adjust_trans(width, height, *shape['720p'])
        video_size = '720p'

    # 帧率，归入到[30,60]
    if frame_rate > 60:
        video_info['frame_rate'] = 60
    elif frame_rate < 30:
        video_info['frame_rate'] = 30

    # 比特率
    br = {
        '8k': 32 * M,
        '4k': 16 * M,
        '2k': 8 * M,
        "1080p": 3 * M,
        "720p": 1.5 * M
    }
    # 只缩小，但是避免误操作，大小超过标称3倍的视频不做处理
    if br[video_size] <= video_bit_rate < br[video_size] * 3:
        video_info['video_bit_rate'] = br[video_size]
    # 对于不足720p的放大到720p的码率，同时至少视频要5M，避免误操作
    if video_bit_rate < br['720p'] and file_size > 5 * M:
        video_info['video_bit_rate'] = br['720p']
    # 60p视频帧率*1.5。https://zunzheng.com/news/archives/40648
    if frame_rate >= 59:
        video_info['video_bit_rate'] *= 1.5

    # 编码方式
    # 画质 低比特用h265，高比特用vp9；https://www.macxdvd.com/mac-dvd-video-converter-how-to/vp9-vs-h265.htm
    # 编码时间 h264为vp9的1/4；https://bitmovin.com/vp9-vs-hevc-h265/
    # 大小 差不多，h265略小（0.2%到38%）。https://www.gumlet.com/learn/vp9-vs-h265/
    # if size_judge(width, height, *shape['1080p']) or size_judge(width, height, *shape['720p']):
    video_info['video_codec_name'] = 'libx265'
    # args.crf = 28
    # else:
    #     video_info['video_codec_name']='libvpx-vp9'

    # 避免断点重复操作：关键参数不变的不修改

    # update
    video_info['file_size'] = video_info['duration'] * video_info['video_bit_rate'] / 8

    return video_info


init()

if __name__ == '__main__':
    try:
        args = get_args()

        num_threads = args.thread_num
        types = args.types.split(",")
        input_folder = args.dir

        # 创建输出文件夹
        # if not os.path.exists(output_folder):
        #     os.makedirs(output_folder)

        # 获取输入文件夹中的所有视频文件
        video_files = walk_files(input_folder)
        video_files = filter_files_by_types(video_files, types)
        for file_path in video_files:
            print(file_path)
        # 使用线程池并发处理视频压缩任务
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            executor.map(process_video, video_files)
        print("压缩完成！")
        for key, value in process_status.items():
            print(value, ":\t", key)
    except Exception as e:
        traceback.print_exc()

# todo: windows适配：subprocess.run在win上需要写ffmpeg（或ffprobe）那个exe的全路径，不然报错，而linux直接ffmpeg就可以了。
#  所以需要whereis ffmpeg自动获取到这个exe然后填进去
# ——finished

# todo: 已压缩文件不再重复处理：目前压缩后的画面效果尚未验证，因此是在文件名加一个前缀compressed来区分。
#  而后续应当是直接覆盖的，所以考虑：要么附带留一个log文件，要么在视频的元信息里写入一个标记

# todo: 目前存在个问题，设置了bufsize之后，会导致压缩出的文件比直接只设置h265而不加其他任何参数就压缩的结果，反而要大几mb。
#  如果是设置缓冲区增强了画面变化激烈时刻的清晰度，那这是理想的行为；但是如果没有增益反而压缩率低了，那就是bug了，需要考虑还要不要设置这个


# fix： 部分年代较早的视频转h265之后无法播放，原因未知，文件见附；h264可以播放，但压缩效果毕竟不好，并且会糊；vp9速度不到h265的一半，太慢了
# 已提问题： https://stackoverflow.com/questions/77030749/when-using-ffmpeg-encode-to-hevc-but-got-rawvideo
# ——疑似finish，设置成MP4就好了

# fix： webm格式视频好像ffprobe获取信息不全，目前的写法会缺字段无法转换，可以考虑缺省。比如以下就会缺字段
# ```
# ffprobe  -v error -show_entries stream=duration,r_frame_rate,bit_rate,width,height,codec_name:stream=codec_name,bit_rate:stream=sample_rate -of json "/data/share
# /视频h/玛丽罗斯/Fluffy Pokemon2/Fluffy Pokemon2/玛丽罗斯/3db5ae8118843082dea2aed43b0cb167.webm"
# {
#     "programs": [
#
#     ],
#     "streams": [
#         {
#             "codec_name": "vp8",
#             "width": 1280,
#             "height": 720,
#             "r_frame_rate": "30/1"
#         },
#         {
#             "codec_name": "vorbis",
#             "sample_rate": "48000",
#             "r_frame_rate": "0/0"
#         }
#     ]
# }
# ```
#
# 正常的：
# ```
# ffprobe  -v error -show_entries stream=duration,r_frame_rate,bit_rate,width,height,codec_name:stream=codec_name,bit_rate:stream=sample_rate -of json "/data/share/视频h/玛丽罗斯/Fluffy Pokemon/compressed_Honoka-b-1080p.mp4"
# {
#     "programs": [
#
#     ],
#     "streams": [
#         {
#             "codec_name": "hevc",
#             "width": 1920,
#             "height": 1080,
#             "r_frame_rate": "60/1",
#             "duration": "10.000000",
#             "bit_rate": "3073224"
#         },
#         {
#             "codec_name": "aac",
#             "sample_rate": "44100",
#             "r_frame_rate": "0/0",
#             "duration": "10.008005",
#             "bit_rate": "130178"
#         }
#     ]
# }
# ```
