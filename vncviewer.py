#!/usr/bin/env python
"""
Python VNC Viewer
PyGame version
(C) 2003 <cliechti@gmx.net>

MIT License
"""
import rfb
import sdl2
import sdl2.ext
import time
import asyncio
import ctypes

from sdl2 import render, rect, surface


class Option:
    def __init__(self):
        self.host = '127.0.0.1'
        self.port = 5900
        self.width = 1280
        self.height = 1024

    def remote_url(self):
        return 'vnc://%s:%s' % (self.host, self.port)


EV_RESIZE = 0
EV_UPDATE_RECT = 1
EV_COPY_RECT = 1


class VNCClient(rfb.RFBClient):
    def __init__(self, loop, option, renderer):
        rfb.RFBClient.__init__(self, loop)
        self.loop = loop
        self.option = option
        self.renderer = renderer
        self._events = []
        self._frames = []

    def vncConnectionMade(self):
        print("Screen format: depth=%d bytes_per_pixel=%r width=%d height=%d" %
              (self.depth, self.bpp, self.width, self.height))
        print("Desktop name: %r" % self.name)
        encoding = [rfb.RAW_ENCODING,
                    rfb.COPY_RECTANGLE_ENCODING,
                    rfb.HEXTILE_ENCODING,
                    rfb.CORRE_ENCODING,
                    rfb.RRE_ENCODING
                    ]

        self.setEncodings(encoding)
        self.framebufferUpdateRequest()

        self._events.append((EV_RESIZE, (self.width, self.height)))

    def updateRectangle(self, x, y, width, height, data):
        """new bitmap data. data is a string in the pixel format set
           up earlier."""
        port = rect.SDL_Rect()
        port.x = x
        port.y = y
        port.w = width
        port.h = height
        #self._frames.append()
        self._events.append((EV_UPDATE_RECT, (port, data, int(port.w * self.bpp / 8))))



    def copyRectangle(self, srcx, srcy, x, y, width, height):
        """used for copyrect encoding. copy the given rectangle
           (src, srxy, width, height) to the target coords (x,y)"""
        #print("copyRectangle", srcx, srcy, x, y, width, height)
        self._events.append((EV_COPY_RECT, (srcx, srcy, x, y, width, height)))
    def fillRectangle(self, x, y, width, height, color):
        """fill rectangle with one color"""
        #~ remoteframebuffer.CopyRect(srcx, srcy, x, y, width, height)
        print('fillRectangle', x, y, width, height, color)

    def commitUpdate(self, rectangles=None):
        """called after a series of updateRectangle(), copyRectangle()
           or fillRectangle() are finished.
           typicaly, here is the place to request the next screen 
           update with FramebufferUpdateRequest(incremental=1).
           argument is a list of tuples (x,y,w,h) with the updated
           rectangles."""
        self.framebufferUpdateRequest(incremental=1)

    def nextEvents(self):
        if len(self._events) <= 0:
            return []
        evs = self._events[::]
        self._events = []
        return evs


def load_gui(option):
    sdl2.ext.init()
    window = sdl2.ext.Window("VNC Viewer [%s]" % (option.remote_url()), size=(
        option.width, option.height))
    window.show()
    sdl2.SDL_ShowCursor(0)
    renderer = render.SDL_CreateRenderer(window.window, -1, 0)
    render.SDL_RenderClear(renderer)
    render.SDL_RenderPresent(renderer)

    return window, renderer


async def run_gui(window, renderer, client):
    running = True
    texture = None
    vport = rect.SDL_Rect()
    buttons = 0

    while running:
        evs = client.nextEvents()
        need_update = len(evs) > 0
        for ev in evs:
            if ev[0] == EV_RESIZE:
                texture = render.SDL_CreateTexture(renderer,
                                                   sdl2.pixels.SDL_PIXELFORMAT_RGB888,
                                                   render.SDL_TEXTUREACCESS_STREAMING,
                                                   ev[1][0], ev[1][1])
                vport.x = 0
                vport.y = 0
                vport.w, vport.h = ev[1]
            elif ev[0] == EV_UPDATE_RECT and texture is not None:
                port, buf, pitch = ev[1]
                render.SDL_UpdateTexture(texture, port, buf, pitch)
            elif ev[0] == EV_COPY_RECT and texture is not None:
                srcx, srcy, x, y, width, height = ev[1]

        if need_update:
            render.SDL_RenderCopy(renderer, texture, vport, vport)
            render.SDL_RenderPresent(renderer)

        events = sdl2.ext.get_events()
        for event in events:
            if event.type == sdl2.SDL_QUIT:
                running = False
                break

            if texture is None:
                break

            if event.type == sdl2.SDL_MOUSEMOTION:
                x = event.motion.x
                y = event.motion.y
                client.pointerEvent(x, y, buttons)
            if event.type == sdl2.SDL_MOUSEBUTTONDOWN:
                e = event.button

                if e.button == 1:
                    buttons |= 1
                elif e.button == 2:
                    buttons |= 2
                elif e.button == 3:
                    buttons |= 4
                elif e.button == 4:
                    buttons |= 8
                elif e.button == 5:
                    buttons |= 16

                client.pointerEvent(e.x, e.y, buttons)
            if event.type == sdl2.SDL_MOUSEBUTTONUP:
                e = event.button

                if e.button == 1:
                    buttons &= ~1
                elif e.button == 2:
                    buttons &= ~2
                elif e.button == 3:
                    buttons &= ~4
                elif e.button == 4:
                    buttons &= ~8
                elif e.button == 5:
                    buttons &= ~16

                client.pointerEvent(e.x, e.y, buttons)

        await asyncio.sleep(0.01)


async def main():
    option = Option()

    window, renderer = load_gui(option)

    loop = asyncio.get_running_loop()
    client = VNCClient(loop, option, renderer)
    transport, protocol = await loop.create_connection(
        lambda: client,
        '127.0.0.1', 5900)

    await run_gui(window, renderer, client)


if __name__ == '__main__':
    asyncio.run(main())
