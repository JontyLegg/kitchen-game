import json
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
SAVE_DIR = os.path.join(os.path.dirname(__file__), "saves")
os.makedirs(SAVE_DIR, exist_ok=True)


def image(name):
    surface = pygame.image.load(os.path.join(IMAGE_DIR, name)).convert_alpha()
    width, height = surface.get_size()

    def is_background(x, y):
        r, g, b, a = surface.get_at((x, y))
        return a and min(r, g, b) > 210 and max(r, g, b) - min(r, g, b) < 18

    # Remove checkerboard/white pixels only when they are connected to the edge.
    # This keeps pale highlights inside food while cleaning the supplied assets.
    queue = deque()
    seen = set()
    for x in range(width):
        queue.extend(((x, 0), (x, height - 1)))
    for y in range(height):
        queue.extend(((0, y), (width - 1, y)))
    while queue:
        x, y = queue.popleft()
        if (x, y) in seen or not (0 <= x < width and 0 <= y < height) or not is_background(x, y):
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
    "board": image("chopping board.png"),
    "potato": image("potato.png"),
    "lettuce_raw": image("unchopped lettuce.png"),
    "lettuce": image("chopped lettuce.png"),
    "tomato_raw": image("unchopped tomato.png"),
    "tomato": image("chopped tomato.png"),
    "fire": image("fire for burnt food.png"),
}

FONT = pygame.font.SysFont("arial", 19)
SMALL = pygame.font.SysFont("arial", 15)
TITLE = pygame.font.SysFont("arial", 32, bold=True)
BIG = pygame.font.SysFont("arial", 22, bold=True)
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
    rendered = font.render(text, True, color)
    rect = rendered.get_rect(center=pos) if center else rendered.get_rect(topleft=pos)
    surface.blit(rendered, rect)


def draw_image(surface, key, rect):
    scaled = pygame.transform.smoothscale(IMAGES[key], rect.size)
    surface.blit(scaled, scaled.get_rect(center=rect.center))


def clamp(value, low, high):
    return max(low, min(high, value))


@dataclass
class Order:
    number: int
    items: list
    patience: float
    max_patience: float
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
    kind: str
    index: int
    rect: pygame.Rect = field(default_factory=pygame.Rect)
    food: Food | None = None
    fill: float = 0.0


class KitchenRush:
    def __init__(self):
        self.running = True
        self.paused = False
        self.save_dialog = None
        self.save_name = ""
        self.save_files = []
        self.money = 0
        self.served = 0
        self.missed = 0
        self.next_order = 1
        self.orders = []
        self.selected_order = 0
        self.message = "Drag ingredients to stations, then drag finished items onto their matching tickets."
        self.message_timer = 6.0
        self.spawn_timer = 0.0
        self.game_time = 0.0
        self.held_item = None
        self.drag_item = None
        self.dragging = None
        self.press_pos = None
        self.auto_click_pending = False
        self.storage = [None, None]
        self.filling = []
        self.chopping = False
        self.chop_unlocked = False
        self.hobs = [Station("hob", 0)]
        self.fryers = [Station("fryer", 0)]
        self.drinks = [Station("drink", 0)]
        self.board = Station("board", 0)
        self.refresh_layout()
        self.add_order()
        self.add_order()

    def refresh_layout(self):
        groups = [(self.hobs, 20), (self.fryers, 310), (self.drinks, 600)]
        for stations, x in groups:
            for station in stations:
                col = station.index % 2
                row = station.index // 2
                station.rect = pygame.Rect(x + col * 138, 125 + row * 112, 130, 102)
        self.board.rect = pygame.Rect(890, 125, 270, 214)

    def say(self, message, duration=3):
        self.message = message
        self.message_timer = duration

    def selected(self):
        if not self.orders:
            return None
        self.selected_order = clamp(self.selected_order, 0, len(self.orders) - 1)
        return self.orders[self.selected_order]

    def add_order(self):
        if not self.chop_unlocked:
            recipes = [["Burger"], ["Drink"], ["Burger", "Drink"]]
            items = random.choice(recipes)
        else:
            # Every burger gets a random topping combination after the first upgrade.
            burger_toppings = [[], ["Lettuce"], ["Tomato"], ["Lettuce", "Tomato"]]
            burger = ["Burger"] + random.choice(burger_toppings)
            recipes = [
                burger,
                burger + ["Drink"],
                burger + ["Chips"],
                burger + ["Chips", "Drink"],
                ["Chips"],
                ["Chips", "Drink"],
                ["Drink"],
            ]
            items = random.choice(recipes)
        patience = (58 + len(items) * 14) * 0.85
        self.orders.append(Order(self.next_order, items, patience, patience))
        self.next_order += 1
        self.sort_orders()

    def order_work(self, order):
        durations = {"Burger": 12.2, "Chips": 11.6, "Drink": 5.0, "Lettuce": 4.3, "Tomato": 4.3}
        return sum(durations[item] for item in order.items if item not in order.plated)

    def sort_orders(self):
        current = self.selected() if self.orders else None
        self.orders.sort(key=lambda order: (self.order_work(order), order.number))
        if current in self.orders:
            self.selected_order = self.orders.index(current)
        else:
            self.selected_order = min(self.selected_order, max(0, len(self.orders) - 1))

    def stations(self):
        result = self.hobs + self.fryers + self.drinks
        if self.chop_unlocked:
            result.append(self.board)
        return result

    def food_image(self, kind, cooked=False):
        return {
            "Burger": "cooked_burger" if cooked else "raw_burger",
            "Chips": "cooked_chips" if cooked else "raw_chips",
            "Drink": "filled_drink" if cooked else "empty_drink",
            "Bun": "bun",
            "Potato": "potato",
            "Lettuce": "lettuce" if cooked else "lettuce_raw",
            "Tomato": "tomato" if cooked else "tomato_raw",
            "Chopped Lettuce": "lettuce",
            "Chopped Tomato": "tomato",
        }[kind]

    def source_rects(self):
        sources = [("Burger", "raw_burger"), ("Bun", "bun"), ("Drink", "empty_drink")]
        if self.chop_unlocked:
            sources += [("Potato", "potato"), ("Lettuce", "lettuce_raw"), ("Tomato", "tomato_raw")]
        return [(pygame.Rect(20 + i * 112, 665, 102, 58), kind, key) for i, (kind, key) in enumerate(sources)]

    def storage_rects(self):
        return [pygame.Rect(430, 12, 76, 68), pygame.Rect(515, 12, 76, 68)]

    def ticket_rect(self, index):
        return pygame.Rect(20 + (index % 4) * 290, 365 + (index // 4) * 92, 278, 82)

    def fill_rect(self, station):
        return pygame.Rect(station.rect.x + 8, station.rect.bottom - 30, station.rect.width - 16, 22)

    def flip_rect(self, station):
        return pygame.Rect(station.rect.x + 34, station.rect.bottom - 30, 62, 22)

    def chop_rect(self):
        return pygame.Rect(self.board.rect.x + 72, self.board.rect.bottom - 32, 126, 24)

    def all_upgrade_rects(self):
        return {
            "chop": pygame.Rect(692, 665, 145, 30),
            "hob": pygame.Rect(692, 700, 145, 30),
            "fryer": pygame.Rect(845, 665, 145, 30),
            "drink": pygame.Rect(845, 700, 145, 30),
        }

    def pause_rect(self):
        return pygame.Rect(1090, 14, 78, 40)

    def has_affordable_upgrade(self):
        return (
            (not self.chop_unlocked and self.money >= 50)
            or (len(self.hobs) < 4 and self.money >= len(self.hobs) * 100)
            or (len(self.fryers) < 4 and self.money >= len(self.fryers) * 100)
            or (len(self.drinks) < 4 and self.money >= len(self.drinks) * 125)
        )

    def save_game(self, name):
        safe = "".join(char for char in name.strip() if char.isalnum() or char in "-_ ").strip()
        if not safe:
            safe = "kitchen_run"
        data = {
            "money": self.money,
            "served": self.served,
            "missed": self.missed,
            "next_order": self.next_order,
            "selected_order": self.selected_order,
            "chop_unlocked": self.chop_unlocked,
            "orders": [order.__dict__ for order in self.orders],
            "storage": self.storage,
            "hobs": self.serialize_stations(self.hobs),
            "fryers": self.serialize_stations(self.fryers),
            "drinks": self.serialize_stations(self.drinks),
            "board": self.serialize_stations([self.board])[0],
        }
        with open(os.path.join(SAVE_DIR, safe + ".json"), "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2)
        self.save_dialog = None
        self.save_name = ""
        pygame.key.stop_text_input()
        self.say(f"Saved run as {safe}.")

    def serialize_stations(self, stations):
        result = []
        for station in stations:
            result.append({"kind": station.kind, "index": station.index, "fill": station.fill, "food": station.food.__dict__ if station.food else None})
        return result

    def load_game(self, filename):
        with open(os.path.join(SAVE_DIR, filename), "r", encoding="utf-8") as handle:
            data = json.load(handle)
        self.money = data["money"]
        self.served = data["served"]
        self.missed = data["missed"]
        self.next_order = data["next_order"]
        self.selected_order = data["selected_order"]
        self.chop_unlocked = data["chop_unlocked"]
        self.orders = [Order(**order) for order in data["orders"]]
        self.storage = data.get("storage", [None, None])
        self.hobs = self.restore_stations(data["hobs"])
        self.fryers = self.restore_stations(data["fryers"])
        self.drinks = self.restore_stations(data["drinks"])
        self.board = self.restore_stations([data["board"]])[0]
        self.held_item = None
        self.drag_item = None
        self.dragging = None
        self.filling.clear()
        self.chopping = False
        self.refresh_layout()
        self.save_dialog = None
        self.save_name = ""
        pygame.key.stop_text_input()
        self.say(f"Loaded {filename[:-5]}.")

    def restore_stations(self, entries):
        stations = []
        for entry in entries:
            station = Station(entry["kind"], entry["index"], fill=entry.get("fill", 0))
            station.food = Food(**entry["food"]) if entry.get("food") else None
            stations.append(station)
        return stations

    def reward(self, order):
        values = {"Burger": 11, "Chips": 9, "Drink": 6, "Lettuce": 1, "Tomato": 1}
        return sum(values[item] for item in order.items)

    def delivered_reward(self, order):
        values = {"Burger": 11, "Chips": 9, "Drink": 6, "Lettuce": 1, "Tomato": 1}
        return sum(values[item] for item in order.plated)

    def buy(self, kind):
        counts = {"hob": len(self.hobs), "fryer": len(self.fryers), "drink": len(self.drinks)}
        if kind == "chop":
            cost = 50
            if self.chop_unlocked:
                self.say("The chopping board is already unlocked.")
                return
        else:
            base = {"hob": 100, "fryer": 100, "drink": 125}[kind]
            cost = base * counts[kind]
            if counts[kind] >= 4:
                self.say(f"You already have the maximum number of {kind} slots.")
                return
        if self.money < cost:
            self.say(f"You need {cost}c for that upgrade. You have {self.money}c.")
            return
        self.money -= cost
        if kind == "chop":
            self.chop_unlocked = True
            self.say("Chopping board unlocked: lettuce, tomato, and potatoes are now available!")
        elif kind == "hob":
            self.hobs.append(Station("hob", len(self.hobs)))
            self.say("Another hob installed.")
        elif kind == "fryer":
            self.fryers.append(Station("fryer", len(self.fryers)))
            self.say("Another fryer installed.")
        else:
            self.drinks.append(Station("drink", len(self.drinks)))
            self.say("Another drink slot installed.")
        self.refresh_layout()

    def take_station(self, station):
        if not station.food:
            return False
        if station.food.burning:
            item = {"kind": station.food.kind, "burnt": True}
        elif station.kind == "drink" and station.food.stage != "ready":
            self.say("Finish filling the drink between 90% and 100% first.")
            return False
        elif station.food.stage != "ready":
            self.say("That item is still being prepared.")
            return False
        else:
            cooked = station.kind != "board"
            item = {"kind": station.food.kind, "burnt": False, "cooked": cooked}
        station.food = None
        station.fill = 0
        self.held_item = item
        self.dragging = "held"
        self.say("Item picked up. Drag it to an order, storage, or BIN.")
        return True

    def drop_on_station(self, item, station):
        if station.food:
            self.say("That station slot is occupied.")
            return False
        kind = item["kind"] if isinstance(item, dict) else item
        accepted = {"hob": "Burger", "fryer": "Chips", "drink": "Drink", "board": {"Potato", "Lettuce", "Tomato"}}
        if station.kind == "board":
            if not self.chop_unlocked or kind not in accepted["board"]:
                self.say("That ingredient cannot go on the chopping board.")
                return False
        elif kind != accepted[station.kind]:
            self.say(f"That item does not belong in this {station.kind} slot.")
            return False
        station.food = Food(kind)
        station.fill = 0
        self.say(f"{kind} placed on the {station.kind}.")
        self.drag_item = None
        self.held_item = None
        return True

    def drop_on_order(self, item, order):
        if item.get("burnt"):
            self.say("Burnt food can only go in the BIN.")
            return False
        kind = item["kind"]
        if kind == "Chips" and not item.get("cooked", False):
            self.say("Those chips are uncooked. Fry them before delivering them.")
            return False
        if kind == "Bun":
            if "Burger" not in order.items:
                self.say("That order does not need a bun.")
                return False
            if order.has_bun:
                self.say("That order already has a bun.")
                return False
            order.has_bun = True
        else:
            delivered_kind = {"Chopped Lettuce": "Lettuce", "Chopped Tomato": "Tomato"}.get(kind, kind)
            if delivered_kind not in order.items:
                self.say(f"Order #{order.number} does not need {kind.lower()}.")
                return False
            if delivered_kind == "Burger" and not order.has_bun:
                self.say("Add the bun before adding the burger.")
                return False
            if delivered_kind in order.plated:
                self.say(f"Order #{order.number} already has {delivered_kind.lower()}.")
                return False
            order.plated.append(delivered_kind)
        self.held_item = None
        self.dragging = None
        if set(order.items).issubset(set(order.plated)) and ("Burger" not in order.items or order.has_bun):
            self.complete_order(order)
        else:
            self.say(f"Added to order #{order.number}.")
        self.sort_orders()
        return True

    def complete_order(self, order):
        reward = self.reward(order)
        self.money += reward
        self.served += 1
        self.say(f"Order #{order.number} served automatically! +{reward}c")
        self.orders.remove(order)
        self.selected_order = min(self.selected_order, max(0, len(self.orders) - 1))
        if len(self.orders) < 3:
            self.add_order()

    def auto_route(self, item):
        """Send a clicked item to the next valid station or waiting order."""
        kind = item["kind"] if isinstance(item, dict) else item
        if isinstance(item, str):
            if kind == "Burger":
                for station in self.hobs:
                    if not station.food:
                        return self.drop_on_station(item, station)
            elif kind == "Drink":
                for station in self.drinks:
                    if not station.food:
                        return self.drop_on_station(item, station)
            elif kind in {"Potato", "Lettuce", "Tomato"}:
                if not self.board.food and self.chop_unlocked:
                    return self.drop_on_station(item, self.board)
            elif kind == "Bun":
                for order in self.orders:
                    if "Burger" in order.items and not order.has_bun:
                        return self.drop_on_order({"kind": "Bun", "burnt": False}, order)
        else:
            if kind == "Chips" and not item.get("cooked", False):
                for station in self.fryers:
                    if not station.food:
                        return self.drop_on_station(item, station)
            elif kind in {"Burger", "Chips", "Drink", "Chopped Lettuce", "Chopped Tomato"}:
                for order in self.orders:
                    needed = {"Chopped Lettuce": "Lettuce", "Chopped Tomato": "Tomato"}.get(kind, kind)
                    if needed in order.items and needed not in order.plated and (kind != "Burger" or order.has_bun):
                        return self.drop_on_order(item, order)
        self.say(f"There is no valid next place for the {kind.lower()}.")
        return False

    def bin_item(self):
        if self.held_item:
            self.held_item = None
            self.dragging = None
            self.say("Item binned.")
        else:
            self.say("Drag an item onto the BIN.")

    def update(self, dt):
        self.game_time += dt
        self.message_timer = max(0, self.message_timer - dt)
        self.spawn_timer += dt
        if self.spawn_timer > 16 and len(self.orders) < 4:
            self.spawn_timer = 0
            self.add_order()
        for order in self.orders[:]:
            order.patience -= dt
            if order.patience <= 0:
                partial = self.delivered_reward(order)
                self.money += partial - 10
                self.orders.remove(order)
                self.missed += 1
                self.selected_order = min(self.selected_order, max(0, len(self.orders) - 1))
                self.say(f"Order #{order.number} walked out: +{partial}c delivered, -10c penalty.")

        for station in self.drinks:
            if station in self.filling and station.food and not station.food.burning:
                station.fill += dt * 0.20125
                station.food.stage = "filling"
                if station.fill > 1:
                    station.food.burning = True
                    if station in self.filling:
                        self.filling.remove(station)
                    self.say("That drink overflowed. Drag it into the BIN.")
        if self.chopping and self.board.food:
            self.board.food.progress += dt / 4.3
            self.board.food.stage = "chopping"
            if self.board.food.progress >= 1:
                result = {"Potato": "Chips", "Lettuce": "Chopped Lettuce", "Tomato": "Chopped Tomato"}[self.board.food.kind]
                self.board.food.kind = result
                self.board.food.stage = "ready"
                self.chopping = False
                self.say(f"{result} chopped and ready to drag.")

    def update_progress(self, dt):
        for station in self.hobs:
            if not station.food or station.food.burning:
                continue
            food = station.food
            if food.stage == "raw":
                food.progress += dt * 0.165
                if food.progress >= 1:
                    food.progress = 1
                    food.stage = "ready"
                    food.burn_flash = 3
                    self.say("Burger ready — flip it now!" if not food.flipped else "Burger cooked — take it off now!", 3)
            elif food.stage == "ready":
                food.burn_flash -= dt
                if food.burn_flash <= 0:
                    food.burning = True
                    self.say("Burger burned. Drag it into the BIN.")
        for station in self.fryers:
            if not station.food or station.food.burning:
                continue
            food = station.food
            if food.stage == "raw":
                food.progress += dt * 0.138
                if food.progress >= 1:
                    food.progress = 1
                    food.stage = "ready"
                    food.burn_flash = 3
                    self.say("Chips ready — take them out now!", 3)
            elif food.stage == "ready":
                food.burn_flash -= dt
                if food.burn_flash <= 0:
                    food.burning = True
                    self.say("Chips burned. Drag them into the BIN.")

    def draw(self):
        SCREEN.fill(BG)
        draw_text(SCREEN, "KITCHEN RUSH", (20, 16), TITLE)
        draw_text(SCREEN, "STARTER KITCHEN", (22, 54), SMALL, MUTED)
        draw_text(SCREEN, f"MONEY  {self.money}c", (750, 20), BIG, YELLOW)
        draw_text(SCREEN, f"SERVED {self.served}   WALKED OUT {self.missed}", (750, 52), SMALL, MUTED)
        pygame.draw.rect(SCREEN, BLUE if self.paused else (64, 74, 92), self.pause_rect(), border_radius=6)
        draw_text(SCREEN, "RESUME" if self.paused else "PAUSE", self.pause_rect().center, SMALL, CREAM, True)
        if not self.paused and self.has_affordable_upgrade():
            pygame.draw.circle(SCREEN, RED, (1078, 14), 9)
            draw_text(SCREEN, "!", (1078, 14), SMALL, CREAM, True)
        self.draw_storage()
        self.draw_group(self.hobs, "HOBS", 20)
        self.draw_group(self.fryers, "DEEP FAT FRYERS", 310)
        self.draw_group(self.drinks, "DRINK FILLERS", 600)
        self.draw_board()
        self.draw_orders()
        self.draw_controls()
        if self.paused:
            self.draw_pause_menu()
        if self.drag_item or self.held_item:
            mouse = self.to_game(pygame.mouse.get_pos())
            kind = self.drag_item or self.held_item["kind"]
            draw_image(SCREEN, self.food_image(kind, bool(self.held_item)), pygame.Rect(mouse[0] - 35, mouse[1] - 35, 70, 70))
        scaled = pygame.transform.smoothscale(SCREEN, DISPLAY.get_size())
        DISPLAY.blit(scaled, (0, 0))
        pygame.display.flip()

    def pause_upgrade_rects(self):
        return {
            "chop": pygame.Rect(300, 350, 250, 38),
            "hob": pygame.Rect(570, 350, 250, 38),
            "fryer": pygame.Rect(300, 400, 250, 38),
            "drink": pygame.Rect(570, 400, 250, 38),
        }

    def draw_pause_menu(self):
        overlay = pygame.Surface(SCREEN.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 185))
        SCREEN.blit(overlay, (0, 0))
        panel = pygame.Rect(220, 80, 740, 610)
        pygame.draw.rect(SCREEN, PANEL, panel, border_radius=14)
        pygame.draw.rect(SCREEN, BLUE, panel, 2, border_radius=14)
        draw_text(SCREEN, "PAUSED", (panel.centerx, 112), TITLE, CREAM, True)
        draw_text(SCREEN, "Nothing is cooking, filling, chopping, or leaving while paused.", (panel.centerx, 145), SMALL, MUTED, True)
        buttons = [(pygame.Rect(285, 180, 180, 40), "SAVE RUN"), (pygame.Rect(480, 180, 180, 40), "OPEN SAVE"), (pygame.Rect(675, 180, 180, 40), "RESUME")]
        for rect, label in buttons:
            pygame.draw.rect(SCREEN, (64, 74, 92), rect, border_radius=6)
            draw_text(SCREEN, label, rect.center, SMALL, CREAM, True)
        draw_text(SCREEN, "UPGRADES", (panel.centerx, 300), BIG, YELLOW, True)
        labels = {"chop": "CHOP BOARD + POTATO 50c", "hob": f"HOB SLOT {len(self.hobs) * 100}c", "fryer": f"FRYER SLOT {len(self.fryers) * 100}c", "drink": f"DRINK SLOT {len(self.drinks) * 125}c"}
        for key, rect in self.pause_upgrade_rects().items():
            pygame.draw.rect(SCREEN, BLUE if key == "chop" and self.chop_unlocked else (64, 74, 92), rect, border_radius=6)
            draw_text(SCREEN, labels[key], rect.center, SMALL, CREAM, True)
        files = sorted(name for name in os.listdir(SAVE_DIR) if name.endswith(".json"))
        draw_text(SCREEN, "SAVES: " + (", ".join(name[:-5] for name in files) if files else "none yet"), (panel.x + 65, 480), SMALL, MUTED)
        if self.save_dialog == "save":
            pygame.draw.rect(SCREEN, PANEL_DARK, pygame.Rect(300, 515, 580, 95), border_radius=8)
            draw_text(SCREEN, "SAVE NAME (type, then press ENTER):", (320, 530), SMALL, CREAM)
            pygame.draw.rect(SCREEN, BG, pygame.Rect(320, 555, 540, 35), border_radius=5)
            draw_text(SCREEN, self.save_name + "_", (330, 563), FONT, CREAM)
        elif self.save_dialog == "load":
            pygame.draw.rect(SCREEN, PANEL_DARK, pygame.Rect(300, 515, 580, 95), border_radius=8)
            draw_text(SCREEN, "CLICK A SAVE FILE TO LOAD:", (320, 530), SMALL, CREAM)
            for i, name in enumerate(files[:4]):
                rect = pygame.Rect(320 + i * 130, 560, 120, 30)
                pygame.draw.rect(SCREEN, (64, 74, 92), rect, border_radius=5)
                draw_text(SCREEN, name[:-5][:16], rect.center, SMALL, CREAM, True)

    def draw_storage(self):
        draw_text(SCREEN, "STORAGE", (430, 2), SMALL, MUTED)
        for i, rect in enumerate(self.storage_rects()):
            pygame.draw.rect(SCREEN, PANEL, rect, border_radius=8)
            pygame.draw.rect(SCREEN, ORANGE if self.storage[i] else (77, 87, 108), rect, 2, border_radius=8)
            if self.storage[i]:
                draw_image(SCREEN, self.food_image(self.storage[i]["kind"], True), rect.inflate(-12, -12))
            else:
                draw_text(SCREEN, str(i + 1), rect.center, SMALL, MUTED, True)

    def draw_group(self, stations, title, x):
        rect = pygame.Rect(x, 92, 280, 242)
        pygame.draw.rect(SCREEN, PANEL_DARK, rect, border_radius=10)
        draw_text(SCREEN, title, (x + 10, 98), BIG, CREAM)
        for station in stations:
            pygame.draw.rect(SCREEN, PANEL, station.rect, border_radius=8)
            pygame.draw.rect(SCREEN, ORANGE if station.food else (77, 87, 108), station.rect, 2, border_radius=8)
            food = station.food
            if station.kind == "hob":
                draw_image(SCREEN, "pan", pygame.Rect(station.rect.x + 26, station.rect.y + 5, 78, 70))
                if food:
                    draw_image(SCREEN, "cooked_burger" if food.stage == "ready" else "raw_burger", pygame.Rect(station.rect.x + 42, station.rect.y + 25, 48, 40))
                    if food.burning:
                        draw_image(SCREEN, "fire", station.rect.inflate(-12, -12))
                    if food.stage == "ready" and not food.flipped:
                        pygame.draw.rect(SCREEN, ORANGE, self.flip_rect(station), border_radius=5)
                        draw_text(SCREEN, "FLIP", self.flip_rect(station).center, SMALL, BG, True)
            elif station.kind == "fryer":
                if food:
                    draw_image(SCREEN, "cooked_chips" if food.stage == "ready" else "raw_chips", pygame.Rect(station.rect.x + 16, station.rect.y + 16, 98, 55))
                    if food.burning:
                        draw_image(SCREEN, "fire", station.rect.inflate(-12, -12))
                else:
                    draw_text(SCREEN, "DROP CHIPS", station.rect.center, SMALL, MUTED, True)
            else:
                if food:
                    draw_image(SCREEN, "filled_drink" if food.stage == "ready" else "empty_drink", pygame.Rect(station.rect.x + 42, station.rect.y + 4, 46, 62))
                    if food.burning:
                        draw_image(SCREEN, "fire", station.rect.inflate(-12, -12))
                    pygame.draw.rect(SCREEN, BLUE if station in self.filling else (64, 74, 92), self.fill_rect(station), border_radius=5)
                    draw_text(SCREEN, "FILL", self.fill_rect(station).center, SMALL, CREAM, True)
                else:
                    draw_text(SCREEN, "DROP CUP", station.rect.center, SMALL, MUTED, True)
            if food and station.kind != "drink":
                self.draw_bar(food, station.rect)
            elif food and station.kind == "drink":
                draw_text(SCREEN, f"{int(station.fill * 100)}%", (station.rect.x + 8, station.rect.y + 76), SMALL, CREAM)

    def draw_board(self):
        rect = self.board.rect
        pygame.draw.rect(SCREEN, PANEL_DARK, rect, border_radius=10)
        draw_text(SCREEN, "CHOPPING BOARD", (rect.x + 10, rect.y + 6), BIG, CREAM)
        if not self.chop_unlocked:
            draw_text(SCREEN, "LOCKED — BUY UPGRADE", rect.center, FONT, MUTED, True)
            return
        draw_image(SCREEN, "board", pygame.Rect(rect.x + 18, rect.y + 32, rect.width - 36, 120))
        if self.board.food:
            draw_image(SCREEN, self.food_image(self.board.food.kind), pygame.Rect(rect.x + 95, rect.y + 50, 80, 65))
            self.draw_bar(self.board.food, rect)
            pygame.draw.rect(SCREEN, BLUE if self.chopping else (64, 74, 92), self.chop_rect(), border_radius=5)
            draw_text(SCREEN, "HOLD CHOP", self.chop_rect().center, SMALL, CREAM, True)
        else:
            draw_text(SCREEN, "DROP POTATO / LETTUCE / TOMATO", rect.center, SMALL, MUTED, True)

    def draw_bar(self, food, rect):
        bar = pygame.Rect(rect.x + 8, rect.bottom - 20, rect.width - 16, 10)
        pygame.draw.rect(SCREEN, PANEL_DARK, bar, border_radius=5)
        pygame.draw.rect(SCREEN, RED if food.burning else (YELLOW if food.stage == "ready" else ORANGE), (bar.x, bar.y, int(bar.width * min(1, food.progress)), bar.height), border_radius=5)
        if food.burning:
            draw_text(SCREEN, "BURNING — DRAG TO BIN", (rect.centerx, rect.y + 5), SMALL, RED, True)
        elif food.stage == "ready":
            draw_text(SCREEN, f"READY {food.burn_flash:.1f}s", (rect.centerx, rect.y + 5), SMALL, YELLOW, True)

    def draw_orders(self):
        draw_text(SCREEN, "CUSTOMER ORDERS — DROP ITEMS DIRECTLY ONTO THE RIGHT ORDER", (20, 344), BIG, CREAM)
        for i, order in enumerate(self.orders):
            rect = self.ticket_rect(i)
            needed = set(order.items)
            supplied = set(order.plated)
            complete = needed.issubset(supplied) and ("Burger" not in needed or order.has_bun)
            partial = bool(needed & supplied) or ("Burger" in needed and order.has_bun)
            outline = GREEN if complete else ORANGE if partial else RED
            pygame.draw.rect(SCREEN, PANEL, rect, border_radius=8)
            pygame.draw.rect(SCREEN, outline, rect, 3, border_radius=8)
            draw_text(SCREEN, f"#{order.number}  {order.label()}", (rect.x + 9, rect.y + 7), SMALL, CREAM)
            delivered = (["Burger"] if "Burger" in order.plated else (["Bun"] if order.has_bun else [])) + [x for x in order.plated if x != "Burger"]
            for n, item in enumerate(delivered[:4]):
                item_key = "burger" if item == "Burger" else self.food_image(item, True)
                draw_image(SCREEN, item_key, pygame.Rect(rect.x + 10 + n * 38, rect.y + 28, 30, 25))
            pygame.draw.rect(SCREEN, PANEL_DARK, (rect.x + 10, rect.bottom - 13, rect.width - 20, 7), border_radius=4)
            pygame.draw.rect(SCREEN, GREEN if order.patience > 35 else RED, (rect.x + 10, rect.bottom - 13, int((rect.width - 20) * order.patience / order.max_patience), 7), border_radius=4)

    def draw_controls(self):
        pygame.draw.rect(SCREEN, PANEL_DARK, (20, 570, 1140, 180), border_radius=10)
        draw_text(SCREEN, self.message if self.message_timer > 0 else "Drag items between stations, storage, BIN, and matching orders.", (35, 580), SMALL, CREAM)
        for rect, kind, key in self.source_rects():
            pygame.draw.rect(SCREEN, PANEL, rect, border_radius=6)
            draw_image(SCREEN, key, pygame.Rect(rect.x + 3, rect.y + 4, 42, 48))
            draw_text(SCREEN, kind.upper(), (rect.x + 48, rect.y + 21), SMALL, CREAM)
        pygame.draw.rect(SCREEN, RED, pygame.Rect(1060, 665, 80, 58), border_radius=7)
        draw_text(SCREEN, "BIN", (1100, 694), BIG, CREAM, True)
        draw_text(SCREEN, "Press P or click PAUSE to buy upgrades and save/load a run.", (692, 675), SMALL, MUTED)
        draw_text(SCREEN, "P = pause", (692, 704), SMALL, MUTED)

    def to_game(self, pos):
        return int(pos[0] * 1180 / DISPLAY.get_width()), int(pos[1] * 760 / DISPLAY.get_height())

    def click(self, pos):
        self.auto_click_pending = False
        if self.save_dialog == "load":
            files = sorted(name for name in os.listdir(SAVE_DIR) if name.endswith(".json"))
            for i, filename in enumerate(files[:4]):
                if pygame.Rect(320 + i * 130, 560, 120, 30).collidepoint(pos):
                    self.load_game(filename)
                    return
            return
        if self.save_dialog == "save":
            return
        if self.pause_rect().collidepoint(pos):
            self.paused = not self.paused
            return
        if self.paused:
            if pygame.Rect(285, 180, 180, 40).collidepoint(pos):
                self.save_dialog = "save"
                self.save_name = ""
                pygame.key.start_text_input()
                return
            if pygame.Rect(480, 180, 180, 40).collidepoint(pos):
                self.save_dialog = "load"
                return
            if pygame.Rect(675, 180, 180, 40).collidepoint(pos):
                self.paused = False
                return
            for key, rect in self.pause_upgrade_rects().items():
                if rect.collidepoint(pos):
                    self.buy(key)
                    return
            return
        if self.held_item:
            self.dragging = "held"
        for i, rect in enumerate(self.storage_rects()):
            if rect.collidepoint(pos):
                if self.storage[i] and not self.held_item:
                    self.held_item = self.storage[i]
                    self.storage[i] = None
                    self.dragging = "held"
                    self.auto_click_pending = True
                return
        for i, order in enumerate(self.orders):
            if self.ticket_rect(i).collidepoint(pos):
                self.selected_order = i
                self.say(f"Order #{order.number} selected.")
                return
        for rect, kind, _ in self.source_rects():
            if rect.collidepoint(pos):
                self.drag_item = kind
                self.dragging = "source"
                self.auto_click_pending = True
                return
        if pygame.Rect(1060, 665, 80, 58).collidepoint(pos):
            self.bin_item()
            return
        if self.chop_unlocked and self.chop_rect().collidepoint(pos) and self.board.food and self.board.food.stage != "ready":
            self.chopping = True
            self.say("Chopping... keep holding.")
            return
        for station in self.stations():
            if station.rect.collidepoint(pos) and station.food:
                if station.food.burning:
                    self.take_station(station)
                elif station.kind == "hob" and not station.food.flipped:
                    if station.food.stage == "ready":
                        station.food.flipped = True
                        station.food.stage = "raw"
                        station.food.progress = 0
                        station.food.burn_flash = 0
                        self.say("Burger flipped. Cook the second side.")
                    else:
                        self.say("Wait until the burger is ready before flipping it.")
                elif station.kind == "drink" and self.fill_rect(station).collidepoint(pos) and station.food.stage != "ready":
                    self.filling = [drink for drink in self.drinks if drink.food and not drink.food.burning and drink.food.stage != "ready"]
                    self.say("Filling all drink slots... release between 90% and 100%.")
                else:
                    if self.take_station(station):
                        self.auto_click_pending = True
                return

    def release(self, pos):
        is_click = self.press_pos is not None and pygame.Vector2(pos).distance_to(self.press_pos) < 10
        if self.dragging == "source" and self.drag_item:
            kind = self.drag_item
            if is_click and self.auto_click_pending:
                self.auto_route(kind)
                self.drag_item = None
                self.dragging = None
                self.auto_click_pending = False
                self.press_pos = None
                self.chopping = False
                self.filling.clear()
                return
            handled = False
            for station in self.stations():
                if station.rect.collidepoint(pos) and self.drop_on_station(kind, station):
                    handled = True
                    break
            if not handled and kind == "Bun":
                for i, order in enumerate(self.orders):
                    if self.ticket_rect(i).collidepoint(pos):
                        self.selected_order = i
                        self.drop_on_order({"kind": "Bun", "burnt": False}, order)
                        handled = True
                        break
            self.drag_item = None
            self.dragging = None
        elif self.dragging == "held" and self.held_item:
            if is_click and self.auto_click_pending:
                self.auto_route(self.held_item)
                self.dragging = "held" if self.held_item else None
                self.auto_click_pending = False
                self.press_pos = None
                self.chopping = False
                self.filling.clear()
                return
            handled = False
            for station in self.stations():
                if station.rect.collidepoint(pos) and self.drop_on_station(self.held_item, station):
                    handled = True
                    break
            for i, rect in enumerate(self.storage_rects()):
                if not handled and rect.collidepoint(pos) and self.storage[i] is None:
                    self.storage[i] = self.held_item
                    self.held_item = None
                    handled = True
                    self.say("Item stored safely.")
                    break
            if not handled and pygame.Rect(1060, 665, 80, 58).collidepoint(pos):
                self.bin_item()
                handled = True
            if not handled:
                for i, order in enumerate(self.orders):
                    if self.ticket_rect(i).collidepoint(pos):
                        self.selected_order = i
                        handled = self.drop_on_order(self.held_item, order)
                        break
            self.dragging = "held" if self.held_item else None
        self.chopping = False
        self.filling.clear()
        self.auto_click_pending = False
        self.press_pos = None
        for station in self.drinks:
            if station.food and station.food.stage == "filling" and not station.food.burning:
                if 0.9 <= station.fill <= 1:
                    station.food.stage = "ready"
                    self.say("Drink filled and ready to drag.")
                else:
                    station.food.stage = "raw"
                    self.say("Drink paused below 90%. Hold FILL again to continue.")

    def run(self):
        while self.running:
            dt = min(CLOCK.tick(60) / 1000, 0.05)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.TEXTINPUT and self.save_dialog == "save":
                    self.save_name += event.text
                elif event.type == pygame.KEYDOWN:
                    if self.save_dialog == "save":
                        if event.key == pygame.K_RETURN:
                            self.save_game(self.save_name)
                        elif event.key == pygame.K_BACKSPACE:
                            self.save_name = self.save_name[:-1]
                        elif event.key == pygame.K_ESCAPE:
                            self.save_dialog = None
                            self.save_name = ""
                            pygame.key.stop_text_input()
                        continue
                    if event.key == pygame.K_p:
                        self.paused = not self.paused
                        continue
                    if event.key == pygame.K_ESCAPE:
                        self.running = False
                    elif not self.paused and event.key == pygame.K_RIGHT:
                        self.selected_order = min(len(self.orders) - 1, self.selected_order + 1)
                    elif not self.paused and event.key == pygame.K_LEFT:
                        self.selected_order = max(0, self.selected_order - 1)
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    self.press_pos = self.to_game(event.pos)
                    self.click(self.press_pos)
                elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                    if not self.paused:
                        self.release(self.to_game(event.pos))
            if not self.paused:
                self.update_progress(dt)
                self.update(dt)
            self.draw()
        pygame.quit()
        sys.exit()


if __name__ == "__main__":
    KitchenRush().run()
