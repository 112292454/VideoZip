# VideoZip
 视频压缩脚本

## 依赖
- ffmpeg
- ffprobe
- requirements.txt的conda环境（这个主要是判断mp4文件的原信息所需要的）

## 使用
`python cli.py -d your_folder`

### 更多参数

-   -h, --help            show this help message and exit                                                         
-   -d DIR, --dir DIR     to processed video dir         ——待处理的文件夹路径，也可以是单个文件名                                                         
-   -t TYPES, --types TYPES                              ——需要处理的文件类型，用英文逗号分隔（基本不用改，除非遇见特殊格式）                                                         
                        to processed video type                                                                 
-   -thread THREAD_NUM, --thread_num THREAD_NUM          ——并发处理的线程数目，默认3（我笔记本的AMD 5800H单线程即可跑满，服务器的 Xeon E5-2660，4线程可跑满）                                                         
                        thread num                                                                              
-   -crf CRF, --crf CRF                                  ——CRF等级，同ffmpeg的（待定，默认的是hevc的28，但是我刚才发现28压出来的视频细节损失还是稍微有点明显，所以可能还需要考虑）       
                        crf level; no loss in {h264-19,h265-22,avi-22}, default in {h264-23,h265-28,avi-30}     
-   -O, --overwrite                                      ——是否覆盖源文件，默认不覆盖                   
                        overwrite compressed file on source file,default is not, and named it as "compressed_xx"


