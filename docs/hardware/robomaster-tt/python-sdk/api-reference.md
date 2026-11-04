# RoboMaster Python SDK - drone API reference

Drone-related classes from the official API page (https://robomaster-dev.readthedocs.io/en/latest/python_sdk/robomaster.html), converted to Markdown. DJI wrote the docstrings in Chinese; parameter ranges match the Tello SDK 3.0 commands in `../sdk-3.0-reference.md`.

## robomaster.robot.Drone

*class* `robomaster.robot.Drone`(*cli=None*)  
Bases: `robomaster.robot.RobotBase`

教育系列无人机

`close`()  
停止drone对象

`config_sta`(*ssid*, *password*)  
设置飞机的连接模式为组网模式

**Parameters:**

- **ssid** – 路由器的账号
- **password** – 路由器的密码

**Returns:**

bool: 设置结果

`get_acceleration`()  
获取飞机三轴加速度值

**Returns:**

dict: 飞机三轴加速度值

`get_attitude`()  
获取飞机三轴姿态信息

**Returns:**

dict: 飞机三轴姿态信息

`get_baro`()  
获取电机气压计高度

**Returns:**

float: 电机气压计高度

`get_drone_version`()  
获取飞机固件版本号

**Returns:**

string: 版本号

`get_esp32_version`()  
获取esp32版本号

**Returns:**

string: 版本号

`get_hardware`()  
获取飞机硬件信息 本命令仅支持SDK版本号\>=30 可通过hardware?指令查询是否有接WIFI拓展模块，没接拓展模块返回TELLO，接了拓展模块返回RMTT。

**Returns:**

string: 硬件信息

`get_height`()  
获取飞机相对高度

**Returns:**

string: 飞机相对高度

`get_motor_time`()  
获取电机运行时间

**Returns:**

string: 电机的运行时间

`get_sdk_version`()  
获取SDK版本号

**Returns:**

string: 版本号

`get_sn`()  
获取飞机sn号

**Returns:**

string: 飞机的SN号

`get_ssid`()  
获取SSID名称

**Returns:**

string: ssid名称

`get_status`(*name*)  
获取飞机指定的状态

**Parameters:**

**name** – string:需要获取的状态名，可列表\[“MID”, “x”, “y”, “z”, “mpry”, “pitch”, “roll”, “yaw”, “vgx”, “vgy”, “vgz”, “templ”, “temph”, “tof”, “h”, “bat”, “baro”, “time”, “agx”, “agy”, “agz”\]，详细介绍 参考SDK使用文档

**Returns:**

name对应状态的数据值，DDS_PAD_MPRY_FLAG 对应状态的返回值为长度为3的list，分别代表的在飞机相对挑战卡的pitch、yaw、row值， 其他状态返回的都是float数据

`get_subnets`()  
Look through the machine’s internet connection and returns subnet addresses and server ip :return: list\[str\]: subnets

> list\[str\]: addr_list

`get_temp`()  
获取飞机机身温度

**Returns:**

dict: 飞机机身温度

`get_wifi`()  
获取wifi信噪比

**Returns:**

float: wifi的信噪比数值

`get_wifi_version`()  
获取WIFI版本号

**Returns:**

string: 版本号

`scan_drone_robot`()  
Automatic scanning of robots in the network

**Parameters:**

**num** –

**Returns:**

`set_wifichannel`(*channel*)  
设置飞机WIFI信道

**Parameters:**

**channel** – 需要设置的信道

**Returns:**

bool: 设置结果

`sub_drone_info`(*freq=5*, *callback=None*, *\*args*, *\*\*kw*)  
订阅飞机高度、气压计、电机运行时间信息

**Parameters:**

- **freq** – 订阅数据的频率, 1HZ, 5HZ, 10HZ
- **callback** – 传入数据处理的回掉函数
- **args** – 回调函数参数
- **kw** – 回调函数参数

**Returns:**

返回订阅结果

`sub_temp`(*freq=5*, *callback=None*, *\*args*, *\*\*kw*)  
订阅飞机温度信息

**Parameters:**

- **freq** – 订阅数据的频率, 1HZ, 5HZ, 10HZ
- **callback** – 传入数据处理的回掉函数
- **args** – 回调函数参数
- **kw** – 回调函数参数

**Returns:**

返回订阅结果

`sub_tof`(*freq=5*, *callback=None*, *\*args*, *\*\*kw*)  
订阅飞机tof信息

**Parameters:**

- **freq** – 订阅数据的频率, 1HZ, 5HZ, 10HZ
- **callback** – 传入数据处理的回掉函数
- **args** – 回调函数参数
- **kw** – 回调函数参数

**Returns:**

返回订阅结果

`unsub_drone_info`()  
取消订阅飞机高度、气压计、电机运行时间信息

**Returns:**

返回取消订阅结果

`unsub_temp`()  
取消订阅温度信息。

**Returns:**

返回取消订阅结果。

`unsub_tof`()  
取消订阅tof信息

**Returns:**

返回取消订阅结果

## robomaster.flight.Flight

*class* `robomaster.flight.Flight`(*robot*)  
Bases: `object`

教育无人机 飞行器模块

`backward`(*distance=0*, *retry=True*)  
向后飞行distance厘米， 指相对距离

**Param:**

distance: float:\[20, 500\]向后飞行的相对距离，单位 cm

**Param:**

retry: bool:是否重发命令

**Returns:**

action对象

`curve`(*x1=0*, *y1=0*, *z1=0*, *x2=0*, *y2=0*, *z2=0*, *speed=20*, *mid=None*, *retry=True*)  
以设置速度飞弧线，经过对应坐标系中的(x1, y1, z1)点到（x2, y2, z2）点

如果选用mid参数，则对应坐标系为指定挑战卡的坐标系。不使用挑战卡时，飞机的前方为x轴正方向，飞机的左方为y轴的正方向 如果mid参数为默认值None,则为飞机自身坐标系

**Param:**

x1: float:\[-500, 500\] x轴坐标

**Param:**

y1: float:\[-500, 500\] y轴坐标

**Param:**

z1: float:如果使用挑战卡（mid不为None），取值范围为 \[0, 500\]; 如果不使用挑战卡（mid为None），取值范围为\[-500, 500\]

**Param:**

x2: float:\[-500, 500\] x轴坐标

**Param:**

y2: float:\[-500, 500\] y轴坐标

**Param:**

z2: float:如果使用挑战卡（mid不为None），取值范围为 \[0, 500\]; 如果不使用挑战卡（mid为None），取值范围为\[-500, 500\]

**Param:**

speed: float:\[10, 60\] 飞行的速度

**Param:**

mid: string: 不使用挑战卡时mid为None，运动坐标系为飞机自身坐标系；当使用挑战卡时mid为对应挑战卡编号，运动坐标系为对应挑战卡 坐标系。挑战卡编号参考挑战卡使用说明

**Param:**

retry: bool:是否重发命令

**Returns:**

action对象

`down`(*distance=0*, *retry=True*)  
向下飞distance厘米，指相对距离

**Param:**

distance: float:\[20, 500\]向下飞行的相对距离，单位 cm

**Param:**

retry: bool:是否重发命令

**Returns:**

action对象

`flip`(*direction='f'*, *retry=True*)  
控制飞机向指定方向翻滚

当电量低于50%时无法完成翻滚 :param direction: string: 飞机翻转的方向， ’l‘ 向左翻滚，’r‘ 向右翻滚，’f‘ 向前翻滚， ’b‘ 向后翻滚 :param: retry: bool:是否重发命令 :return: action对象

`flip_backward`(*retry=True*)  
控制飞机向后翻滚

当电量低于50%时无法完成翻滚 :param: retry: bool:是否重发命令 :return: action对象

`flip_forward`(*retry=True*)  
控制飞机向前翻滚

当电量低于50%时无法完成翻滚 :param: retry: bool:是否重发命令 :return: action对象

`flip_left`(*retry=True*)  
控制飞机向左翻滚

当电量低于50%时无法完成翻滚 :param: retry: bool:是否重发命令 :return: action对象

`flip_right`(*retry=True*)  
控制飞机向右翻滚

当电量低于50%时无法完成翻滚 :param: retry: bool:是否重发命令 :return: action对象

`fly`(*direction='forward'*, *distance=0*, *retry=True*)  
控制飞机向指定方向飞行指定距离。

**Param:**

direction: string: 飞行的方向，”forward” 向上飞行， “back” 向下飞行， “up” 向上飞行， “down” 向下飞行， “left” 向左飞行， “right” 向右飞行

**Param:**

distance: float:\[20, 500\]，飞行的距离，单位 cm

**Param:**

retry: bool:是否重发命令

**Returns:**

action对象

`forward`(*distance=0*, *retry=True*)  
向前飞行distance厘米，指相对距离

**Param:**

distance: float:\[20, 500\]向前飞行的相对距离，单位 cm

**Param:**

retry: bool:是否重发命令

**Returns:**

action对象

`get_speed`()  
获取当前设置速度

**Returns:**

float: 当前速度值，单位 cm/s

`go`(*x*, *y*, *z*, *speed=10*, *mid=None*, *retry=True*)  
控制飞机以设置速度飞向指定坐标位置

注意， x,y,z 同时在-20~20时，飞机不会运动。当不使用挑战卡时，飞机所在位置为坐标系原点，飞机的前方为x轴正方向，飞机的左方为y轴的正方向

**Param:**

x: float: \[-500, 500\] x轴的坐标，单位 cm

**Param:**

y: float: \[-500, 500\] y轴的坐标，单位 cm

**Param:**

z: float: \[-500, 500\] z轴的坐标，单位 cm

**Param:**

speed: float: \[10, 100\] 运动速度， 单位 cm/s

**Param:**

mid: string: 不使用挑战卡时mid为None，运动坐标系为飞机自身坐标系；当使用挑战卡时mid为对应挑战卡编号， 运动坐标系为指定挑战卡的坐标系。支持编号可参考挑战卡使用说明。

**Param:**

retry: bool:是否重发命令

**Returns:**

action对象

`jump`(*x=0*, *y=0*, *z=0*, *speed=20*, *yaw=0*, *mid1='m-1'*, *mid2='m-1'*, *retry=True*)  
飞行器飞往mid1坐标系的(x, y, z)点后悬停，识别mid2的挑战卡，飞到mid2坐标系下(0, 0, z)的位置并且旋转到设定的yaw值

**Param:**

x: float: \[-500, 500\]，x轴的坐标，单位 cm

**Param:**

y: float: \[-500, 500\]，y轴的坐标，单位 cm

**Param:**

z: float: \[0, 500\]，z轴的坐标，单位 cm

**Param:**

speed: float:\[10, 60\]，飞行的速度, 单位 cm/s

**Param:**

yaw: \[-360, 360\] 最终悬停的yaw轴角度, 单位 °

**Param:**

mid1: string: 第一个挑战卡的id, 挑战卡id的介绍参考挑战卡使用说明

**Param:**

mid2: string: 第一个挑战卡的id, 挑战卡id的介绍参考挑战卡使用说明

**Param:**

retry: bool:是否重发命令

**Returns:**

action对象

`land`(*retry=True*)  
自动降落

**Param:**

retry: bool:是否重发命令

**Returns:**

action对象

`left`(*distance=0*, *retry=True*)  
向左飞行distance厘米， 指相对距离

**Param:**

distance: float:\[20, 500\]向左飞行的相对距离，单位 cm

**Param:**

retry: bool:是否重发命令

**Returns:**

action对象

`mission_pad_off`()  
关闭挑战卡探测

**Returns:**

bool:控制结果

`mission_pad_on`()  
打开挑战卡探测

默认同时打开前视和下视探测 :return: bool: 控制结果

`motor_off`()  
控制飞机停桨

**Returns:**

action对象

`motor_on`()  
控制飞机转桨

**Returns:**

action对象

`move`(*x=0*, *y=0*, *z=0*, *speed=10*, *mid=None*, *retry=True*)  
飞机相对位置的控制

x/y/z值不能同时在-20~20之间，适用该接口时应当先打开挑战卡检测功能

**Param:**

x: float:\[-500, 500\]，目标位置在挑战卡坐标系中的x坐标，实际取值范围要根据挑战卡大小调整，单位 cm

**Param:**

y: float:\[-500, 500\]，目标位置在挑战卡坐标系中的y坐标，实际取值范围要根据挑战卡大小调整，单位 cm

**Param:**

z: float:\[-500, 500\]，目标位置在挑战卡坐标系中的z坐标，实际取值范围要根据挑战卡大小调整，单位 cm

**Param:**

speed: int:\[10, 100\]，运动速度，单位 cm/s

**Param:**

mid: string: 挑战卡的编号，支持编号可参考挑战卡使用说明

**Param:**

retry: bool:是否重发命令

**Returns:**

action对象

`moveto`(*yaw=0*, *retry=True*)  
控制飞机旋转到挑战卡坐标系中指定的绝对角度

**Param:**

yaw: float:\[-180, 180\]，飞机在挑战卡上的的角度，俯视时，顺时针为正角度，逆时针为负角度

**Param:**

retry: bool:是否重发命令

**Returns:**

action 对象

`rc`(*a=0*, *b=0*, *c=0*, *d=0*)  
控制飞机遥控器的四个杆量

**Parameters:**

- **a** – float:\[-100, 100\] 横滚
- **b** – float:\[-100, 100\] 俯仰
- **c** – float:\[-100, 100\] 油门
- **d** – float:\[-100, 100\] 偏航

`right`(*distance=0*, *retry=True*)  
向右飞行distance厘米， 指相对距离

**Param:**

distance: float:\[20, 500\]向右飞行的相对距离，单位 cm

**Param:**

retry: bool:是否重发命令

**Returns:**

action对象

`rotate`(*angle=0*, *retry=True*)  
控制飞机旋转指定角度

**Param:**

angle: float:\[-360, 360\] 旋转的角度，俯视飞机时，顺时针为正角度，逆时针为负角度

**Param:**

retry: bool:是否重发命令

**Returns:**

action对象

`set_speed`(*speed=0*)  
设置当前飞行速度

**Parameters:**

**speed** – float:\[10, 100\]，飞行速度，单位 cm/s

**Returns:**

bool: 设置结果

`stop`(*retry=True*)  
停止rc运动并悬停，任何时候都可以

**Param:**

retry: bool:是否重发命令

**Returns:**

bool: 控制结果

`sub_attitude`(*freq=5*, *callback=None*, *\*args*, *\*\*kw*)  
订阅飞机姿态信息

**Parameters:**

- **freq** – enum:(1, 5, 10)，订阅数据的频率
- **callback** – 传入数据处理的回掉函数
- **args** – 回调函数参数
- **kw** – 回调函数参数

**Returns:**

bool: 数据订阅结果

`sub_imu`(*freq=5*, *callback=None*, *\*args*, *\*\*kw*)  
订阅飞机陀螺仪信息

**Parameters:**

- **freq** – enum:(1, 5, 10)，订阅数据的频率
- **callback** – 传入数据处理的回掉函数
- **args** – 回调函数参数
- **kw** – 回调函数参数

**Returns:**

bool: 数据订阅结果

`takeoff`(*retry=True*)  
自动起飞

**Param:**

retry: bool:是否重发命令

**Returns:**

action对象

`throw_fly`()  
控制飞机抛飞

**Returns:**

action对象

`unsub_attitude`()  
取消订阅飞机姿态信息

**Returns:**

bool: 取消数据订阅结果

`unsub_imu`()  
取消订阅飞机陀螺仪信息

**Returns:**

bool: 取消数据订阅结果

`up`(*distance=0*, *retry=True*)  
向上飞distance厘米，指相对距离

**Param:**

distance: float:\[20, 500\]向上飞行的相对距离，单位 cm

**Param:**

retry: bool:是否重发命令

**Returns:**

action对象

## robomaster.camera.TelloCamera

*class* `robomaster.camera.TelloCamera`(*robot*)  
Bases: `robomaster.camera.Camera`

教育无人机 摄像机模块

`read_cv2_image`(*timeout=3*, *strategy='pipeline'*)  
读取一帧视频流帧

**Parameters:**

- **timeout** – float: (0, inf)，超时参数，在timeout时间内未获取到视频流帧，函数返回
- **strategy** – enum: (“pipeline”, “newest”)，读取帧策略：pipeline 依次读取缓存的帧信息，newest 获取最新的一帧 数据，会清空旧的数据帧

**Returns:**

image

`read_video_frame`(*timeout=3*, *strategy='pipeline'*)  
读取一帧视频流帧

**Parameters:**

- **timeout** – float: (0, inf)，超时时间，超过指定timeout时间后函数返回
- **strategy** – enum: (“pipeline”, “newest”) 读取帧策略：pipeline 流水线依次读取，newest 获取最新的一帧数据， 注意会清空老的数据帧队列

**Returns:**

frame, 已解码的视频流帧字节流

`set_bitrate`(*bitrate*)  
设置飞机传输码率

**Parameters:**

**bitrate** – 需要设置的传输码率，\[0, 6\]

**Returns:**

bool: 设置结果

`set_fps`(*fps*)  
设置飞机视频帧率

**Parameters:**

**fps** – 需要设置的帧率，\[high, middle, low\]

**Returns:**

bool: 设置结果

`set_resolution`(*resolution*)  
设置飞机视频分辨率

**Parameters:**

**resolution** – 需要设置的视频分辨率，\[high, low\]

**Returns:**

bool: 设置结果

`start_video_stream`(*display=True*)  
开启视频流

**Parameters:**

**display** – bool, 是否显示视频流

**Returns:**

bool: 调用结果

## robomaster.battery.TelloBattery

*class* `robomaster.battery.TelloBattery`(*robot*)

Bases: `object`

教育无人机 电池模块

`get_battery`()  
获取电池电量信息

**Returns:**

int: 电池的剩余电量百分比

`sub_battery_info`(*freq=5*, *callback=None*, *\*args*, *\*\*kw*)

订阅电池信息

**Parameters:**

**freq** – enum:(1,5,10) 设置数据订阅数据的推送频率，单位 Hz

**callback** –

回调函数，返回数据 percent:

- **percent** – 电池电量百分比
- **args** – 可变参数
- **kw** – 关键字参数

**Returns:**

bool: 数据订阅结果

`unsub_battery_info`()  
取消订阅飞机电池信息

**Returns:**

返回取消订阅结果

## robomaster.action.Action

*class* `robomaster.action.Action`(*\*\*kw*)  
Bases: `object`

`wait_for_completed`(*timeout=None*)  
等待任务动作直到完成

**Parameters:**

**timeout** – 超时，在timeout前未完成任务动作，直接返回

**Returns:**

bool: 动作在指定时间内完成，返回True; 动作超时返回False

## robomaster.action.TextAction

*class* `robomaster.action.TextAction`(*\*\*kw*)  
Bases: [`robomaster.action.Action`](#robomaster.action.Action "robomaster.action.Action")

Blocking action in plaintext protocol

`wait_for_completed`(*timeout=None*)  
等待任务动作直到完成

**Parameters:**

**timeout** – 超时，在timeout前未完成任务动作，直接返回

**Returns:**

bool: 动作在指定时间内完成，返回True; 动作超时返回False

