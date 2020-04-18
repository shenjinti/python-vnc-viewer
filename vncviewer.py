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
import struct

from sdl2 import render, rect, surface


class Option:
    def __init__(self):
        self.host = '127.0.0.1'
        self.port = 5900
        self.width = 1280
        self.height = 1024
        self.encoding = [
            rfb.RAW_ENCODING,
            rfb.HEXTILE_ENCODING,
            rfb.COPY_RECTANGLE_ENCODING,
            rfb.CORRE_ENCODING,
            rfb.RRE_ENCODING,
        ]

    def remote_url(self):
        return 'vnc://%s:%s' % (self.host, self.port)


EV_RESIZE = 0
EV_UPDATE_RECT = 1
EV_COPY_RECT = 2
EV_FILL_RECT = 3


class VNCClient(rfb.RFBClient):
    def __init__(self, loop, renderer, option):
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

        self.setEncodings(self.option.encoding)
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
        pitch = int(port.w * self.bpp / 8)
        self._events.append((EV_UPDATE_RECT, (port, data, pitch)))

    def copyRectangle(self, srcx, srcy, x, y, width, height):
        """used for copyrect encoding. copy the given rectangle
           (src, srxy, width, height) to the target coords (x,y)"""
        #print("copyRectangle", srcx, srcy, x, y, width, height)
        self._events.append((EV_COPY_RECT, (srcx, srcy, x, y, width, height)))

    def fillRectangle(self, x, y, width, height, color):
        """fill rectangle with one color"""
        #~ remoteframebuffer.CopyRect(srcx, srcy, x, y, width, height)
        #print('==========fillRectangle', x, y, width, height, color)

        port = (x, y, width, height)
        r, g, b, a = struct.unpack("!BBBB", color)
        self._events.append((EV_FILL_RECT, (port, sdl2.ext.Color(r, g, b, a))))

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
        evs = self._events
        self._events = []
        return evs


def load_gui(option):
    sdl2.ext.init()
    window = sdl2.ext.Window("VNC Viewer [%s]" % (option.remote_url()), size=(
        option.width, option.height))
    window.show()
    return window


async def run_gui(window, renderer, client):
    running = True
    in_present = False
    buttons = 0

    renderer.clear()
    sdl2.SDL_ShowCursor(0)

    factory = sdl2.ext.SpriteFactory(sdl2.ext.TEXTURE, renderer=renderer)
    pformat = sdl2.pixels.SDL_AllocFormat(sdl2.pixels.SDL_PIXELFORMAT_RGB888)

    while running:
        evs = client.nextEvents()
        need_update = len(evs) > 0
        for ev in evs:
            if ev[0] == EV_RESIZE:
                pass
            elif ev[0] == EV_UPDATE_RECT:
                port, buf, pitch = ev[1]
                texture = factory.create_texture_sprite(
                    renderer, (port.w, port.h),
                    pformat=sdl2.pixels.SDL_PIXELFORMAT_RGB888,
                    access=render.SDL_TEXTUREACCESS_STREAMING)
                tport = sdl2.SDL_Rect()
                tport.x = 0
                tport.y = 0
                tport.w = port.w
                tport.h = port.h
                render.SDL_UpdateTexture(texture.texture, tport, buf, pitch)
                renderer.copy(texture, (0, 0, port.w, port.h),
                              (port.x, port.y, port.w, port.h))
            elif ev[0] == EV_COPY_RECT:
                srcx, srcy, x, y, width, height = ev[1]
                texture = factory.from_surface(window.get_surface())
                renderer.copy(texture, (srcx, srcy, width,
                                        height), (x, y, width, height))
            elif ev[0] == EV_FILL_RECT:
                port, color = ev[1]
                pcolor = sdl2.pixels.SDL_MapRGBA(pformat, color.r, color.g, color.b, color.a)
                renderer.fill(port, pcolor)

        if need_update:
            in_present = True
            renderer.present()

        events = sdl2.ext.get_events()
        for event in events:
            if event.type == sdl2.SDL_QUIT:
                running = False
                break

            if in_present is False:
                continue

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

    window = load_gui(option)

    loop = asyncio.get_running_loop()

    flags = sdl2.render.SDL_RENDERER_SOFTWARE
    renderer = sdl2.ext.Renderer(window, flags=flags)

    client = VNCClient(loop, renderer, option)
    transport, protocol = await loop.create_connection(
        lambda: client,
        option.host, option.port)

    await run_gui(window, renderer, client)


if __name__ == '__main__':
    asyncio.run(main())
