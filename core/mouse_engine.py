"""
Simulates human-like mouse movements and scrolling.

Uses Bezier curves and coherent noise to create realistic cursor trajectories
and scrolling behaviors, helping to bypass basic bot detection systems.
"""
import time
import random
import numpy as np
from scipy.special import comb

class HumanCursor:
    def __init__(self, page, show=False):
        self.page = page
        self.show = show
        self.cur_x, self.cur_y = random.randint(50, 500), random.randint(50, 500)
        if self.show:
            self._setup_visual_cursor()

    def _setup_visual_cursor(self):
        script = """
        function ensureCursor() {
            if (!document.getElementById('human-cursor-dot')) {
                const cursor = document.createElement('div');
                cursor.id = 'human-cursor-dot';
                cursor.style.position = 'fixed';
                cursor.style.width = '14px';
                cursor.style.height = '14px';
                cursor.style.backgroundColor = 'red';
                cursor.style.border = '2px solid white';
                cursor.style.borderRadius = '50%';
                cursor.style.zIndex = '9999999';
                cursor.style.pointerEvents = 'none';
                cursor.style.top = '0';
                cursor.style.left = '0';
                cursor.style.boxShadow = '0 0 5px rgba(0,0,0,0.5)';
                document.documentElement.appendChild(cursor);
            }
        }
        window.updateCursor = (x, y) => {
            ensureCursor();
            const cursor = document.getElementById('human-cursor-dot');
            if (cursor) cursor.style.transform = `translate(${x}px, ${y}px)`;
        };
        new MutationObserver(ensureCursor).observe(document.documentElement, {childList: true, subtree: true});
        ensureCursor();
        """
        self.page.add_init_script(script)

    def _bernstein_poly(self, i, n, t):
        return comb(n, i) * (t**i) * (1 - t)**(n - i)

    def _generate_bezier_path(self, x1, y1, x2, y2):
        dist = np.hypot(x2 - x1, y2 - y1)
        # Меньше точек = выше скорость. 1 точка на каждые 15-20 пикселей.
        n_points = max(10, int(dist / 20))
        
        # Почти прямая линия
        offset_scale = min(15, dist * 0.05)
        knots = np.array([
            [x1, y1],
            [x1 + (x2 - x1) * 0.5 + random.uniform(-offset_scale, offset_scale), 
             y1 + (y2 - y1) * 0.5 + random.uniform(-offset_scale, offset_scale)],
            [x2, y2]
        ])
        
        n = len(knots) - 1
        t = np.linspace(0, 1, n_points)
        path = np.zeros((n_points, 2))
        for i in range(len(knots)):
            path += np.outer(self._bernstein_poly(i, n, t), knots[i])
            
        # Легкий когерентный шум
        seed = random.uniform(0, 50)
        noise_amp = 0.8
        for i in range(n_points):
            ti = i / n_points * np.pi * 2
            path[i][0] += np.sin(ti * 2 + seed) * noise_amp
            path[i][1] += np.cos(ti * 1.5 + seed) * noise_amp
            
        return path

    def smooth_scroll_to(self, locator):
        try:
            # Используем нативный метод Playwright для надежного скролла в зону видимости
            locator.scroll_into_view_if_needed()
            time.sleep(random.uniform(0.1, 0.3))
        except:
            pass

    def move_to(self, locator):
        self.smooth_scroll_to(locator)
        box = locator.bounding_box()
        if not box:
            time.sleep(0.1)
            box = locator.bounding_box()
            if not box: return False
        
        target_x = box['x'] + box['width'] * random.uniform(0.45, 0.55)
        target_y = box['y'] + box['height'] * random.uniform(0.45, 0.55)
        
        path = self._generate_bezier_path(self.cur_x, self.cur_y, target_x, target_y)
        
        # Основной цикл движения БЕЗ задержек
        for i, (x, y) in enumerate(path):
            # Шанс на микро-задумчивость в середине длинного пути
            if len(path) > 40 and i == len(path) // 2 and random.random() < 0.15:
                time.sleep(random.uniform(0.1, 0.4))

            self.page.mouse.move(x, y)
            # Обновляем красную точку только на каждой 5-й позиции, чтобы не тормозить
            if self.show and i % 5 == 0:
                try: self.page.evaluate(f"window.updateCursor({x}, {y})")
                except: pass
            
            # Рандомное микро-торможение
            if random.random() < 0.01:
                time.sleep(random.uniform(0.005, 0.015))
        
        # Финальное позиционирование
        self.page.mouse.move(target_x, target_y)
        if self.show:
            try: self.page.evaluate(f"window.updateCursor({target_x}, {target_y})")
            except: pass
            
        self.cur_x, self.cur_y = target_x, target_y
        return True

    def click(self, locator):
        if self.move_to(locator):
            # Мгновенный человеческий клик
            self.page.mouse.down()
            time.sleep(random.uniform(0.01, 0.03))
            self.page.mouse.up()
            time.sleep(0.05)
            return True
        return False
