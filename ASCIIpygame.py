import sys
import pygame
import random
import math
from gpiozero import Button

#######################################################
#region game params & initialization
#######################################################
pygame.init()

clock = pygame.Clock()

font_dict = {i: pygame.font.SysFont('georgia', i) for i in range(100)}

kelpfont = pygame.font.SysFont("couriernew", 12, bold=True)
cache = {} # stores all kelp fonts

h, w = 516, 720
fins = ["0", "d", "f", "fd"]
fish_frame_dict = { "(": ")",  ")": "(",  ">": "<",  "<": ">",
                    "*": "*",  "/": "\\", "\\": "/"}
#######################################################
#endregion
#######################################################
#region Helper Functions
#######################################################
## Checks if a given coordinate is inbounds, returns true/false
in_bounds = lambda x, y: 0 <= x <= w and 50 <= y <= h

def far_out_of_bounds(fish, x, y):
    """
    Determines if a new spot is far enough out of bounds to create/delete a fish
    """
    if (fish.length + x < 0 and y < h - 200) or (fish.length + x > w and y < h - 200):
        return True
    return False

def flip_body(chars):
    """
    Given a proper body of the form [(char, size), ...]
    Reverses characters and returns the new body object
    """
    return [(fish_frame_dict[c[0]], c[1]) for c in reversed(chars)]

def draw_bresenham_line(x1, y1, x2, y2):
    """
    Generates integer pixel coordinates for a line between two points
    using Bresenham's line algorithm
    """
    x1, y1, x2, y2 = round(x1), round(y1), round(x2), round(y2)
    pixels = []
    
    # Calculate absolute differences
    dx = abs(x2 - x1)
    dy = abs(y2 - y1)
    
    # Determine step directions
    sx = 1 if x1 < x2 else -1
    sy = 1 if y1 < y2 else -1
    
    # Identify the control / driving axis
    if dx > dy:
        # X-axis is the driving axis
        p = 2 * dy - dx
        x, y = x1, y1
        while x != x2:
            pixels.append((x, y))
            if p >= 0:
                y += sy
                p -= 2 * dx
            x += sx
            p += 2 * dy
        pixels.append((x, y)) # Add the final point
    else:
        # Y-axis is the driving axis
        p = 2 * dx - dy
        x, y = x1, y1
        while y != y2:
            pixels.append((x, y))
            if p >= 0:
                x += sx
                p -= 2 * dy
            y += sy
            p += 2 * dx
        pixels.append((x, y)) # Add the final point
        
    return pixels

def ramp(a, b, n):
    """
    n integers evenly spaced from a to b (inclusive).
    """
    if n == 1:
        return [a]
    return [round(a + (b - a) * i / (n - 1)) for i in range(n)]

def add_fish(f_stack):
    """
    Randomly generates a fish object by arbitrarily creating each body part with different
    length, size, and color. 07% chance to generate regular fish of any length (keep things pretty).
    """
    length = random.randint(0, 8)
    mutant = random.random()
    colors_max = random.randint(1, length + 1)
    colors = colors_max*[0]

    # randomly generate color sequence
    for i in range(colors_max):
        colors[i] = (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))

    # normal fish
    if mutant <= 0.5:
        font_size = random.randint(10, 50)
        body = "<*" + length*"(" + "><"
        fs = (length+4)*[font_size]

    else:
        head_sz, tail_sz = random.randint(10, 60), random.randint(10, 70)
        body_sz = random.randint(20, 70)
        grad = random.random()

        # gradient up for body size
        if grad <= 0.5:
            fs = 2*[head_sz] + length*[body_sz] + 2*[tail_sz]

        # gradient down for body size
        else:
            fs = 2*[head_sz] + ramp(head_sz, tail_sz, length) + 2*[tail_sz]

        body = "<*" + length*"(" + "><"

    fih = fish(body, (0, 0), random.randint(1, 4), fs, colors,
               random.randint(50, 300), random.random(), "0", f_stack)
    f_stack.append(fih)

    # Determine starting position
    y, x = random.randint(0, h - 200), 0
    side = random.random()
    while not far_out_of_bounds(fih, x, y):
        # decide if fish spawns in from left or right
        if side < 0.5:
            x = -1*random.randint(fih.length, 2*fih.length)
            fih.text, fih.facing = fih.textr, "right"
        else:
            x = w + random.randint(fih.length, 2*fih.length)
            fih.text, fih.facing = fih.textl, "left"
    fih.pos = (x, y)
    xg, yg = random.randint(0, w), random.randint(0, h)
    fih.points = draw_bresenham_line(*fih.pos, xg, yg)[::fih.vel]
    return None

def remove_fish(f_stack):
    """
    Removes a random fish in the stack. Fish will be assigned
    coordinates out of bounds to swim to. Either adds points to current
    pathway if the fish is swimming, or interrupts rest
    """
    # empty case, return none to avoid rand range error
    if not f_stack:
        return None
    
     # selecting fish for removal
    index = random.randint(0, len(f_stack)-1)
    fih = fishlist[index]
    i = 0
    while fih.leaving is True and i < 20:
        index = index = random.randint(0, len(f_stack)-1)
        fih = fishlist[index]
        i += 1

    # all fish are leaving, end early
    if i == 20:
        return
    
    y, x = random.randint(0, h - 200), 0
    while not far_out_of_bounds(fih, x, y):
        # decide if fish exits to the left or right
        if fih.facing == "right":
            x = w + random.randint(fih.length, 2*fih.length)
        else:
            x = -random.randint(fih.length, 2*fih.length)

    # fish is stationary, can start moving now
    if not fih.points:
        fih.points = draw_bresenham_line(*fih.pos, x, y)[::fih.vel]
        fih.can_act = True

    # append points to current path
    else:
        fih.points.extend(draw_bresenham_line(*fih.points[-1], x, y)[::fih.vel])
    fih.leaving = True
    return None

def add_bubble(bub_stack, fish=None):
    """
    Given a bubble list, creates a bubble object and appends to the list
    """
    # if fish is not None:
    radius = random.randint(5, 15)
    pos = (random.randint(0, w), h + 10*radius)
    bub_stack.append(bubble(pos, radius**0.5, radius, radius/4, 
                            random.randint(0, 10000), 0.005*(1.25-1/15*radius)))
    return None

def lerp(a, b, t): return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))

def glyph(ch, color):
    """
    Returns rendered font object of kelp characters,
    or creates them if they have not been made already
    """
    if (ch, color) not in cache:
        cache[(ch, color)] = kelpfont.render(ch, True, color)
    return cache[(ch, color)]


#######################################################
#endregion
#######################################################
#region Classes
#######################################################
class fish:
    """
    fish class, used only for representing fish in the asciiquarium
    """
    def __init__(self, chars, pos, vel, fs, colors, decrange, laze, fins, stack=None):
        """
        chars (string): body of fish as ascii characters: ex: <*((((><
        pos (tuple): coordinates of first character of fish's body
        vel: constant (int), defines movement speed of fish
        fs: font size (list), determines how large each fish character is drawn.
        colors (tuple): stores color array for the fish, length(colors) <= length(chars)
        range (int): determines radius of action for fish
        laze (float): used to determine whether a fish will move
        fins (char): either "0", "d", "f", or "fd", determines where fins are drawn
        stack, the list of fish objects that this fish belongs to
        """
        # wrap colors to repeat over length of fish
        colorlist, sze = len(chars)*[0], len(colors)
        for i in range(len(chars)):
            colorlist[i] = colors[(i+1) % sze]
        self.colorsl = colorlist
        self.colorsr = list(reversed(colorlist))

        # Create fish body
        self.textl = [(pair) for pair in zip(chars, fs)]
        self.textr = flip_body(self.textl)
        self.prep_text()
        self.text = self.textl
        self.length = 0
        self.height = 0
        for c in self.text:
            l, h = c.get_size()
            self.length += l
            if h > self.height:
                self.height = h

        self.pos = pos
        self.vel = vel

        self.decrange = decrange
        self.facing = "left"
        self.laze = laze
        self.fins = fins
        self.can_act = True
        self.new = True
        self.points = []
        self.end_time = None
        self.max_size = max(fs)
        self.leaving = False
        self.stack = stack
        self.id = random.random()

    def prep_text(self):
        """
        Given textr and textl for the fish, generates the list of font objects
        to render on screen

        # textl = font.render('<*((((><', True,  (255, 0, 0))
        # textr = font.render('><))))*>', True, (0, 0, 255))
        """
        tr, tl = self.textr, self.textl
        cl, cr = self.colorsl, self.colorsr

        # render text
        self.textr = [(font_dict[size].render(c, True, cr[i])) for i, (c, size) in enumerate(tr)]
        self.textl = [(font_dict[size].render(c, True, cl[i])) for i, (c, size) in enumerate(tl)]
        # format: [(font screen obj, font rectangle: (x, y, w, h))]

    def sketch(self, screen, time):
        """
        Sketches each character in self.text starting at self.pos
        """
        loc_sum = 0 # stores how far away we should generate
        
        wave_amplitude = 2.5 * self.max_size/60      # How high/low the wave goes
        wave_frequency = 0.4    # Space between wave peaks along the text
        speed = 0.2               # How fast the wave travels

        if self.facing == "right":
            for (i, c) in enumerate(self.text):
                phase = (time * speed) - (i * wave_frequency)
                vertical_offset = wave_amplitude * math.sin(phase)

                # blit takes screen obj, and pos
                screen.blit(c, (self.pos[0] + loc_sum, self.pos[1] + vertical_offset - c.get_size()[1]/2))
                loc_sum += c.get_size()[0]

        else: # + 2*math.sin(time + i)
            for (i, c) in enumerate(self.text):
                phase = (time * speed) - (i * wave_frequency)
                vertical_offset = wave_amplitude * math.sin(phase)

                # blit takes screen obj, and pos
                screen.blit(c, (self.pos[0] + loc_sum, self.pos[1] + vertical_offset - c.get_size()[1]/2))
                loc_sum += c.get_size()[0]

    def turn_around(self):
        """
        turns fish around, inverting characters about center and updating location to the end
        Updates self.text
        """
        if self.facing == "right":
            self.facing = "left"
            self.text = self.textl

        else:
            self.facing = "right"
            self.text = self.textr

    def choose_spot(self):
        """
        Uses decision range to choose a new spot for the fish to swim to.
        Returns the coordinates of the new spot
        """
        R = self.decrange
        x = random.uniform(-R, R)
        y = random.uniform(-R, R)

        while (x)**2 + (y)**2 > R**2 or not in_bounds(self.pos[0] + round(x), self.pos[1] + round(y)):
            x = random.uniform(-R, R)
            y = random.uniform(-R, R)
        return (self.pos[0] + round(x), self.pos[1] + round(y))

    def update(self):
        """
        If the fish is swimming, move to the next location,

        If the fish is stationary, check if it can move again, 
        try to select new point with laziness factor, check turnaround.

        If the fish is not actionable, return None
        """
        if not self.points:
            # no update, fish is inactionable
            if self.leaving:
                self.stack.remove(self)
                return None
            
            if self.can_act == False:
                if pygame.time.get_ticks() - self.end_time >= self.laze * 5000:
                    self.can_act = True
                return None

            # No points to swim to, can act. Generate a new location!
            new_loc = self.choose_spot()
            self.points = draw_bresenham_line(*self.pos, *new_loc)[::self.vel] # generate new point series
            last = self.points[-1] # turn around as first move if necessary

            if (last[0] < self.pos[0] and self.facing == 'right') or (last[0] > self.pos[0] and self.facing == 'left'):
                self.turn_around()
                self.can_act = False
                return

            else:
                self.pos = self.points[0]
                self.points = self.points[1:]
                self.can_act = False

                if not self.points: # only had to move 1 tile, pause
                    self.end_time = pygame.time.get_ticks()
                return
        else:
            self.pos = self.points[0]
            self.points = self.points[1:]

            if not self.points and not self.leaving:
                self.end_time = pygame.time.get_ticks()
                self.can_act = False

    def __eq__(self, fih2):
        return self.id == fih2.id

class bubble:
    """
    Bubble class, stores location, vel, amp, and ID
    """
    def __init__(self, pos, vel, rad, amp, ID, freq):
        self.pos = pos
        self.vel = vel
        self.rad = rad
        self.amp = amp
        self.ID = ID
        self.freq = freq
        self.bub = font_dict[rad*2].render("o", True, (0, 100, 200))
        self.light = font_dict[rad].render("'", True, (200, 200, 255))

    def sketch(self, screen, time):
        """
        Draws bubble object on screen. Follows a sinusoidal path until it is off the screen.
        Assumes terminal velocity
        """
        x_offset = self.amp*math.sin(time*self.freq)
        screen.blit(self.bub, (self.pos[0] + x_offset, self.pos[1]))
        screen.blit(self.light, (self.pos[0] + x_offset + self.rad/1.6, self.pos[1] + self.rad/1.1))
        return None

    def update(self, bubblestack):
        """
        Updates bubble's vertical position, and checks if it is offscreen yet.
        Removes from bubblestack if it is offscreen.
        """
        self.pos = (self.pos[0], self.pos[1] - self.vel)
        if self.pos[1] + 2*self.rad < 0:
            bubblestack.remove(self)

    def __eq__(self, other):
        return self.ID == other.ID

class kelp:
    """
    Kelp object, stores height and location from bottom. Body will be procedurally
    generated. Follows sinusoidal motion with rooted base
    """
    def __init__(self, color, amp, speed, fill_char, strand, win):
        """
        color: rgb color tuple
        amp: scalar, amplitude of oscillation
        speed: scalar, frequency of oscillation
        fill_char: string, character used to fill gaps in the rendered kelp
        strand: tuple, contains: base_col, height_rows, speed, phase, base_width)
        win: screen object that kelp will be drawn on
        """
        self.color = color
        self.amp = amp
        self.speed = speed
        self.fill_char = fill_char
        self.strand = strand
        self.win = win

    def update(self, time):
        """
        Produces new kelp body for the next frame.
        time is used to find position on traveling wave
        """
        bx, height, sp, ph, bw = self.strand
        sp *= self.speed
        for row in range(height):
            x  = self.strand_x(bx, height, sp, ph, self.amp, time, row)
            x2 = self.strand_x(bx, height, sp, ph, self.amp, time, row + 1)
            w = self.width_at(bw, row, height)
            self.draw_row(x, x2 - x, w, self.color, self.fill_char, row)
        return None

    def strand_x(self, bx, height, speed, phase, amp, t, row):
        """
        Uses traveling waves to determine x location of current kelp row
        """
        k = row / height
        return bx + (math.sin(t * speed + phase - row * 0.3) * 3.5
                 + math.sin(t * 0.4 + row * 0.1) * 1.5) * amp * k ** 1.3

    def width_at(self, base, row, height):
        return max(1, round(base * (1 - 0.6 * row / height)))

    def put(self, ch, col, c, row):
        """
        Renders a character at the given location
        """
        if 0 <= c < COLS:
            self.win.blit(glyph(ch, col), (c * CW, (h - (ROWS)*CH) + (ROWS - 1 - row) * CH))
        return None

    def draw_row(self, x, dx, w, col, fill, row):
        """
        Draws the entire row for a given kelp strand
        """
        left = round(x - (w - 1) / 2)
        if dx > 0.7 or dx < -0.7:
            ch = "/" if dx > 0 else "\\"
            for i in range(w): self.put(ch, col, left + i, row)
        elif w == 1:
            lean = dx + (x - left) * 0.9
            self.put(")" if lean > 0.25 else "(" if lean < -0.25 else "|", col, left, row)
        else:
            self.put("(", col, left, row)
            self.put(")", col, left + w - 1, row)
            for i in range(1, w - 1): self.put(fill, col, left + i, row)

#######################################################
#endregion
#######################################################
#region GAME Loading
#######################################################
B_add, B_remove = Button(17), Button(27)

FISH_ADD = pygame.event.custom_type()
FISH_REMOVE = pygame.event.custom_type()
B_add.when_activated = lambda: pygame.event.post(pygame.event.Event(FISH_ADD))
B_remove.when_activated = lambda: pygame.event.post(pygame.event.Event(FISH_REMOVE))


screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
win = pygame.Surface((w, h))

pygame.display.flip()
pygame.display.set_caption('Tiles')
pygame.display.flip()
win.fill((0,0,0))

# prechosen fish colors
colors1 = [(255, 255, 255), (255, 150, 0)]
colors2 = [(255, 10, 10), (5, 200, 0)]
colors3 = [(255, 255, 10), (5, 200, 255)]
colors4 = [(255, 50, 255), (100, 200, 255), (0, 0, 250)]
colors5 = [(255, 0, 255), (200, 200, 255), (0, 100, 250), (255, 255, 255)]

# pre-generated fish for your enjoyment
fishlist = [0, 0, 0, 0]
f = fish('<*((((((((><', (356, 254), 2, 12*[30], colors1, 400, 1, "0", fishlist)
f3 = fish('<*(((><', (200, 320), 3, 7*[30], colors3, 350, 0.45, "0", fishlist)
f4 = fish('<*((((((><', (356, 254), 2, 12*[40], colors4, 400, 1, "0", fishlist)
f5 = fish('<*((((><', (200, 320), 2, 8*[20], colors5, 350, 0.45, "0", fishlist)
fishlist[0] = f
fishlist[1] = f3
fishlist[2] = f4
fishlist[3] = f5

# initial test bubble
bubs = bubble((300, 600), 3, 10, 5, 11203, 0.005)
bubblelist = [bubs]

# initial kelp
CW, CH = 6, 10 # number of rows/columns to render kelp
COLS, ROWS = 120, 22
# background
kelplist_bg = [kelp(lerp((0, 0, 0), (60, 200, 100), 0.65), 0.85, 0.85, "|", (16, 14, 1.0, 0.0, 2), win),
               kelp(lerp((0, 0, 0), (60, 200, 100), 0.65), 0.85, 0.85, "|", (50, 15, 0.8, 1.7, 2), win),
               kelp(lerp((0, 0, 0), (60, 200, 100), 0.65), 0.85, 0.85, "|", (85, 13, 1.2, 3.1, 2), win)]
# foreground
kelplist_fg = [kelp((65, 220, 105), 1.0, 1.0, "#", (34, 20, 0.9, 4.6, 4), win),
               kelp((65, 220, 105), 1.0, 1.0, "#", (70, 17, 1.0, 2.2, 3), win),
               kelp((65, 220, 105), 1.0, 1.0, "#", (100, 15, 0.8, 2.2, 3), win)]
#######################################################
#endregion
#######################################################
#region Loop
#######################################################

FPS = 30
run = True
while run:
    win.fill((0,0,0))
    # win.blit(text, playerpos)
    for bgk in kelplist_bg:
        bgk.update(pygame.time.get_ticks()/750)

    for f in fishlist:
        f.sketch(win, pygame.time.get_ticks())

    for b in bubblelist:
        b.sketch(win, pygame.time.get_ticks())

    for fgk in kelplist_fg:
        fgk.update(pygame.time.get_ticks()/750)

    scaled = pygame.transform.scale(win, screen.get_size())
    screen.blit(scaled, (0, 0))
    pygame.display.flip()

    for f in fishlist:
        f.update()

    for b in bubblelist:
        b.update(bubblelist)

    # 1% change to generate bubble each frame
    if random.random() < 0.01:
        add_bubble(bubblelist)

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            run = False

        if event.type == FISH_ADD:
            add_fish(fishlist)

        if event.type == FISH_REMOVE:
            remove_fish(fishlist)

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_SPACE:
                add_fish(fishlist)

            if event.key == pygame.K_LSHIFT:
                remove_fish(fishlist)

    clock.tick(FPS)
pygame.quit()
sys.exit()

#######################################################
#endregion
#######################################################
