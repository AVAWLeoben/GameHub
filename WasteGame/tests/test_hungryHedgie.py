"""Behavior checks for the Hungry Hedgie quality pass.

Run from the folder containing hungryHedgie.py:
    SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python -m unittest discover -s tests -v

The suite needs pygame (or pygame-ce); everything else is the standard library.
"""
import asyncio
import copy
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame
import hungryHedgie as hedgie


class MemoryStore:
    def __init__(self, data=None):
        self.data = data or {}

    def load(self):
        return copy.deepcopy(self.data)

    def save(self, data):
        self.data = copy.deepcopy(data)
        return True


class GameChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def setUp(self):
        self.screen = pygame.display.set_mode((800, 600))
        pygame.event.clear()
        self.store = MemoryStore()
        self.game = hedgie.HedgieGame(self.screen, storage=self.store)
        self.start(self.game)

    @staticmethod
    def start(game):
        game.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN,
                                            pos=game.ACTION.center, button=1))
        game.handle_event(pygame.event.Event(pygame.MOUSEBUTTONUP,
                                            pos=game.ACTION.center, button=1))

    @staticmethod
    def click(game, pos):
        game.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pos, button=1))
        game.handle_event(pygame.event.Event(pygame.MOUSEBUTTONUP, pos=pos, button=1))

    def assert_food_conserved(self, game):
        self.assertGreaterEqual(game.carrying, 0)
        self.assertLessEqual(game.carrying, game.capacity)
        self.assertGreaterEqual(game.delivered, 0)
        self.assertLessEqual(game.delivered, game.stage["goal"])
        remaining = sum(b["active"] for b in game.berries)
        self.assertEqual(remaining + game.carrying + game.delivered, game.stage["goal"])

    def advance(self, game, seconds, fps=60):
        for _ in range(round(seconds * fps)):
            game.tick(1 / fps)
            self.assert_food_conserved(game)

    def test_one_pickup_is_one_berry_and_cannot_be_collected_twice(self):
        game = self.game
        game.pos = game.berries[0]["pos"].copy()
        game.target = game.pos.copy()
        self.advance(game, 0.4)
        self.assertEqual(game.carrying, 1)

    def test_basket_capacity_keeps_excess_food_in_the_field(self):
        game = self.game
        for berry in game.berries[:game.capacity + 1]:
            game.pos = berry["pos"].copy()
            game.target = game.pos.copy()
            game.tick(1 / 60)
        self.assertEqual(game.carrying, game.capacity)
        self.assertTrue(game.berries[game.capacity]["active"])
        self.assert_food_conserved(game)

    def test_delivery_is_counted_once_without_negative_carried_food(self):
        game = self.game
        for berry in game.berries[:3]:
            game.pos = berry["pos"].copy()
            game.target = game.pos.copy()
            game.tick(1 / 60)
        game.pos.update(651, 302)
        game.target = game.pos.copy()
        self.advance(game, 4)
        self.assertEqual((game.carrying, game.delivered), (0, 3))
        self.assertEqual(game.flows, [])
        self.assert_food_conserved(game)

    def test_complete_adventure_by_tapping_and_walking(self):
        game = self.game
        deliveries = 0
        previous_delivered = 0
        for stage in range(3):
            for frame in range(12000):
                if game.state != "play":
                    break
                if game.delivery_time <= 0:
                    if game.carrying == game.capacity or (
                            game.carrying and not any(b["active"] for b in game.berries)):
                        self.click(game, (651, 302))
                    else:
                        active = [b for b in game.berries if b["active"]]
                        if active:
                            berry = min(active, key=lambda b: game.pos.distance_squared_to(b["pos"]))
                            self.click(game, hedgie.point(berry["pos"]))
                game.tick(1 / 60)
                self.assert_food_conserved(game)
                if game.delivered > previous_delivered:
                    deliveries += 1
                    previous_delivered = game.delivered
                if frame % 45 == 0:
                    game.draw()
            else:
                self.fail("The tap-to-walk play-through could not finish stage %s" % stage)
            self.assertEqual(game.state, "win" if stage == 2 else "reward")
            self.assertEqual(game.total_delivered, (6, 14, 24)[stage])
            game.draw()
            if stage < 2:
                self.start(game)
                previous_delivered = 0
                self.assertEqual(game.capacity, stage + 4)
        self.assertEqual(deliveries, 6)
        self.assertTrue(self.store.data["started"])

    def test_tap_walks_after_release_and_drag_changes_target(self):
        game = self.game
        self.click(game, (500, 460))
        initial = game.pos.copy()
        game.tick(0.1)
        self.assertGreater(game.pos.distance_to(initial), 10)
        self.assertEqual(game.target, pygame.Vector2(500, 460))
        game.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(500, 460), button=1))
        game.handle_event(pygame.event.Event(pygame.MOUSEMOTION, pos=(350, 360)))
        self.assertEqual(game.target, pygame.Vector2(350, 360))

    def test_hud_and_modal_clicks_do_not_steer(self):
        game = self.game
        original = game.target.copy()
        self.click(game, (200, 50))
        self.assertEqual(game.target, original)
        game.pause()
        self.click(game, (100, 300))
        game.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RIGHT))
        self.assertFalse(game.held)
        self.start(game)
        self.advance(game, 0.5)
        self.assertEqual(game.pos, original)

    def test_frame_rate_independent_travel_and_diagonal_speed(self):
        distances = []
        for fps in (15, 30, 60, 120):
            game = hedgie.HedgieGame(self.screen, storage=MemoryStore())
            self.start(game)
            game.pos.update(100, 470)
            game.target.update(500, 470)
            self.advance(game, 1, fps)
            distances.append(game.pos.x - 100)
        self.assertTrue(all(abs(d - 188) < 0.01 for d in distances), distances)
        game = self.game
        game.pos.update(100, 350)
        game.target = game.pos.copy()
        for key in (pygame.K_UP, pygame.K_RIGHT):
            game.handle_event(pygame.event.Event(pygame.KEYDOWN, key=key))
        initial = game.pos.copy()
        self.advance(game, 0.5)
        self.assertAlmostEqual(game.pos.distance_to(initial), 94, places=5)

    def test_releasing_keyboard_stops_without_a_backward_step(self):
        game = self.game
        game.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_LEFT))
        self.advance(game, 0.2)
        game.handle_event(pygame.event.Event(pygame.KEYUP, key=pygame.K_LEFT))
        position = game.pos.copy()
        self.advance(game, 0.2)
        self.assertEqual(game.pos, position)

    def test_touch_uses_scaled_coordinates_and_ignores_duplicate_mouse(self):
        screen = pygame.display.set_mode((1200, 600))
        game = hedgie.HedgieGame(screen, storage=MemoryStore())
        game.welcome = False
        game.handle_event(pygame.event.Event(pygame.FINGERDOWN, finger_id=11, x=600/1200, y=350/600))
        self.assertEqual(game.target, pygame.Vector2(400, 350))
        game.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(300, 220), button=1, touch=True))
        self.assertEqual(game.target, pygame.Vector2(400, 350))
        game.handle_event(pygame.event.Event(pygame.FINGERDOWN, finger_id=12, x=0.3, y=0.4))
        self.assertEqual(game.pointer, 11)
        game.handle_event(pygame.event.Event(pygame.FINGERMOTION, finger_id=11, x=0.6, y=0.7))
        self.assertEqual(game.target, pygame.Vector2(520, 420))
        game.handle_event(pygame.event.Event(pygame.FINGERUP, finger_id=11, x=0.6, y=0.7))
        self.assertIsNone(game.pointer)
        game.draw()
        self.assertIsNone(game.logical_position((10, 300)))

    def test_pause_and_focus_loss_freeze_gameplay_and_clear_input(self):
        game = self.game
        game.lantern_time = 7
        game.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_LEFT))
        game.handle_event(pygame.event.Event(pygame.WINDOWFOCUSLOST))
        pos = game.pos.copy()
        self.advance(game, 2)
        self.assertEqual(game.state, "pause")
        self.assertEqual(game.lantern_time, 7)
        self.assertEqual(game.pos, pos)
        self.assertFalse(game.held)
        self.assertIsNone(game.pointer)

    def test_neighbour_keeps_food_and_home_is_safe(self):
        game = self.game
        game.stage_index = 1
        game._build_stage()
        game.carrying = 1
        game.berries[0]["active"] = False
        game.pos = game.neighbour.copy()
        game.target = game.pos.copy()
        game.tick(1 / 60)
        self.assertEqual(game.carrying, 1)
        self.assertGreater(game.invulnerable, 0)
        self.advance(game, 1)
        self.assertEqual(game.carrying, 1)
        self.assertLess(game.neighbour.distance_to(pygame.Vector2(285, 442)), 40)
        game.pos.update(650, 300)
        game.neighbour = game.pos.copy()
        game.invulnerable = 0
        game._move_neighbour(1 / 60)
        self.assertEqual(game.invulnerable, 0)

    def test_lantern_expires_without_changing_base_rules(self):
        game = self.game
        game.stage_index = 1
        game._build_stage()
        game.pos = game.lantern.copy()
        game.target = game.pos.copy()
        game.tick(1 / 60)
        self.assertTrue(game.lantern_collected)
        self.assertGreater(game.lantern_time, 13)
        self.advance(game, 15)
        self.assertEqual(game.lantern_time, 0)
        self.assert_food_conserved(game)

    def test_save_resume_carried_food_and_partial_stage(self):
        game = self.game
        game.pos = game.berries[0]["pos"].copy()
        game.target = game.pos.copy()
        game.tick(1 / 60)
        game.persist()
        resumed = hedgie.HedgieGame(self.screen, storage=self.store)
        self.assertEqual(resumed.carrying, 1)
        self.assertEqual(resumed.pos, game.pos)
        self.assertTrue(resumed.welcome)
        self.assertTrue(resumed.has_played)
        self.assert_food_conserved(resumed)

    def test_save_during_delivery_cannot_lose_or_duplicate_food(self):
        game = self.game
        for berry in game.berries[:3]:
            game.pos = berry["pos"].copy()
            game.target = game.pos.copy()
            game.tick(1 / 60)
        game.pos.update(650, 300)
        game.target = game.pos.copy()
        game.tick(1 / 60)
        self.assertGreater(game.delivery_time, 0)
        resumed = hedgie.HedgieGame(self.screen, storage=self.store)
        self.start(resumed)
        self.advance(resumed, 2)
        self.assertEqual(resumed.delivered, 3)
        self.assertEqual(resumed.carrying, 0)

    def test_completed_save_opens_its_reward_and_replay_starts_cleanly(self):
        game = self.game
        game.stage_index = 2
        game._build_stage()
        game.delivered = game.stage["goal"]
        for berry in game.berries:
            berry["active"] = False
        game._finish_stage()
        resumed = hedgie.HedgieGame(self.screen, storage=self.store)
        self.assertEqual(resumed.state, "win")
        self.assertFalse(resumed.welcome)
        self.start(resumed)
        self.assertEqual((resumed.stage_index, resumed.carrying, resumed.delivered), (0, 0, 0))
        self.assertEqual(resumed.state, "play")
        self.assert_food_conserved(resumed)

    def test_corrupt_or_out_of_range_save_cannot_break_progression(self):
        for data in (None, [], {"schema": 9}, {"schema": 2, "stage": "bad"},
                     {"schema": 2, "stage": 80, "delivered": -2, "carrying": 500,
                      "remaining": ["bad"], "pos": [float("nan"), 6]}):
            game = hedgie.HedgieGame(self.screen, storage=MemoryStore(data))
            self.assert_food_conserved(game)
            game.draw()

    def test_real_desktop_store_roundtrip_and_invalid_json(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            store = hedgie.ProgressStore()
            store.path = Path(directory) / "save.json"
            self.assertTrue(store.save({"example": 7}))
            self.assertEqual(store.load(), {"example": 7})
            store.path.write_text("{broken", encoding="utf-8")
            self.assertEqual(store.load(), {})

    def test_browser_store_roundtrip_and_denied_storage(self):
        class LocalStorage:
            def __init__(self): self.items = {}
            def getItem(self, key): return self.items.get(key)
            def setItem(self, key, value): self.items[key] = value
        local = LocalStorage()
        browser = types.SimpleNamespace(window=types.SimpleNamespace(localStorage=local))
        with patch.object(sys, "platform", "emscripten"), patch.dict(sys.modules, {"platform": browser}):
            store = hedgie.ProgressStore()
            self.assertTrue(store.save({"schema": 2, "stage": 1}))
            self.assertEqual(store.load()["stage"], 1)
            with patch.object(local, "getItem", side_effect=RuntimeError("SecurityError")), \
                 patch.object(local, "setItem", side_effect=RuntimeError("QuotaExceeded")):
                self.assertEqual(store.load(), {})
                self.assertFalse(store.save({"example": 2}))

    def test_all_screen_states_render_without_assets_and_at_other_sizes(self):
        game = self.game
        for size in ((800, 600), (1024, 768), (1280, 720), (600, 900), (400, 300)):
            game.screen = pygame.display.set_mode(size)
            for state in ("play", "pause", "reward", "win"):
                game.state = state
                game.draw()
            game.welcome = True
            game.draw()
            game.welcome = False

    def test_existing_asset_names_load_when_present(self):
        original = Path.cwd()
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            assets = Path(directory).resolve() / "assets" / "hungryHedgie"
            assets.mkdir(parents=True)
            for name in ("hedgie", "enemy", "tree", "burrow", "berry", "torch", "grass"):
                image = pygame.Surface((50, 50), pygame.SRCALPHA)
                image.fill((150, 180, 100, 255))
                pygame.image.save(image, str(assets / (name + ".png")))
            try:
                os.chdir(assets.parent.parent)
                game = hedgie.HedgieGame(self.screen, storage=MemoryStore())
                self.assertEqual(len(game.art.loaded), 7)
                game.draw()
            finally:
                os.chdir(original)

    def test_gamehub_entry_point_returns_without_quitting_pygame(self):
        with patch.object(hedgie, "ProgressStore", return_value=MemoryStore()):
            pygame.event.post(pygame.event.Event(pygame.QUIT))
            asyncio.run(hedgie.main(self.screen, pygame.time.Clock()))
            self.assertFalse(hedgie.RUNNING)
            self.assertTrue(pygame.display.get_init())
            hedgie.setup(self.screen, pygame.time.Clock())
            self.assertTrue(hedgie.RUNNING)
            hedgie.ret()
            self.assertFalse(hedgie.RUNNING)


if __name__ == "__main__":
    unittest.main(verbosity=2)
