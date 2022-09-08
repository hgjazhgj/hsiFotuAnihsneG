import json
import os
import random
import time
import traceback

import cv2
import ctypes
import numpy
import win32api
import win32con
import win32gui
import win32ui

ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))

class Window:
    def __init__(self, name, cls=None):
        self.hWnd = win32gui.FindWindow(cls, name)
        assert self.hWnd
        self.hWndDC = win32gui.GetDC(self.hWnd)
        self.hMfcDc = win32ui.CreateDCFromHandle(self.hWndDC)
        self.hMemDc = self.hMfcDc.CreateCompatibleDC()

    def capture(self):
        self.width, self.height = win32gui.GetClientRect(self.hWnd)[2:]
        hBmp = win32ui.CreateBitmap()
        hBmp.CreateCompatibleBitmap(self.hMfcDc, self.width, self.height)
        self.hMemDc.SelectObject(hBmp)
        self.hMemDc.BitBlt((0, 0), (self.width, self.height), self.hMfcDc, (0, 0), win32con.SRCCOPY)
        result = numpy.frombuffer(hBmp.GetBitmapBits(True), dtype=numpy.uint8).reshape(self.height, self.width, 4)
        win32gui.DeleteObject(hBmp.GetHandle())
        return result

    def click(self, hold=0):
        win32api.PostMessage(self.hWnd, win32con.WM_LBUTTONDOWN, 0, 0)
        time.sleep(hold)
        win32api.PostMessage(self.hWnd, win32con.WM_LBUTTONUP, 0, 0)

    def __del__(self):
        self.hMemDc.DeleteDC()
        self.hMfcDc.DeleteDC()
        win32gui.ReleaseDC(self.hWnd, self.hWndDC)


READY = cv2.imread('image/ready.png')
FRONT = cv2.imread('image/front.png')
BACK = cv2.imread('image/back.png')
CUR = cv2.imread('image/cur.png')
READYMASK = cv2.imread('image/readymask.png') >> 7
FRONTMASK = cv2.imread('image/frontmask.png') >> 7
BACKMASK = cv2.imread('image/backmask.png') >> 7
CURMASK = cv2.imread('image/curmask.png') >> 7


class Check:
    @classmethod
    def setup(cls, capture, readyRect, posRect):
        cls.capture = capture
        cls.readySlice = (slice(readyRect[1], readyRect[3]), slice(readyRect[0], readyRect[2]))
        cls.posSlice = (slice(posRect[1], posRect[3]), slice(posRect[0], posRect[2]))
    
    def __init__(self, im=None):
        try:
            im = self.capture() if im is None else im
            size = (1280, round(im.shape[0]*1280//im.shape[1])) \
                if im.shape[0]*16 > im.shape[1]*9 else (round(im.shape[1]*720/im.shape[0]), 720)
            self.im = cv2.resize(im, size, interpolation=cv2.INTER_CUBIC)
            self.im = numpy.vstack([self.im[:360, size[0]//2-640:size[0]//2+640],self.im[-360:, -1280:]])
        except:
            self.im = numpy.zeros((720, 1280, 4), dtype=numpy.uint8)

    def wrapAlpha(self, im):
        im, alpha = im[..., :3]>>4, im[..., 3]>>4
        for i in range(3):
            im[..., i] *= alpha
        return im

    def isReady(self):
        return .2 > cv2.minMaxLoc(cv2.matchTemplate(
            self.wrapAlpha(self.im[self.readySlice]), READY, cv2.TM_SQDIFF_NORMED, mask=READYMASK))[0]

    def getPos(self):
        img = self.wrapAlpha(self.im[self.posSlice])
        loc = cv2.minMaxLoc(cv2.matchTemplate(img, CUR, cv2.TM_SQDIFF_NORMED, mask=CURMASK))
        if loc[0] > .2:
            return None
        return (loc[2][0],
            cv2.minMaxLoc(cv2.matchTemplate(img, FRONT, cv2.TM_SQDIFF_NORMED, mask=FRONTMASK))[2][0],
            cv2.minMaxLoc(cv2.matchTemplate(img, BACK, cv2.TM_SQDIFF_NORMED, mask=BACKMASK))[2][0])

    def save(self, name=None):
        cv2.imwrite(time.strftime('capture_%Y-%m-%d_%H.%M.%S.png') if name is None else name, self.im)

    def show(self):
        cv2.imshow('capture', self.wrapAlpha(cv2.resize(self.im, (640, 360))))
        cv2.waitKey(0)
        cv2.destroyAllWindows()


if __name__ == '__main__':
    try:
        print('GenshinAutoFish v2.5.0')

        with open('config.json', 'r', encoding='utf-8') as f:
            config = json.load(f)
        window = Window(config['title'], 'UnityWndClass')
        Check.setup(window.capture, config['readyRect'], config['posRect'])
        count = 0
        print('initialized', hex(window.hWnd), win32gui.GetWindowPlacement(window.hWnd))

        while True:
            lastCapture = 0
            if config['startKey']:
                while win32api.GetKeyState(config['startKey']) >= 0:
                    time.sleep(.05)
                    if time.time()-lastCapture > 1 and config['captureKey'] and win32api.GetKeyState(config['captureKey']) < 0:
                        Check().save()
                        print('captured')
                        lastCapture = time.time()
                    if config['showKey'] and win32api.GetKeyState(config['showKey']) < 0:
                        Check().show()
            print('wait')

            while win32gui.GetForegroundWindow() != window.hWnd or not Check().isReady():
                time.sleep(.05)
                assert win32gui.IsWindow(window.hWnd)
            print('ready')

            time.sleep(.2 + random.random()*.9*config['clumsyMode'])
            window.click(.8)
            print('go')

            while True:
                pos = Check().getPos()
                if pos is None:
                    break
                cur, front, back = pos

                buf = list(f'[{window.width:8}x{window.height:<9}{window.width:9}x{window.height:<8}]')
                buf[front//10+2: back//10+5] = f' <{"":{back//10-front//10-1}}> '
                buf[cur//10+2: cur//10+5] = f'{"<"if buf[cur//10+2]=="<" else " "}|{">"if buf[cur//10+4]==">" else " "}'
                print(''.join(buf), end='\r')

                if cur+10 < (front+back)//2:
                    window.click(.08 + random.random()*.2*config['clumsyMode'])
                else:
                    time.sleep(random.random()*.2*config['clumsyMode'])

            print(' '*38, end='\r')
            count += 1
            print('next', count)

    except KeyboardInterrupt:
        pass
    except BaseException:
        traceback.print_exc()
        os.system('pause')
