 
import random
import time
import threading

import mido
import numpy as np
import os; os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"
import pygame

import OpenGL.GL as gl
import OpenGL.GL.shaders as shaders
import OpenGL.GLU as glu
import OpenGL.GLUT as glut

#import music

#init metronome
pygame.init()
pygame.mixer.init()
tick = pygame.mixer.Sound("tick.wav")
tick.set_volume(0.25)
#tick.play()


KEY_C       = 0
KEY_D       = 1
KEY_E       = 2
KEY_B_FLAT  = 3
KEY_G_FLAT  = 4
KEY_E_FLAT  = 5

KEY_NAMES = {
    KEY_C:      "C",
    KEY_D:      "D",
    KEY_E:      "E",
    KEY_B_FLAT:      "Bb",
    KEY_E_FLAT:      "Eb",
    KEY_G_FLAT:      "Gb",
}

SCALE_MAJ           =  0
SCALE_MIN_MLD       =  1
SCALE_MIN_HRM       =  2
SCALE_DOM7_SOLID    =  3
SCALE_DOM7_BROKEN   =  4
SCALE_DIM7_SOLID    =  5
SCALE_DIM7_BROKEN   =  6
SCALE_DOM7_ARP      =  7
SCALE_DIM7_ARP      =  8
SCALE_MIN_TONIC_4   =  9
SCALE_MAJ_TONIC_4   = 10
SCALE_ARP_MIN       = 11
SCALE_ARP_MAJ       = 12
SCALE_FORMULA_MAJ   = 13
SCALE_FORMULA_MIN   = 14
SCALE_CHROMATIC     = 15

ARPEGGIO_SPEED = 60
TONIC_4_SPEED  = 75

BPM_TARGETS = {
    SCALE_MAJ:          88,
    SCALE_MIN_MLD:      88,
    SCALE_MIN_HRM:      88,
    SCALE_DOM7_SOLID:  100,
    SCALE_DOM7_BROKEN:  80,
    SCALE_DIM7_SOLID:  100,
    SCALE_DIM7_BROKEN:  80,
    SCALE_DOM7_ARP:     65,
    SCALE_DIM7_ARP:     65,
    SCALE_MAJ_TONIC_4:  TONIC_4_SPEED,
    SCALE_MIN_TONIC_4:  TONIC_4_SPEED,
    SCALE_ARP_MIN:      ARPEGGIO_SPEED,
    SCALE_ARP_MAJ:      ARPEGGIO_SPEED,
    SCALE_FORMULA_MAJ:  88,
    SCALE_FORMULA_MIN:  88,
    SCALE_CHROMATIC:   100,
}

SCALE_NAMES = {
    SCALE_MAJ:          "Major",
    SCALE_MIN_MLD:      "Minor Melodic",
    SCALE_MIN_HRM:      "Minor Harmonic",
    SCALE_DOM7_SOLID:   "Dominant 7th Solid",
    SCALE_DOM7_BROKEN:  "Dominant 7th Broken",
    SCALE_DIM7_SOLID:   "Diminished 7th Solid",
    SCALE_DIM7_BROKEN:  "Diminished 7th Broken",
    SCALE_DOM7_ARP:     "Dominant 7th Arpeggio",
    SCALE_DIM7_ARP:     "Diminished 7th Arpeggio",
    SCALE_MAJ_TONIC_4:  "Major Tonic 4 Note",
    SCALE_MIN_TONIC_4:  "Minor Tonic 4 Note",
    SCALE_ARP_MIN:      "Minor Arpeggio",
    SCALE_ARP_MAJ:      "Major Arpeggio",
    SCALE_FORMULA_MAJ:  "Major Formula Pattern",
    SCALE_FORMULA_MIN:  "Minor Formula Pattern",
    SCALE_CHROMATIC:    "Chromatic"
}


triangle_shader = {
    "vert": """
#version 450
layout(location = 0) in vec4 position;
layout(location = 1) in vec4 color;
out vec4 color_out;
void main() {
    gl_Position = vec4(position.xyz * 2 - 1, 1);
    color_out = color;
    color_out.w = 1.0;
}
""",
    "frag": """
#version 450
smooth in vec4 color_out;
out vec4 outputColor;
void main() {
    outputColor = color_out;
    outputColor.w = 0.25;
}
""",
}

muted = False
def metronome():
    t = time.time()

    while 1:
        delta_time = 60 / bpm
        time.sleep((t + delta_time) - time.time())
        #while time.time() < t + delta_time:
        #    time.sleep(0.01)
        if not muted:
            tick.play()
        t += delta_time

def set_bpm(new_bpm):
    global bpm
    bpm = new_bpm

def generate_scales(keys, forms):
    scales = [(key, form) for key in keys for form in forms]
    return scales

def main(scales):
    random.shuffle(scales)
    tricky = []
    i = 0
    for key, form in scales:
        set_bpm(BPM_TARGETS[form])
        scale = KEY_NAMES[key] + " " + SCALE_NAMES[form]
        print(f"[{i + 1}/{len(scales)}]  {scale}", end="")
        a = input()
        if a:
            tricky.append(scale)
        i += 1
    print(sorted(tricky))

class Controller:

    DONE_TIMER = 2 # scale is considered "done" after this many seconds without playing

    def __init__(self, scales):
        self.scales = scales
        self.num_scales = len(self.scales)
        self.current_scale = -1
        self.next_scale()

        self.pressed_keys = {}
        self.released_keys = []

        self.is_playing = False
        self.time_started = 0
        self.time_current = 0
        self.time_stopped = time.time() + 3600

        self._init_gl()

    def quit(self):
        exit()

    def _init_gl(self):
        gl.glClearColor(0, 0, 0, 1)
        gl.glEnable(gl.GL_BLEND)
        gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)
        gl.glPointSize(5)

    def next_scale(self):
        self.current_scale = (self.current_scale + 1) % len(self.scales)
        set_bpm(BPM_TARGETS[self.scales[self.current_scale][1]])

    def prev_scale(self):
        self.current_scale = (self.current_scale - 1) % len(self.scales)
        set_bpm(BPM_TARGETS[self.scales[self.current_scale][1]])

    def on_midi(self, event):
        t = time.time()
        if event.type == "note_on":
            if not self.is_playing:
                self.time_started = t
                self.released_keys = []
            self.is_playing = True
            self.time_stopped = t
            event.time = t
            self.pressed_keys[event.note] = event
        elif event.type == "note_off":
            if event.note in self.pressed_keys:
                evt = self.pressed_keys.pop(event.note)
                #self.time_stopped = t
                self.released_keys.append((evt.note, evt.time, t, evt.velocity))
                #print(evt)
                if len(self.pressed_keys) == 0:
                    self.time_stopped = t
        elif event.type == "control_change":
            pass
        #print(type(event.type))
        #print(f"time:     {event.time}")
        #print(f"type:     {event.type}")
        #print(f"note:     {event.note}")
        #print(f"velocity: {event.velocity}")
        #print()

    def on_keyboard(self, key, x, y):
        #print(key, x, y)
        if key == b'q':
            self.quit()
        elif key == b'm':
            global muted
            muted = not muted
        elif key == b'\r':
            self.next_scale()
        elif key == b'\x08': # backspace
            self.prev_scale()
        else:
            print(key, ord(key))

    def on_special(self, key, x, y):
        if key == glut.GLUT_KEY_UP:
            set_bpm(bpm + 1)
        elif key == glut.GLUT_KEY_DOWN:
            set_bpm(bpm - 1)

    def on_mouse(self, button, state, x, y):
        pass

    def update(self):

        if self.is_playing:
            self.time_current = time.time()
            if not self.pressed_keys:
                t = time.time()
                if t - self.time_stopped > self.DONE_TIMER:
                    self.is_playing = False
                    #print(self.released_keys)
                    self.time_stopped = t
                    #print(self.time_started, self.time_stopped)

        glut.glutPostRedisplay()

    def draw(self):
        gl.glClear(gl.GL_COLOR_BUFFER_BIT)

        end_time = self.time_stopped
        if self.is_playing:
            end_time = self.time_current

        # draw background
        if self.is_playing:
            gl.glColor4f(0, 1, 0, 0.55)
        else:
            gl.glColor4f(1, 0, 0, 0.55)

        gl.glBegin(gl.GL_QUADS)
        gl.glVertex2f(-1, -1)
        gl.glVertex2f( 1, -1)
        gl.glVertex2f( 1,  1)
        gl.glVertex2f(-1,  1)
        gl.glEnd()

        # draw metronome bars

        # draw notes
        gl.glColor4f(1, 1, 1, 0.5)
        delta_t = (end_time) - self.time_started
        gl.glBegin(gl.GL_QUADS)
        for key, start, stop, velocity in self.released_keys:
            x1 = (start - self.time_started) / delta_t
            x2 = (stop  - self.time_started) / delta_t
            y  = key / 128
            y  = y * 1.5 - 0.5
            gl.glVertex2f(x1 * 2 - 1, y + 0.015)
            gl.glVertex2f(x2 * 2 - 1, y + 0.015)
            gl.glVertex2f(x2 * 2 - 1, y)
            gl.glVertex2f(x1 * 2 - 1, y)
        gl.glEnd()

        gl.glColor4f(1, 1, 1, 1)
        gl.glBegin(gl.GL_POINTS)
        for key, start, stop, velocity in self.released_keys:
            x = (start - self.time_started) / delta_t
            y  = velocity / 128
            gl.glVertex2f(x * 2 - 0.99, y * 0.8 - 1)
        gl.glEnd()

        # draw text
        gl.glColor3f(1, 1, 1)
        gl.glRasterPos2f(-0.975, -0.95)
        #glutPrint("asdf")
        glut.glutBitmapString(glut.GLUT_BITMAP_9_BY_15, f"BPM: {bpm}".encode())
        gl.glRasterPos2f(-0.975, -0.90)
        prog = f"[{self.current_scale + 1}/{len(self.scales)}]"
        key = KEY_NAMES[self.scales[self.current_scale][0]]
        scale = SCALE_NAMES[self.scales[self.current_scale][1]]
        glut.glutBitmapString(glut.GLUT_BITMAP_9_BY_15, f"Scale: {prog} {key} {scale}".encode())
        gl.glFlush()

def glutPrint(string):
    gl.glRasterPos2i(0, 0)
    for char in string:
        glut.glutBitmapCharacter(glut.GLUT_BITMAP_8_BY_13, ord(char))


if __name__ ==  "__main__":

    keys = ["C", "D", "E", "Bb", "Gb", "Eb"]
    keys = [KEY_C, KEY_D, KEY_E, KEY_B_FLAT, KEY_G_FLAT, KEY_E_FLAT]

    scales      = [SCALE_MAJ, SCALE_MIN_HRM, SCALE_MIN_MLD] #"Major", "Harmonic Minor", "Melodic Minor"]
    tonics      = [SCALE_MAJ_TONIC_4, SCALE_MIN_TONIC_4] # ["min Tonic 4-Note", "Maj Tonic 4-Note"]
    sevenths    = [SCALE_DIM7_BROKEN, SCALE_DIM7_SOLID, SCALE_DOM7_BROKEN, SCALE_DOM7_SOLID] #["Dom7 Solid", "Dom7 Broken", "Dim7 Solid", "Dim7 Broken"]
    brokenSevenths = [SCALE_DIM7_BROKEN, SCALE_DOM7_BROKEN] # ["Dom7 Broken", "Dim7 Broken"]
    solidSevenths = [SCALE_DIM7_SOLID, SCALE_DOM7_SOLID] #["Dom7 Solid", "Dim7 Solid"]
    seventhsArps = [SCALE_DIM7_ARP, SCALE_DOM7_ARP] #["Dominant 7th Arpeggio", "Diminished 7th Arpeggio"]
    arpeggios = [SCALE_ARP_MAJ, SCALE_ARP_MIN] #["Maj Arpeggios", "min Arpeggios"]

    all_forms = scales + tonics + brokenSevenths + solidSevenths + seventhsArps + arpeggios
    difficults_forms = tonics + brokenSevenths + seventhsArps + arpeggios
    #controller = Controller()
    #port = mido.open_input()
    #port.callback = controller.on_midi

    bpm = 60
    next_tick_time = 0

    print("\n\n")
    m = threading.Thread(target=metronome, daemon=True)
    m.start()
    scales = generate_scales(keys, difficults_forms)
    scales.extend([
        (KEY_E_FLAT, SCALE_FORMULA_MAJ),
        (KEY_E_FLAT, SCALE_FORMULA_MIN),
        (KEY_E_FLAT, SCALE_CHROMATIC),
    ])


    # tricky ones
    scales.extend([
        (KEY_G_FLAT, SCALE_ARP_MAJ),
        (KEY_E_FLAT, SCALE_ARP_MIN),
    ])
    random.shuffle(scales)

    #main(scales)


    # add sight reading to randomizer

    

    glut.glutInit()

    # Setup window
    w, h = (960, 800)
    screen_width  = glut.glutGet(glut.GLUT_SCREEN_WIDTH)
    screen_height = glut.glutGet(glut.GLUT_SCREEN_HEIGHT)

    glut.glutInitWindowSize(w, h)
    #glut.glutInitWindowPosition(0, 0)
    glut.glutInitDisplayMode(glut.GLUT_SINGLE | glut.GLUT_RGB)
    glut.glutCreateWindow(b'glMidi')

    controller = Controller(scales)
    
    port = mido.open_input()
    port.callback = controller.on_midi

    # Register event callbacks
    glut.glutIdleFunc(controller.update)
    glut.glutDisplayFunc(controller.draw)
    glut.glutKeyboardFunc(controller.on_keyboard)
    glut.glutSpecialFunc(controller.on_special)
    glut.glutMouseFunc(controller.on_mouse)
    #glut.glutReshapeFunc(controller.resize)

    glut.glutMainLoop()