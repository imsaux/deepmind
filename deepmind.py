# encoding=utf-8

from PIL import Image, ImageTk
from tkinter import filedialog, Menu, Tk, Canvas, Toplevel, Message, Button, Frame, Label
from tkinter.ttk import  Treeview, Scrollbar
import os
import sys
import os.path
import datetime
import logging
import sqlite3
import pickle

logging.basicConfig(
    level=10,
    filename='deepmind.log',
    format='[time]%(asctime)-15s[time] %(filename)s[line:%(lineno)d] %(levelname)s >>> %(message)s',
    datefmt='[%Y-%m-%d %H:%M:%S]',
    filemode='a'
)  # 全局日志模块


class sqlhandle():
    def __init__(self):
        # 数据库初始化
        with sqlite3.connect(
                'deepmind.db',
                detect_types=sqlite3.PARSE_DECLTYPES) as self.conn:
            self.sqlcursor = self.conn.cursor()
            # 建初始表
            # 日期，时间，日志类型，图片，车型，状态（未修改、车轴异常、已修改）
            sql_pics = '''CREATE TABLE IF NOT EXISTS pics
            (
                id integer primary key autoincrement not null,
                opdate integer,
                optime integer,
                filename varchar,
                kind varchar,
                rootpath varchar,
                laststate integer,
                oldlabel blob,
                newlabel blob
            )
            '''
            self.sqlcursor.execute(sql_pics)
            sql_history = '''CREATE TABLE IF NOT EXISTS history
            (
                id integer primary key autoincrement not null,
                hdate integer,
                htime integer,
                serialization blob
            )
            '''
            self.sqlcursor.execute(sql_history)
            self.conn.commit()

    def exec(self, _sql, _list, mode='single', result=False):
        print('_sql >>> ', _sql)
        print('_list >>> ', _list)
        if mode == 'single':
            if len(_list) == 0:
                self.sqlcursor.execute(_sql)
            else:
                self.sqlcursor.execute(_sql, _list)
        else:
            self.sqlcursor.executemany(_sql, _list)
        if result is False:
            self.conn.commit()
            return None
        else:
            self.conn.commit()
            recv = self.sqlcursor.fetchall()
            # print(recv)
            return recv

class box():
    # boundingbox类
    def __init__(self, _classification, _rectangle, _isfromtxt, _canvasid):
        self.classification = _classification
        self.rectangle = _rectangle
        self.fromtxt = _isfromtxt
        self.canvasid = _canvasid

    def getclass(self):
        return self.classification

    def getrectangle(self):
        return self.rectangle

    def getfromTXT(self):
        return self.fromtxt

    def setclass(self, newclass):
        self.classification = newclass

    def setcanvasid(self, newcanvasid):
        self.canvasid = newcanvasid

    def setrectangle(self, newrectangle):
        self.rectangle = newrectangle

    def getcanvasid(self):
        return self.canvasid

    def getLableString(self):
        return str(self.classification) + \
               ' 0.0 0 0.0 ' + \
               ' '.join([str(x) for x in self.rectangle[0]] + \
                        [str(x) for x in self.rectangle[1]]) + \
               ' 0.0 0.0 0.0 0.0 0.0 0.0 0.0'


class logic():
    def __init__(self, size):
        self.index = -1  # 图片序号
        self.pics = []
        # box = ['window', ((event.x, event.y), (event.x, event.y))]
        self.boxes = []
        self.src_boxes = None  # 原始数据序列化
        self.coords = []
        self.picspath = None
        self.labelspath = None
        self.ratio = 1.0
        self.zoomratio = 1.0, 1.0
        self.outputsize = 1096, 256
        self.picsize = size
        self.dir_path = None
        self.classcolor = {
            'window': 'red',  # 车窗
            'door': 'yellow',
            'wheel': 'green',
            'spillobj': 'blue',
            'None': 'pink',
            'point': 'gray'}
        self.warningdir = ''
        self.nochangeddir = ''
        self.changeddir = ''
        self.sh = sqlhandle()

    def getcolors(self, _class):
        # 根据标框类型获取对应颜色
        try:
            return self.classcolor[str(_class)]
        except:
            return self.classcolor['None']

    """
    屏幕坐标 << >> 原图坐标
    """
    def coord_screen2originimage(self, coord):
        x = coord[0] / self.ratio
        y = coord[1] / self.ratio
        # x = coord[0] / self.ratio * self.zoomratio[0]
        # y = coord[1] / self.ratio * self.zoomratio[1]
        return int(x), int(y)

    """
    原图坐标 << >> 输出特定坐标系
    """
    def coord_originimage2output(self, _from, _to):
        pass


    def addcoords(self, coord, fast=False):
        # 将左键单击坐标加入列表1
        if fast is False:
            self.coords.append(self.coord_screen2originimage(coord))
        elif fast is True:
            self.coords.append(coord)
        if len(self.coords) % 2 == 0 and len(self.coords) > 0:
            x = box(None, (self.coords[0], self.coords[1]), False, None)
            self.boxes.append(x)
            self.coords.clear()
    
    def getmiddlexy(self, _currentimage):
        x = int(self.picsize[0] / 2 - _currentimage.size[0] / 2)
        y = int(self.picsize[1] / 2 - _currentimage.size[1] / 2)
        return x, y

    def clear_coords(self):
        self.coords.clear()

    def getboxes(self):
        # 获取boundingbox列表
        return self.boxes

    def getcoords(self):
        # 获取坐标点列表
        return self.coords
    
    def getfileindex(self, file):
        if file is not None and os.path.exists(os.path.join(self.dir_path, file)) is True:
            return self.pics.index(file)
        else:
            return None

    def getfilecount(self):
        return len(self.pics)

    def getfiles(self, path):
        # 根据类别生成文件列表
        self.dir_path = path
        self.index = -1
        self.pics = []
        if path != ():
            logging.info('[path]' + self.dir_path + '[path]')
            _files = []
            for root, dirs, files in os.walk(self.dir_path, topdown=False):
                _files = [str(name) for name in files]
            for f in _files:
                if f[-4:] == '.jpg':
                    self.pics.append(f)
            # 序列化图片列表
            _serial = pickle.dumps(self.pics)
            _t = [(_serial,),]
            # hdate     integer
            # htime     integer
            # serialization            blob,
            self.sh.exec("insert into history(hdate,htime,serialization) values(date('now'),time('now','localtime'),?)", _t, mode='')
            r = self.sh.exec('select serialization from history order by htime desc', list(), result=True)
            for obj in r:
                print(pickle.loads(obj[0]))

            logging.info('[files]' + ';'.join(self.pics) + '[files]')

    def show_ratio_reset(self):
        self.ratio = 1.0

    def boxes_recovery(self):
        # 恢复初始boundingbox列表
        # print(len(self.boxes), len(self.originbox))
        self.boxes.clear()
        for _box in pickle.loads(self.src_boxes):
            self.boxes.append(_box)

    def boxes_delete(self, param=None):
        # 从boundingbox列表中删除指定的box或清空列表
        if param is None:
            self.boxes.clear()
        else:
            self.boxes.remove(param)

    def boxes_modify(self, newclass):
        self.boxes[len(self.boxes) - 1].setclass(newclass)

    def boxes_append(self, _box):
        self.boxes.append(_box)

    def dir_init(self):
        if isinstance(self.dir_path, str) and os.path.exists(self.dir_path) is True:
            self.warningdir = os.path.join(self.dir_path, 'warning')
            self.nochangeddir = os.path.join(self.dir_path, 'nochanged')
            self.changeddir = os.path.join(self.dir_path,  'changed')
            if os.path.exists(self.nochangeddir) is False:
                os.mkdir(self.nochangeddir)
            if os.path.exists(self.changeddir) is False:
                os.mkdir(self.changeddir)
            if os.path.exists(self.warningdir) is False:
                os.mkdir(self.warningdir)

    def clear_label(self):
        _file = self.getcurrentimagefile()
        print(type(_file))
        if _file is not None:
            for path in [os.path.join(x, _file.replace('jpg', 'txt')) for x in [self.warningdir, self.nochangeddir, self.changeddir]]:
                if os.path.exists(path) is True:
                    os.remove(path)

    def getcurrentstate(self):
        # 返回当前数据修改状态
        wheelcounter = 0
        if len(self.boxes) > 0:
            _new = set([n.getLableString() for n in self.boxes])
        else:
            _new = set([])
        # _origin = set([o.getLableString() + '\n' for o in self.src_boxes])
        if len(self.src_boxes) > 0:
            _origin = set([o.getLableString() for o in pickle.loads(self.src_boxes)])
        else:
            _origin = set([])

        if len(_new ^ _origin) == 0:
            # 集合成员一致 >>> 无修改
            return 1    # 无修改
        else:
            for box in _new:
                try:
                    if box.index('wheel') > -1:
                        wheelcounter += 1
                except:
                    pass
            # if wheelcounter != 2:
            #     return 2   # 有修改， 轴数异常
            return 3    # 有修改


    def writelable(self):
        # 写lable
        _state = self.getcurrentstate()
        _file = self.getcurrentimagefile()
        if isinstance(_file, str) is True:
            _file = _file.replace('jpg', 'txt')
        else:
            return
        dst_file = None
        if _state == 1:
            # 无修改
            dst_file = os.path.join(self.nochangeddir, _file)
            logging.info('[result]' + '未更改')
        elif _state == 2:
            dst_file = os.path.join(self.warningdir, _file)
            logging.info('[result]' + '轴数异常')
        elif _state == 3:
            dst_file = os.path.join(self.changeddir, _file)
            logging.info('[result]' + '有更改')

        if os.path.exists(dst_file) is True:
            os.remove(dst_file)
        else:
            with open(dst_file, 'w') as f:
                f.writelines([_box.getLableString() + '\n' for _box in self.boxes])
            self.update_db()

    def read_db(self):
        sql_getpics = '''
        select serialization from history order by id desc
        '''
        sql_getlastpic = '''
        select filename,rootpath from pics order by id desc
        '''

        r_getpics = self.sh.exec(sql_getpics, list(), result=True)
        r_lastpics = self.sh.exec(sql_getlastpic, list(), result=True)
        print('r_lastpics >>>', r_lastpics)
        print('r_getpics >>>', r_getpics)
        if len(r_getpics) != 0:
            # print(pickle.loads(r_getpics[0][0]))
            self.pics = pickle.loads(r_getpics[0][0])
        if len(r_lastpics) != 0:
            # print(r_lastpics[0])
            try:
                self.index = pickle.loads(r_getpics[0][0]).index(r_lastpics[0][0])
            except ValueError:
                self.index = -1
            self.dir_path = r_lastpics[0][1]
            self.ratio = 1.0
            self.readlable()
        if self.index > 0 and self.index != len(self.pics) - 1:
            return 1
        else:
            return 0

    def update_db(self):
        sql_update = '''
        insert into pics
        (opdate,optime,filename,kind,rootpath,laststate,oldlabel,newlabel)
        values
        (date('now'), time('now','localtime'),?,?,?,?,?,?);
        '''
        _filename = self.getcurrentimagefile()
        _lst = [(
            _filename,
            _filename.split('_')[0],
            self.dir_path,
            self.getcurrentstate(),
            pickle.dumps(self.src_boxes) if len(self.src_boxes)==0 else self.src_boxes,
            pickle.dumps(self.boxes)
        ),]
        # print('_lst >>> ', _lst)
        self.sh.exec(sql_update, _lst, mode='')
        # r = self.sh.exec('select * from pics order by optime', list(), result=True)
        # for l in r:
        #     print(l)

    def readlable(self):
        # 读取并建立、返回label列表
        sql_label = 'select oldlabel,newlabel from pics where filename=? order by id desc'
        query_param = [(self.getcurrentimagefile()),]
        _r = self.sh.exec(sql_label, query_param, result=True)
        if len(_r) > 0:
            self.boxes = pickle.loads(_r[0][1])
            self.src_boxes = _r[0][0]
        else:
            self.boxes.clear()
            _src_boxes = []
            _f = self.getcurrentimagefile()
            lablefile = ''
            if _f is not None:
                lablefile = os.path.join(
                    self.dir_path,
                    self.getcurrentimagefile().replace('jpg', 'txt'))
            if os.path.exists(lablefile) is True:
                try:
                    with open(lablefile, 'r') as f:
                        lines = f.read().split('\n')
                        for l in lines:
                            if l != '':
                                _p = l.split(' ')
                                x = box(
                                    _p[0],
                                    ((int(_p[4]), int(_p[5])),
                                     (int(_p[6]), int(_p[7]))),
                                    True,
                                    None)
                                self.boxes.append(x)
                                _src_boxes.append(x)
                        self.src_boxes = pickle.dumps(_src_boxes)
                except Exception as e:
                    self.boxes = list()
                    self.src_boxes = tuple()
                    print(e)
            else:
                self.boxes = list()
                self.src_boxes = tuple()

    def getcurrentimagefile(self, incl_path=False):
        # 提供当前jpg文件名（可含路径）
        print('当前图片序号： ', self.index)
        if self.index > -1 and self.index < len(self.pics):
            if incl_path is False:
                return self.pics[self.index]
            else:
                return os.path.join(self.dir_path, self.pics[self.index])
        else:
            return None

    def getpicratio(self, origin_img):
        # 返回图片缩放系数
        if self.ratio == 1.0:
            self.ratio = max(
                self.picsize[0]/origin_img.size[0],
                self.picsize[1]/origin_img.size[1])
        return self.ratio

    def getdrawratio(self, origin_img):
        # 从（1096,256）变换到原图尺寸的缩放系数
        # origin_size = 1096, 256
        _ratiox = self.outputsize[0] / origin_img.size[0]
        _ratioy = self.outputsize[1] / origin_img.size[1]
        self.zoomratio = _ratiox, _ratioy
        return _ratiox, _ratioy


    def setpicratio(self, newratio):
        # newratio list
        self.ratio = newratio

    def _next(self):
        # 返回下一张序号，并更新bbox
        if self.index + 1 <= len(self.pics):
            self.index += 1
            self.readlable()
            self.ratio = 1.0
            return self.index
        return None

    def _last(self):
        # 返回上一张序号，并更新bbox
        if self.index - 1 > -1:
            self.index -= 1
            self.readlable()
            self.ratio = 1.0
            return self.index
        return None

"""
UI 层
"""

def display(func):
    def _func(self, *args, **kw):
        func(self, *args, **kw)
        self._clear_canvas()
        self._show()
        self._draw()
        self.fileinfo_update()
        # self._logic.setoutputratio(self.origin_image.size, self.origin_image)

    return _func


class ui():
    def __init__(self, mode, param):
        if mode == 'QT':
            pass
        elif mode == 'TK':
            # 整合平台
            self.tkmaster = param
            self.window_size = (self.tkmaster.winfo_screenwidth(), self.tkmaster.winfo_screenheight())
            self.tkmaster.geometry('%dx%d' % self.window_size)
            # 2192,512
            self.showoffset = 0, 0
            self.canvas_ratio = 0.8
            self._logic = logic((self.window_size[0], self.window_size[1] * self.canvas_ratio))
            self.startX = 0
            self.startY = 0
            self.current_actived_menu = None
            self.origin_image = None  # 原图image对象
            self.currentshowresizedimage = None
            self.coords = []
            self.dir_path = None
            self.ratio = 1.0
            self.fetchobjs = None
            self._tkinit()
            tmp_r = self._logic.read_db()  # 有操作痕迹
            if tmp_r == 1:
                self._logic.dir_init()
                self._show()
                self._draw()
                self.fileinfo_update()
        else:
            pass

    def _tkinit(self):
        self.canvas = Canvas(
            self.tkmaster, 
            bg='pink',
            width=self.window_size[0], 
            height=self.window_size[1] * self.canvas_ratio)
        self.canvas.place(x=0, y=0)
        self.funcframe = Frame(
            self.tkmaster,
            width=self.window_size[0],
            height=self.window_size[1] * (1 - self.canvas_ratio)
        )
        self.funcframe.place(x=0, y=self.window_size[1] * self.canvas_ratio)
        Button(
            self.funcframe,
            text='上一张',
            width=10,
            height=1,
            command=self.cmd_pic_last
        ).place(x=1250, y=5)
        Button(
            self.funcframe,
            text='下一张',
            width=10,
            height=1,
            command=self.cmd_pic_next
        ).place(x=1250, y=40)
        _lb_root = 15, 0
        self._lb_status = Label(self.funcframe, text='欢迎使用！！')
        self._lb_status.place(x=_lb_root[0], y=_lb_root[1])
        self._lb_statistics = Label(self.funcframe, text='')
        self._lb_statistics.place(x=_lb_root[0], y=_lb_root[1] + 35)
        self._lb_help = Label(
            self.funcframe,
            text='[Ctrl+O] : 打开目录    [左键双击]：画点    [右键单击]：功能菜单    [Ctrl+左键拖动]：移动图框    [Home]：适应屏幕    [←]：上一张    [→]：下一张')
        self._lb_help.place(x=_lb_root[0], y=_lb_root[1] + 70)

        self._show(first=True)
        self.tkmaster.bind('<Key>', self.event_press_key)
        self.tkmaster.bind('<Control-o>', self.cmd_open_dir)

    def update_stat(self):
        sql_stat = '''
        select kind,laststate,count(*)
        from (select id,kind,laststate from pics where opdate=date('now') group by filename order by optime desc)
        group by kind,laststate
        '''
        self._r = self._logic.sh.exec(sql_stat, list(), result=True)
        _l1 = _l2 = _l3 = 0
        for l in self._r:
            if l[1] == 1:
                _l1 += l[2]
            if l[1] == 2:
                _l2 += l[2]
            if l[1] == 3:
                _l3 += l[2]
        str_stat = '今日共处理图片（%d）张，其中未修改（%d）张、常规修改（%d）、轴数异常（%d）张。' % (_l1+_l2+_l3,_l1,_l3,_l2)
        self._lb_statistics.config(text=str_stat)
        self._lb_statistics.bind('<Button-1>', self._create_popwin)

    def recovery_init(self):
        _dt =  self._logic.sh.exec('select * from history', None, result=True)
        if len(_dt) != 0:
            print(pickle.loads(_dt[0]))

    def event_press_key(self, event):
        # print('keychar >>> ', event.keycode)
        # 113 next
        print(event.keycode)
        if event.keycode == (37 if os.name == 'nt' else 113):  # next
            self.cmd_pic_last()
        if event.keycode == (39 if os.name == 'nt' else 114):  # last
            self.cmd_pic_next()
        if event.keycode == (33 if os.name == 'nt' else 112):  # pageup
            self.cmd_pic_zoomin()
        if event.keycode == (34 if os.name == 'nt' else 117):  # pagedown
            self.cmd_pic_zoomout()
        # if event.keycode == 39:  # opendir
        #     self.cmd_open_dir()
        if event.keycode == 110 or event.keycode == 43:
            self.cmd_show_middle()

    @display
    def cmd_show_middle(self):
        self._logic.show_ratio_reset()
        self.showoffset = self._logic.getmiddlexy(self.currentshowresizedimage)
    
    def _clear_canvas(self):
        for item in self.canvas.find_all():
            self.canvas.delete(item)

    def bbox_move(self, offX, offY, specify=None):
        if specify is None:
            _items = self.canvas.find_all()
            for item in _items:
                self.canvas.move(item, offX, offY)
        else:
            self.canvas.move(specify, offX, offY)
    
    @display
    def cmd_recovery(self):
        # bbox还原
        self._boxes_recovery()

    @display
    def cmd_clear(self):
        # bbox清除
        self._boxes_delete()

    @display
    def cmd_undo(self):
        # 撤销绘图
        coords = self._logic.getcoords()
        if len(coords) == 1:
            self._logic.clear_coords()
        else:
            boxes = self._logic.getboxes()
            box = boxes[len(boxes) - 1]
            xy = box.getrectangle()
            self._logic.boxes_delete(box)
            self._logic.addcoords(xy[0], fast=True)

    def cmd_analyze(self):
        # analyze
        _top = Toplevel()
        _top.title = '统计结果'
        msg = Message(_top, text=self.get_analyze_result())
        msg.pack()

        button = Button(_top, text="确认", command=_top.destroy)
        button.pack()

    def cmd_box_delete(self):
        self._logic.clear_coords()
        _boxes = self._logic.getboxes()
        for obj in self.fetchobjs:
            if self.canvas.type(obj) != 'image':
                self.canvas.delete(obj)
                for box in _boxes:
                    if box.getcanvasid() == obj:
                        self._logic.boxes_delete(box)
                        break


    def _create_point(self, x, y, r, **kwargs):
        #   画圆 point
        # self._create_point(500,300,2,fill='red')
        return self.canvas.create_oval(x - r, y - r, x + r, y + r, **kwargs)

    def event_next_pic(self, event):
        self.cmd_pic_next()

    @display
    def cmd_pic_next(self):
        self._clear_menu()
        self._logic.writelable()
        self._logic._next()
        self.update_stat()
        self.fileinfo_update()


    def event_last_pic(self, event):
        self.cmd_pic_last()

    @display
    def cmd_pic_last(self):
        self._clear_menu()
        self._logic.writelable()
        self._logic._last()
        self.update_stat()
        self.fileinfo_update()

    def fileinfo_update(self):
        _currentfile = self._logic.getcurrentimagefile(incl_path=False)
        print('_currentfile >>> ', type(_currentfile))
        print('*'*100)
        if isinstance(_currentfile, str) is True and os.path.exists(os.path.join('' if self.dir_path is None else self.dir_path, _currentfile)) is True:
            fileinfo = '(%d/%d)' % (self._logic.getfileindex(_currentfile) + 1, self._logic.getfilecount()) + _currentfile
        # self.tkmaster.title(newtitle)
            self._lb_status.config(text=fileinfo)
            logging.info('[tofile]' + fileinfo + '[tofile]')

    def _clear_menu(self):
        # 清空menu
        if self.current_actived_menu is not None:
            self.current_actived_menu.unpost()
    def _show(self, first=False):
        if first is True:
            self.origin_image = Image.open('bg.jpg')
        else:
            _currentfile = self._logic.getcurrentimagefile(incl_path=True)
            if _currentfile is not None and os.path.exists(_currentfile) is True:
                self.origin_image = Image.open(_currentfile)
            self.canvas.bind(
                '<Double-Button-1>',
                self.event_dbclick_b1
            )
            self.canvas.bind(
                '<Button-1>',
                self.event_left_click
            )  # 左键
            self.canvas.bind(
                '<Button-3>',
                self.event_right_click
            )  # 右键
            # self.canvas.bind(
            #     '<B1-Motion>',
            #     self.event_b1_motion
            # )  # 拖动
            self.canvas.bind(
                '<ButtonRelease-1>',
                self.event_b1_release
            )
            # 滚轮仅支持windows系统和mac系统
            self.canvas.bind(
                '<MouseWheel>',
                self.event_mouse_wheel
            )
            self.canvas.bind(
                '<Control-B1-Motion>',
                self.event_move
            )

        if self.origin_image is not None:
            self.ratio = self._logic.getpicratio(self.origin_image)
            print('缩放倍数： >>> ', self.ratio)
            self.currentshowresizedimage = self.origin_image.resize(
                (int(float(self.origin_image.size[0]) * self.ratio),
                 int(float(self.origin_image.size[1]) * self.ratio)),
                Image.ANTIALIAS)
            # print(self._resized_image.size)
            self._photo = ImageTk.PhotoImage(self.currentshowresizedimage)
            if self.showoffset[0] == 0 and self.showoffset[1] == 0:
                self.showoffset = self._logic.getmiddlexy(self.currentshowresizedimage)
            # self._create_popwin(str(self.showoffset[0]) + ' | ' + str(self.showoffset[1]))
            _img = self.canvas.create_image(
                self.showoffset[0],
                self.showoffset[1], 
                anchor='nw', 
                image=self._photo)
            for o in self.canvas.find_all():
                if self.canvas.type(o) == 'image':
                    self.canvas.coords(o, self.showoffset)
            self._logic.clear_label()

    def _create_popwin(self, event):
        if self._r is not None:
            top = Toplevel()
            top.title("统计")
            #
            # tr = Treeview(top, columns=('kind','state'))
            tr = Treeview(top, show='headings', columns=('kind', 'state', 'count'))
            # ysb = Scrollbar(tr, orient='vertical', command=tr.yview)
            # tr.configure(yscroll=ysb.set)
            # ysb.pack()
            tr.column('kind', width = 100, anchor ='center')
            tr.column('state', width = 100, anchor ='center')
            tr.column('count', width = 100, anchor ='center')
            tr.heading('kind', text='车型')
            tr.heading('state', text='状态')
            tr.heading('count', text='总量')

            for l in self._r:
                _state = ''
                if l[1] == 1:
                    _state = '未修改'
                elif l[1] == 2:
                    _state = '轴数异常'
                elif l[1] == 3:
                    _state = '已修改'

                tr.insert('',0, text='', values=(l[0], _state, l[2]))
                # tr.insert('',0,values=(l[0], _state, l[2]))

            tr.pack()
            button = Button(top, text="退出", command=top.destroy)
            button.pack()
            top.config(height=top.bbox(tr)[3]+100)

    def event_combo_test(self, event):
        print('ok')

    def event_b1_release(self, event):
        c = event.widget
        item = c.find_withtag('current')
        if c.type(item) == 'image':
            self.showoffset = c.coords(item)
            print('当前显示坐标原点位于： (%d, %d)' % (self.showoffset[0],self.showoffset[1]))
             
    def event_mouse_wheel(self, event):
        if event.delta > 0:
            self.event_pic_zoomin(event)
        elif event.delta < 0:
            self.event_pic_zoomout(event)

    def event_left_click(self, event):
        # 
        self.startX = event.x
        self.startY = event.y
        self._fetch_obj(event)

    def _fetch_obj(self, event):
        c = event.widget
        x = c.canvasx(event.x)
        y = c.canvasy(event.y)
        self.fetchobjs = None
        objs = []
        xyxy = None
        item = c.find_withtag('current')
        # print('_ self.showoffset >>> (%d,%d)' % (self.showoffset))
        if c.type(item) == 'image':
            for i in c.find_all():
                xyxy = c.bbox(i)
                if x >= xyxy[0] and x <= xyxy[2] and y >= xyxy[1] and y <= xyxy[3]:
                    objs.append(i)
            print('all >>>(%d), fetch >>>(%d)' % (len(c.find_all()), len(objs)))
            # for o in objs:
                # print(c.type(o))
            self.fetchobjs = objs

    def _get_relcoord(self, coords):
        dx = coords[0] - self.showoffset[0]
        dy = coords[1] - self.showoffset[1]
        if self.showoffset[0] < 0:
            dx = abs(self.showoffset[0]) + coords[0]
        if self.showoffset[1] < 0:
            dy = abs(self.showoffset[1]) + coords[1]
        return (dx, dy)

    def _get_imagecoord(self, event):
        c = event.widget
        x = c.canvasx(event.x)
        y = c.canvasy(event.y)
        dX = 0
        dY = 0
        xyxy = None
        item = c.find_withtag('current')
        if c.type(item) == 'image':
            xyxy = c.bbox(item)
            dX = x - xyxy[0]
            dY = y - xyxy[1]
            if xyxy[0] < 0:
                dX = abs(xyxy[0]) + x
            if xyxy[1] < 0:
                dY = abs(xyxy[1]) + y
            # print(dX, dY)
            return (dX, dY)
        else:
            return None

    def event_dbclick_b1(self, event):
        self._logic.addcoords(self._get_imagecoord(event))   # 将坐标加入列表
        c = event.widget
        item = c.find_withtag('current')
        self.showoffset = c.coords(item)
        # print('双击时 >>>', self.showoffset)
        self._clear_canvas()
        self._show()
        self._draw()
        if len(self._logic.getcoords()) == 0:
            self.event_pop_class_menu(event)

    def event_right_click(self, event):
        self._clear_menu()
        popmenu = Menu(self.canvas, tearoff=0)
        self.current_actived_menu = popmenu
        self._fetch_obj(event)
        if self.fetchobjs is not None:
            if len(self.fetchobjs) == 1:
                popmenu.add_command(label='还原', command=self.cmd_recovery)
                popmenu.add_command(label='清除', command=self.cmd_clear)
                popmenu.add_command(label='撤销', command=self.cmd_undo)
            elif len(self.fetchobjs) > 1:
                popmenu.add_command(label='删除', command=self.cmd_box_delete)
                boxeditmenu = Menu(popmenu, tearoff=0)
                boxeditmenu.add_command(label='车门', command=self.cmd_box_edit_door)
                boxeditmenu.add_command(label='车窗', command=self.cmd_box_edit_window)
                boxeditmenu.add_command(label='车轮', command=self.cmd_box_edit_wheel)
                boxeditmenu.add_command(label='异物', command=self.cmd_box_edit_spillobj)
                popmenu.add_cascade(label='修改类型', menu=boxeditmenu)
        popmenu.post(event.x_root, event.y_root)

    def cmd_box_edit_door(self):
        if self.fetchobjs is not None:
            for obj in self.fetchobjs:
                if self.canvas.type(obj) == 'rectangle':
                    self.canvas.itemconfig(obj, outline=self._logic.getcolors('door'))
                    for box in self._logic.getboxes():
                        if box.getcanvasid() == obj:
                            box.setclass('door')
                            
    def cmd_box_edit_window(self):
        if self.fetchobjs is not None:
            for obj in self.fetchobjs:
                if self.canvas.type(obj) == 'rectangle':
                    self.canvas.itemconfig(obj, outline=self._logic.getcolors('window'))
                    for box in self._logic.getboxes():
                        if box.getcanvasid() == obj:
                            box.setclass('window')
                            
    def cmd_box_edit_wheel(self):
        if self.fetchobjs is not None:
            for obj in self.fetchobjs:
                if self.canvas.type(obj) == 'rectangle':
                    self.canvas.itemconfig(obj, outline=self._logic.getcolors('wheel'))
                    for box in self._logic.getboxes():
                        if box.getcanvasid() == obj:
                            box.setclass('wheel')

    def cmd_box_edit_spillobj(self):
        if self.fetchobjs is not None:
            for obj in self.fetchobjs:
                if self.canvas.type(obj) == 'rectangle':
                    self.canvas.itemconfig(obj, outline=self._logic.getcolors('spillobj'))
                    for box in self._logic.getboxes():
                        if box.getcanvasid() == obj:
                            box.setclass('spillobj')



    def event_move(self, event):
        offx = event.x - self.startX
        offy = event.y - self.startY
        if self.fetchobjs is not None:
            if len(self.fetchobjs) == 1:
                # print('sum >>> (%d)' % (len(self.fetchobjs)))
                self.bbox_move(offx, offy)
            elif len(self.fetchobjs) > 1:
                for obj in self.fetchobjs:
                    if self.canvas.type(obj) != 'image':
                        self.bbox_move(offx, offy, specify=obj)
                    for box in self._logic.getboxes():
                        if box.getcanvasid() == obj:
                            _tuple = self.canvas.bbox(obj)
                            p1 = self._logic.coord_screen2originimage(self._get_relcoord((_tuple[0], _tuple[1])))
                            p2 = self._logic.coord_screen2originimage(self._get_relcoord((_tuple[2], _tuple[3])))
                            box.setrectangle((p1, p2))
                            # print(p1, p2)
        self.startX = event.x
        self.startY = event.y

    @display
    def cmd_pic_zoomin(self, event=None):
    # def event_pic_zoomin(self, event):
        # 放大 步进0.5x
        self._logic.setpicratio(self.ratio / 0.5)

    @display
    def cmd_pic_zoomout(self):
    # def event_pic_zoomout(self, event):
        # 缩小 步进0.5x
        self._logic.setpicratio(self.ratio * 0.5)

    def _clear_canvas(self):
        _items = self.canvas.find_all()
        for item in _items:
            self.canvas.delete(item)

    
    def _draw(self):
        # 绘图
        _coords = self._logic.getcoords()
        _boxes = self._logic.getboxes()
        # self.origin_ratio = self._logic.getdrawratio(self.origin_image)  # 还原1096,256
        self.origin_ratio = 1, 1
        print(self.ratio)
        for _box in _boxes:
            # print(box.getrectangle())
            _id = self.canvas.create_rectangle(
                (
                    (
                        _box.getrectangle()[0][0] / self.origin_ratio[0] * self.ratio + self.showoffset[0],
                        _box.getrectangle()[0][1] / self.origin_ratio[1] * self.ratio + self.showoffset[1]
                        ), 
                    (
                        _box.getrectangle()[1][0] / self.origin_ratio[0] * self.ratio + self.showoffset[0],
                        _box.getrectangle()[1][1] / self.origin_ratio[1] * self.ratio + self.showoffset[1]
                        )
                    ),
                width=2,
                outline=self._logic.getcolors(_box.getclass()))
            _box.setcanvasid(_id)
        if len(_coords) % 2 == 1:
            # 坐标落单画点
            self._create_point(
                _coords[0][0]/self.origin_ratio[0]*self.ratio+self.showoffset[0],
                _coords[0][1]/self.origin_ratio[1]*self.ratio+self.showoffset[1],
                2,
                fill=self._logic.getcolors('point'))

    def event_pop_class_menu(self, event):
        # 分类菜单
        self._clear_menu()
        popmenu = Menu(self.canvas, tearoff=0)
        self.current_actived_menu = popmenu
        popmenu.add_command(label='车门', command=self.cmd_type_door)
        popmenu.add_command(label='车窗', command=self.cmd_type_window)
        popmenu.add_command(label='车轮', command=self.cmd_type_wheel)
        popmenu.add_command(label='异物', command=self.cmd_type_spillobj)
        popmenu.post(event.x_root, event.y_root)

    @display
    def cmd_type_spillobj(self):
        self._logic.boxes_modify('spillobj')

    @display
    def cmd_type_wheel(self):
        self._logic.boxes_modify('wheel')

    @display
    def cmd_type_door(self):
        self._logic.boxes_modify('door')

    @display
    def cmd_type_window(self):
        self._logic.boxes_modify('window')

    @display
    def cmd_open_dir(self, event=None):
    # def event_open_dir(self, event):
        self.dir_path = filedialog.askdirectory(
            initialdir=os.path.join(sys.path[0]),
            title='请选择图片文件夹')
        self._logic.getfiles(self.dir_path)
        self._logic._next()
        self.fileinfo_update()
        self._logic.dir_init()

def main():
    logging.info('[start]' + '程序启动' + '[start]')
    _m = Tk()
    _m.title('深度学习图像素材处理工具')
    # _m.geometry('1096x512')
    # _m.maxsize(1096, 300)
    # _m.minsize(1096, 300)
    u = ui('TK', _m)
    _m.mainloop()


if __name__ == '__main__':
    main()
