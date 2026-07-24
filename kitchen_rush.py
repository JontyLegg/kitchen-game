import math
import os
import random
import sys
from collections import deque
from dataclasses import dataclass, field

import pygame


pygame.init()
pygame.display.set_caption("Kitchen Rush")
DISPLAY = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
SCREEN = pygame.Surface((1180, 760))
CLOCK = pygame.time.Clock()
IMAGE_DIR = os.path.join(os.path.dirname(__file__), "images")


def image(name):
    surface = pygame.image.load(os.path.join(IMAGE_DIR, name)).convert_alpha()
    # Remove white/checkered backdrops only when connected to an outer edge, so
    # pale highlights inside the food remain intact.
    width, height = surface.get_size()
    def background_pixel(x, y):
        r, g, b, a = surface.get_at((x, y))
        return a and min(r, g, b) > 210 and max(r, g, b) - min(r, g, b) < 18

    queue = deque()
    seen = set()
    for x in range(width):
        queue.extend([(x, 0), (x, height - 1)])
    for y in range(height):
        queue.extend([(0, y), (width - 1, y)])
    while queue:
        x, y = queue.popleft()
        if (x, y) in seen or not (0 <= x < width and 0 <= y < height) or not background_pixel(x, y):
            continue
        seen.add((x, y))
        r, g, b, _ = surface.get_at((x, y))
        surface.set_at((x, y), (r, g, b, 0))
        queue.extend(((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)))
    bounds = surface.get_bounding_rect()
    return surface.subsurface(bounds).copy() if bounds.width and bounds.height else surface


IMAGES = {
    "raw_burger": image("uncooked burger patty.png"),
    "cooked_burger": image("cooked Burger patty.png"),
    "raw_chips": image("uncooked chips.png"),
    "cooked_chips": image("cooked chips.png"),
    "empty_drink": image("empty cup.png"),
    "filled_drink": image("filled cup.png"),
    "bun": image("empty burger bun.png"),
    "burger": image("burger buns with patty.png"),
    "pan": image("pan.png"),
}

FONT = pygame.font.SysFont("arial", 20)
SMALL = pygame.font.SysFont("arial", 16)
TITLE = pygame.font.SysFont("arial", 34, bold=True)
BIG = pygame.font.SysFont("arial", 25, bold=True)

BG = (27, 31, 41)
PANEL = (42, 48, 62)
PANEL_DARK = (33, 38, 50)
CREAM = (250, 242, 220)
MUTED = (176, 183, 198)
ORANGE = (244, 143, 53)
RED = (226, 77, 75)
GREEN = (89, 202, 126)
BLUE = (85, 177, 230)
YELLOW = (248, 210, 72)


def draw_text(surface, text, pos, font=FONT, color=CREAM, center=False):
    image = font.render(text, True, color)
    rect = image.get_rect()
    rect.center = pos if center else rect.center
    if not center:
        rect.topleft = pos
    surface.blit(image, rect)


def draw_image(surface, key, rect, padding=0):
    target = rect.inflate(-padding * 2, -padding * 2)
    source = IMAGES[key]
    scaled = pygame.transform.smoothscale(source, target.size)
    surface.blit(scaled, scaled.get_rect(center=rect.center))


def clamp(value, low, high):
    return max(low, min(high, value))


@dataclass
class Order:
    number: int
    items: list
    patience: float = 58.0
    max_patience: float = 58.0
    flash: float = 0.0
    plated: list = field(default_factory=list)
    has_bun: bool = False

    def label(self):
        return " + ".join(self.items)


@dataclass
class Food:
    kind: str
    stage: str = "raw"
    progress: float = 0.0
    flipped: bool = False
    burning: bool = False
    burn_flash: float = 0.0


@dataclass
class Station:
    name: str
    rect: pygame.Rect
    kind: str
    food: Food | None = None
    fill: float = 0.0


class KitchenRush:
    def __init__(self):
        self.running = True
        self.score = 0
        self.served = 0
        self.missed = 0
        self.next_order_number = 1
        self.orders: list[Order] = []
        self.message = "Take an order, then use the stations to prepare it."
        self.message_timer = 6.0
        self.spawn_timer = 0.0
        self.selected_order = 0
        self.dragging = None
        self.drag_item = None
        self.held_item = None
        self.filling = False
        self.storage = [None, None]
        self.game_time = 0.0
        self.stations = [
            Station("HOB", pygame.Rect(38, 170, 330, 245), "hob"),
            Station("DEEP FAT FRYER", pygame.Rect(390, 170, 330, 245), "fryer"),
            Station("DRINK FILLER", pygame.Rect(742, 170, 400, 245), "drink"),
        ]
        self.add_order()
        self.add_order()

    def add_order(self):
        # Weighted orders keep the first playthrough learnable but increasingly busy.
        recipes = [["Burger"], ["Chips"], ["Drink"], ["Burger", "Chips"], ["Burger", "Drink"], ["Chips", "Drink"]]
        items = random.choice(recipes)
        self.orders.append(Order(self.next_order_number, items))
        self.next_order_number += 1

    def say(self, message, duration=3.0):
        self.message = message
        self.message_timer = duration

    def selected(self):
        if not self.orders:
            return None
        self.selected_order = clamp(self.selected_order, 0, len(self.orders) - 1)
        return self.orders[self.selected_order]

    def take_from_station(self, station):
        if not station.food:
            return False
        if station.food.burning:
            self.say("That item is burnt. Use BIN before starting again.")
            return False
        if station.food.stage != "ready":
            self.say("That item is still cooking.")
            return False
        if station.food.kind == "Drink" and station.fill < 0.9:
            self.say("Fill the drink to the target line before taking it off.")
            return False
        item = {"kind": station.food.kind, "fill": station.fill}
        station.food = None
        station.fill = 0
        self.held_item = item
        self.say(f"{item['kind']} picked up. Drag it onto the matching order.")
        return True

    def drop_on_station(self, kind, station):
        if station.food:
            self.say(f"The {station.name.lower()} is already occupied.")
            return
        if kind == "Burger" and station.kind == "hob":
            station.food = Food("Burger")
        elif kind == "Chips" and station.kind == "fryer":
            station.food = Food("Chips")
        elif kind == "Drink" and station.kind == "drink":
            station.food = Food("Drink")
            station.fill = 0
        else:
            self.say("That ingredient belongs at a different station.")
            return
        self.say(f"{kind} dropped onto the {station.name.lower()}.")
        self.drag_item = None

    def drop_on_plate(self, item):
        order = self.selected()
        if not order:
            return
        if item == "Bun":
            if order.has_bun:
                self.say("This plate already has a bun.")
            else:
                order.has_bun = True
                self.say("Bun added. Now drag the burger onto this order.")
        elif isinstance(item, dict):
            kind = item["kind"]
            if kind == "Burger" and not order.has_bun:
                self.say("Every burger needs a bun first — drag a bun onto this order.")
                return
            if kind in order.plated:
                self.say(f"This plate already has {kind.lower()}.")
            else:
                order.plated.append(kind)
                self.say(f"{kind} added to the order. Add the remaining items.")
        self.maybe_auto_serve(order)
        self.held_item = None
        self.drag_item = None

    def maybe_auto_serve(self, order):
        if set(order.items).issubset(set(order.plated)) and ("Burger" not in order.items or order.has_bun):
            self.serve_order(order)

    def action(self, action):
        order = self.selected()
        if action == "new_order":
            self.add_order()
            self.say("New customer! Select their ticket before cooking.")
            return
        if not order:
            self.say("There are no waiting customers.")
            return
        if action == "start_burger":
            station = self.stations[0]
            if station.food:
                self.say("The hob is already occupied.")
            else:
                station.food = Food("Burger", "raw")
                self.say(f"Patty started for order #{order.number}.")
        elif action == "flip":
            station = self.stations[0]
            if not station.food:
                self.say("Put a patty on the hob first.")
            elif station.food.stage == "ready":
                self.say("That patty is ready — move it to the pass.")
            elif station.food.flipped:
                self.say("You already flipped this patty.")
            else:
                station.food.flipped = True
                station.food.stage = "raw"
                station.food.progress = 0
                self.say("Patty flipped. Keep an eye on the bar!")
        elif action == "start_chips":
            station = self.stations[1]
            if station.food:
                self.say("The fryer is already occupied.")
            else:
                station.food = Food("Chips", "raw")
                self.say("Chips dropped into the fryer.")
        elif action == "start_drink":
            station = self.stations[2]
            if station.food:
                self.say("The drink filler is already occupied.")
            else:
                station.food = Food("Drink", "raw")
                station.fill = 0
                self.say("Empty cup placed. Use FILL DRINK when ready.")
        elif action == "serve":
            self.serve_order(order)
        elif action == "bin":
            for station in self.stations:
                if station.food and station.food.burning:
                    station.food = None
                    station.fill = 0
                    self.say("Burnt item binned. Start that item again.")
                    return
            self.say("Nothing burnt needs binning.")

    def serve_order(self, order):
        if not set(order.items).issubset(set(order.plated)):
            self.say("Plate every item on the selected ticket before serving.")
            return
        if "Burger" in order.items and not order.has_bun:
            self.say("A burger cannot leave without a bun.")
            return
        order.plated.clear()
        order.has_bun = False
        bonus = int(order.patience * 2)
        self.score += 100 + bonus
        self.served += 1
        self.orders.remove(order)
        self.selected_order = min(self.selected_order, max(0, len(self.orders) - 1))
        self.say(f"Order #{order.number} served! +{100 + bonus} points.")
        if len(self.orders) < 3:
            self.add_order()

    def update(self, dt):
        self.game_time += dt
        self.message_timer = max(0, self.message_timer - dt)
        if len(self.orders) < 4:
            self.spawn_timer += dt
            if self.spawn_timer > 16:
                self.spawn_timer = 0
                self.add_order()
                self.say("Another customer has arrived.")

        for order in self.orders[:]:
            order.patience -= dt
            if order.patience <= 0:
                self.orders.remove(order)
                self.missed += 1
                self.score = max(0, self.score - 50)
                self.selected_order = max(0, self.selected_order - 1)
                self.say(f"Order #{order.number} walked out. Keep moving!")

        hob = self.stations[0]
        if hob.food and not hob.food.burning:
            if hob.food.stage == "raw":
                speed = 0.22 if not hob.food.flipped else 0.18
                hob.food.progress += dt * speed
                if not hob.food.flipped and hob.food.progress >= 1:
                    hob.food.progress = 1
                    hob.food.stage = "warning"
                    hob.food.burn_flash = 3
                    self.say("FLIP NOW! The patty is starting to burn!", 3)
                elif hob.food.flipped and hob.food.progress >= 1:
                    hob.food.progress = 1
                    hob.food.stage = "ready"
                    hob.food.burn_flash = 3
                    self.say("Burger cooked! Take it off before it burns.", 3)
            elif hob.food.stage == "warning":
                hob.food.burn_flash -= dt
                if hob.food.burn_flash <= 0:
                    hob.food.burning = True
                    self.say("Patty burned! Bin it and start again.")
            elif hob.food.stage == "ready":
                hob.food.burn_flash -= dt
                if hob.food.burn_flash <= 0:
                    hob.food.burning = True
                    self.say("Burger burned! Bin it and start again.")

        fryer = self.stations[1]
        if fryer.food and not fryer.food.burning:
            fryer.food.progress += dt * 0.18
            if fryer.food.progress >= 1 and fryer.food.stage == "raw":
                fryer.food.progress = 1
                fryer.food.stage = "ready"
                fryer.food.burn_flash = 3
                self.say("Chips are ready — take them out before they burn!", 3)
            if fryer.food.stage == "ready" and fryer.food.burn_flash > 0:
                fryer.food.burn_flash -= dt
            elif fryer.food.stage == "ready" and fryer.food.burn_flash <= 0:
                fryer.food.stage = "burned"
                fryer.food.burning = True
                self.say("Chips burned! Bin them and start again.")

        drink = self.stations[2]
        if drink.food and not drink.food.burning:
            if drink.food.stage == "filling" and drink.fill >= 1:
                drink.fill = 1
                drink.food.stage = "ready"
                self.filling = False
                self.say("Drink filled! Pick it up and drag it onto its order.")

        for station in self.stations:
            if station.food and station.food.stage == "warning":
                station.food.burn_flash = max(0, station.food.burn_flash)

    def draw(self):
        SCREEN.fill(BG)
        draw_text(SCREEN, "KITCHEN RUSH", (38, 22), TITLE, CREAM)
        draw_text(SCREEN, "You are the whole kitchen. Read the tickets, multitask, and serve before patience runs out.", (40, 65), SMALL, MUTED)
        draw_text(SCREEN, f"SCORE  {self.score}", (890, 24), BIG, YELLOW)
        draw_text(SCREEN, f"SERVED {self.served}   WALKED OUT {self.missed}", (890, 58), SMALL, MUTED)
        self.draw_storage()
        self.draw_orders()
        for station in self.stations:
            self.draw_station(station)
        self.draw_controls()
        if self.drag_item or self.held_item:
            mouse = self.to_game_pos(pygame.mouse.get_pos())
            if self.drag_item:
                key = {"Burger": "raw_burger", "Chips": "raw_chips", "Drink": "empty_drink", "Bun": "bun"}[self.drag_item]
            else:
                key = {"Burger": "cooked_burger", "Chips": "cooked_chips", "Drink": "filled_drink"}[self.held_item["kind"]]
            draw_image(SCREEN, key, pygame.Rect(mouse[0] - 42, mouse[1] - 42, 84, 84))
        scaled = pygame.transform.smoothscale(SCREEN, DISPLAY.get_size())
        DISPLAY.blit(scaled, (0, 0))
        pygame.display.flip()

    def to_game_pos(self, pos):
        return (int(pos[0] * SCREEN.get_width() / DISPLAY.get_width()), int(pos[1] * SCREEN.get_height() / DISPLAY.get_height()))

    def storage_rects(self):
        return [pygame.Rect(455, 12, 82, 70), pygame.Rect(548, 12, 82, 70)]

    def draw_storage(self):
        draw_text(SCREEN, "STORAGE", (455, 2), SMALL, MUTED)
        for index, rect in enumerate(self.storage_rects()):
            pygame.draw.rect(SCREEN, PANEL, rect, border_radius=8)
            pygame.draw.rect(SCREEN, ORANGE if self.storage[index] else (77, 87, 108), rect, 2, border_radius=8)
            if self.storage[index]:
                key = {"Burger": "cooked_burger", "Chips": "cooked_chips", "Drink": "filled_drink"}[self.storage[index]["kind"]]
                draw_image(SCREEN, key, rect.inflate(-12, -12))
            else:
                draw_text(SCREEN, str(index + 1), rect.center, SMALL, MUTED, True)

    def draw_orders(self):
        draw_text(SCREEN, "CUSTOMER TICKETS", (38, 110), BIG, CREAM)
        x = 295
        for index, order in enumerate(self.orders):
            width = 245
            rect = pygame.Rect(x, 440, width, 122)
            selected = index == self.selected_order
            needed = set(order.items)
            supplied = set(order.plated)
            complete = needed.issubset(supplied) and ("Burger" not in needed or order.has_bun)
            partial = bool(needed & supplied) or ("Burger" in needed and order.has_bun)
            outline = GREEN if complete else ORANGE if partial else RED
            pygame.draw.rect(SCREEN, (67, 75, 95) if selected else PANEL, rect, border_radius=10)
            pygame.draw.rect(SCREEN, outline, rect, 4 if selected else 3, border_radius=10)
            draw_text(SCREEN, f"#{order.number}", (x + 14, 451), BIG, ORANGE)
            draw_text(SCREEN, order.label(), (x + 55, 454), FONT, CREAM)
            delivered = (["Bun"] if order.has_bun else []) + order.plated
            for item_index, item in enumerate(delivered[:4]):
                item_key = {"Bun": "bun", "Burger": "burger", "Chips": "cooked_chips", "Drink": "filled_drink"}[item]
                draw_image(SCREEN, item_key, pygame.Rect(x + 14 + item_index * 42, 476, 34, 30))
            if delivered:
                draw_text(SCREEN, "delivered", (x + 185, 486), SMALL, GREEN)
            draw_text(SCREEN, "patience", (x + 14, 508), SMALL, MUTED)
            pygame.draw.rect(SCREEN, PANEL_DARK, (x + 14, 532, width - 28, 10), border_radius=6)
            patience_color = GREEN if order.patience > 25 else RED
            pygame.draw.rect(SCREEN, patience_color, (x + 14, 532, int((width - 28) * order.patience / order.max_patience), 10), border_radius=6)
            x += width + 14
            if x + width > SCREEN.get_width():
                break

    def draw_station(self, station):
        pygame.draw.rect(SCREEN, PANEL, station.rect, border_radius=14)
        pygame.draw.rect(SCREEN, (77, 87, 108), station.rect, 2, border_radius=14)
        draw_text(SCREEN, station.name, (station.rect.x + 18, station.rect.y + 16), BIG, CREAM)
        inner = station.rect.inflate(-36, -70)
        pygame.draw.rect(SCREEN, PANEL_DARK, inner, border_radius=10)
        food = station.food
        if station.kind == "hob":
            draw_image(SCREEN, "pan", pygame.Rect(inner.centerx - 75, inner.y + 2, 150, 135))
            if food:
                draw_image(SCREEN, "cooked_burger" if food.stage in ("ready", "warning") else "raw_burger", pygame.Rect(inner.centerx - 55, inner.y + 28, 110, 90))
                self.draw_food_status(food, inner, "FLIP" if not food.flipped else "COOKING")
            else:
                draw_text(SCREEN, "DROP RAW PATTY", inner.center, SMALL, MUTED, True)
        elif station.kind == "fryer":
            pygame.draw.rect(SCREEN, (151, 98, 43), inner.inflate(-55, -28), border_radius=9)
            if food:
                draw_image(SCREEN, "cooked_chips" if food.stage in ("ready", "warning") else "raw_chips", pygame.Rect(inner.centerx - 90, inner.y + 20, 180, 105))
                self.draw_food_status(food, inner, "FRYING")
            else:
                draw_text(SCREEN, "DROP RAW CHIPS", inner.center, SMALL, MUTED, True)
        else:
            pygame.draw.rect(SCREEN, (75, 121, 147), inner.inflate(-110, -20), border_radius=12)
            if food:
                draw_image(SCREEN, "filled_drink" if food.stage == "ready" else "empty_drink", pygame.Rect(inner.centerx - 52, inner.y + 5, 104, 130))
                draw_text(SCREEN, f"FILL {int(station.fill * 100)}%", (station.rect.x + 24, station.rect.bottom - 48), SMALL, CREAM)
            else:
                draw_text(SCREEN, "DROP EMPTY CUP", inner.center, SMALL, MUTED, True)

    def draw_food_status(self, food, area, label):
        bar = pygame.Rect(area.x + 18, area.bottom - 34, area.width - 36, 14)
        pygame.draw.rect(SCREEN, (24, 27, 35), bar, border_radius=7)
        fill_color = RED if food.burning else (YELLOW if food.progress > 0.8 else ORANGE)
        pygame.draw.rect(SCREEN, fill_color, (bar.x, bar.y, int(bar.width * food.progress), bar.height), border_radius=7)
        text_color = RED if food.burning else (YELLOW if food.stage == "warning" else CREAM)
        status = "BURNING — BIN IT" if food.burning else (f"READY — {food.burn_flash:.1f}s" if food.stage in ("warning", "ready") and food.burn_flash > 0 else label)
        draw_text(SCREEN, status, (area.centerx, area.y + 15), SMALL, text_color, True)
        if food.stage == "warning" or (food.stage == "ready" and food.burn_flash > 0):
            pygame.draw.rect(SCREEN, RED, area, 3, border_radius=10)

    def draw_controls(self):
        pygame.draw.rect(SCREEN, PANEL_DARK, (38, 590, 1104, 138), border_radius=12)
        draw_text(SCREEN, self.message if self.message_timer > 0 else "Drag ingredients to cookers. Tap a cooker to flip or pick up food.", (58, 602), FONT, CREAM)
        sources = [("BURGER", "Burger"), ("CHIPS", "Chips"), ("DRINK", "Drink"), ("BUN", "Bun")]
        for index, (label, kind) in enumerate(sources):
            rect = pygame.Rect(58 + index * 135, 650, 118, 48)
            pygame.draw.rect(SCREEN, (64, 74, 92), rect, border_radius=7)
            pygame.draw.rect(SCREEN, ORANGE if self.drag_item == kind else (113, 124, 145), rect, 2 if self.drag_item == kind else 1, border_radius=7)
            image_key = {"Burger": "raw_burger", "Chips": "raw_chips", "Drink": "empty_drink", "Bun": "bun"}[kind]
            draw_image(SCREEN, image_key, pygame.Rect(rect.x + 4, rect.y + 4, 40, 40))
            draw_text(SCREEN, f"DRAG {label}", rect.center, SMALL, CREAM, True)
        fill_rect = pygame.Rect(608, 650, 130, 48)
        pygame.draw.rect(SCREEN, BLUE if self.filling else (64, 74, 92), fill_rect, border_radius=7)
        draw_text(SCREEN, "FILL DRINK", fill_rect.center, SMALL, CREAM, True)
        bin_rect = pygame.Rect(1042, 650, 65, 48)
        pygame.draw.rect(SCREEN, RED, bin_rect, border_radius=7)
        draw_text(SCREEN, "BIN", bin_rect.center, SMALL, CREAM, True)

    def source_rects(self):
        return [(pygame.Rect(58 + index * 135, 650, 118, 48), kind) for index, kind in enumerate(("Burger", "Chips", "Drink", "Bun"))]

    def click(self, pos):
        for index, rect in enumerate(self.storage_rects()):
            if rect.collidepoint(pos):
                if self.storage[index] and not self.held_item:
                    self.held_item = self.storage[index]
                    self.storage[index] = None
                    self.dragging = "held"
                    self.say("Stored item picked up. Drag it onto its order.")
                return
        for index, order in enumerate(self.orders):
            rect = pygame.Rect(295 + index * 259, 440, 245, 122)
            if rect.collidepoint(pos):
                self.selected_order = index
                self.say(f"Order #{order.number} selected: {order.label()}.")
                return
        for rect, kind in self.source_rects():
            if rect.collidepoint(pos):
                self.drag_item = kind
                self.dragging = "source"
                self.say(f"Drag the {kind.lower()} to its station or matching order.")
                return
        for station in self.stations:
            if station.rect.collidepoint(pos) and station.food:
                if station.kind == "hob" and not station.food.flipped and not station.food.burning:
                    self.action("flip")
                elif station.kind == "drink" and station.food.stage != "ready" and not station.food.burning:
                    self.say("Use the FILL DRINK button, then release at the target level.")
                else:
                    if self.take_from_station(station):
                        self.dragging = "held"
                return
        if pygame.Rect(608, 650, 130, 48).collidepoint(pos):
            drink = self.stations[2]
            if drink.food and not drink.food.burning and drink.food.stage != "ready":
                drink.food.stage = "filling"
                self.filling = True
                self.say("Filling... release near 80%.")
            else:
                self.say("Drag an empty cup to the drink filler first.")
            return
        if pygame.Rect(1042, 650, 65, 48).collidepoint(pos):
            self.action("bin")

    def run(self):
        while self.running:
            dt = min(CLOCK.tick(60) / 1000, 0.05)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self.running = False
                    elif event.key == pygame.K_RIGHT:
                        self.selected_order = min(len(self.orders) - 1, self.selected_order + 1)
                    elif event.key == pygame.K_LEFT:
                        self.selected_order = max(0, self.selected_order - 1)
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    self.click(self.to_game_pos(event.pos))
                elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                    pos = self.to_game_pos(event.pos)
                    if self.dragging == "source" and self.drag_item:
                        for station in self.stations:
                            if station.rect.collidepoint(pos):
                                self.drop_on_station(self.drag_item, station)
                                break
                        else:
                            for index, order in enumerate(self.orders):
                                ticket = pygame.Rect(295 + index * 259, 440, 245, 122)
                                if ticket.collidepoint(pos):
                                    self.selected_order = index
                                    self.drop_on_plate(self.drag_item)
                                    break
                        self.dragging = None
                        self.drag_item = None
                    elif self.dragging == "held" and self.held_item:
                        stored = False
                        for index, rect in enumerate(self.storage_rects()):
                            if rect.collidepoint(pos) and self.storage[index] is None:
                                self.storage[index] = self.held_item
                                self.held_item = None
                                stored = True
                                self.say("Item stored safely.")
                                break
                        if not stored:
                            for index, order in enumerate(self.orders):
                                ticket = pygame.Rect(295 + index * 259, 440, 245, 122)
                                if ticket.collidepoint(pos):
                                    self.selected_order = index
                                    self.drop_on_plate(self.held_item)
                                    break
                        self.dragging = None
                    self.filling = False
                    drink = self.stations[2]
                    if drink.food and drink.food.stage == "filling" and not drink.food.burning and drink.fill >= 0.9:
                        drink.fill = 1
                        drink.food.stage = "ready"
                        self.say("Drink filled! Pick it up and drag it onto its order.")

            if self.filling and pygame.mouse.get_pressed()[0]:
                station = self.stations[2]
                if station.food and not station.food.burning:
                    station.food.stage = "filling"
                    station.fill = clamp(station.fill + dt * 0.175, 0, 1)
            self.update(dt)
            self.draw()
        pygame.quit()
        sys.exit()


if __name__ == "__main__":
    KitchenRush().run()
