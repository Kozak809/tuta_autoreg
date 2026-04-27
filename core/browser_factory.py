import random
import re
from playwright.sync_api import sync_playwright
from core.mouse_engine import HumanCursor

def get_random_ua():
    is_ubuntu = random.choice([True, False])
    os_str = "X11; Ubuntu; Linux x86_64" if is_ubuntu else "X11; Linux x86_64"
    ua = f"Mozilla/5.0 ({os_str}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36"
    return ua, "Linux x86_64"

def get_browser_config(headless=True, port=None):
    launch_args = [
        "--disable-blink-features=AutomationControlled",
        "--no-sandbox",
        "--disable-infobars",
        "--disable-dev-shm-usage",
        "--disable-gpu",
        "--disable-extensions",
        "--disable-component-extensions-with-background-pages",
        "--disable-default-apps",
        "--mute-audio",
        "--no-default-browser-check",
        "--autoplay-policy=user-gesture-required",
        "--disable-background-timer-throttling",
        "--disable-backgrounding-occluded-windows",
        "--disable-notifications",
        "--disable-background-networking",
        "--disable-breakpad",
        "--disable-client-side-phishing-detection",
        "--disable-sync",
        "--metrics-recording-only",
    ]
    
    config = {
        "headless": headless,
        "channel": "chrome",
        "args": launch_args
    }
    
    if port:
        config["proxy"] = {"server": f"socks5://127.0.0.1:{port}"}
        
    return config

def get_context_config(proxy_info=None):
    screens = [
        (1920, 1080), (1366, 768), (1536, 864), 
        (1440, 900), (1600, 900), (1280, 720)
    ]
    vw, vh = random.choice(screens)
    ua, platform = get_random_ua()
    
    chrome_version_match = re.search(r"Chrome/(\d+\.\d+\.\d+\.\d+)", ua)
    chrome_version = chrome_version_match.group(1) if chrome_version_match else "122.0.0.0"
    
    dsf = 1.25 if vw > 1600 else 1.0
    
    if not proxy_info:
        proxy_info = {"timezone": "UTC", "locale": "en-US"}

    fake_brand, fake_v = random.choice([('"Not_A Brand"', '8'), ('"Not A(Brand"', '24'), ('"Not(A:Brand"', '99')])
    sec_ch_ua = f'"Chromium";v="{chrome_version.split(".")[0]}", {fake_brand};v="{fake_v}", "Google Chrome";v="{chrome_version.split(".")[0]}"'

    context_args = {
        "viewport": {"width": vw, "height": vh - random.randint(100, 140)},
        "screen": {"width": vw, "height": vh},
        "user_agent": ua,
        "locale": proxy_info['locale'],
        "timezone_id": proxy_info['timezone'],
        "device_scale_factor": dsf,
        "has_touch": False,
        "permissions": [],
        "extra_http_headers": {
            "sec-ch-ua": sec_ch_ua,
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": f'"{ "Windows" if "Win" in platform else "macOS" if "Mac" in platform else "Linux" }"'
        }
    }
    
    gpu_list = [
        ('Intel Open Source Technology Center', 'Mesa DRI Intel(R) HD Graphics 520 (Skylake GT2)'),
        ('Intel Open Source Technology Center', 'Mesa DRI Intel(R) HD Graphics 620 (Kaby Lake GT2)'),
        ('Intel', 'Mesa Intel(R) UHD Graphics 630 (Coffeelake 3x8 GT2)'),
        ('Intel', 'Mesa Intel(R) UHD Graphics (ADL-S GT1)'),
        ('Intel', 'Mesa Intel(R) Arc(TM) A770 Graphics (DG2)'),
        ('AMD', 'AMD Radeon RX 5700 XT (NAVI10, DRM 3.40.0, 5.11.0-49-generic, LLVM 12.0.0)'),
        ('AMD', 'AMD Radeon RX 6600 XT (DIMGREY_CAVE, DRM 3.42.0, 5.15.0-76-generic, LLVM 12.0.0)'),
        ('AMD', 'AMD Radeon RX 6700 XT (NAVY_FLOUNDER, DRM 3.42.0, 5.15.0-76-generic, LLVM 12.0.0)'),
        ('AMD', 'AMD Radeon RX 6800 (SIENNA_CICHLID, DRM 3.42.0, 5.15.0-76-generic, LLVM 12.0.0)'),
        ('AMD', 'AMD Radeon Graphics (RENOIR, DRM 3.40.0, 5.11.0-49-generic, LLVM 12.0.0)'),
        ('NVIDIA Corporation', 'NVIDIA GeForce GTX 1060/PCIe/SSE2'),
        ('NVIDIA Corporation', 'NVIDIA GeForce GTX 1660 SUPER/PCIe/SSE2'),
        ('NVIDIA Corporation', 'NVIDIA GeForce RTX 2060/PCIe/SSE2'),
        ('NVIDIA Corporation', 'NVIDIA GeForce RTX 3060/PCIe/SSE2'),
        ('NVIDIA Corporation', 'NVIDIA GeForce RTX 3070/PCIe/SSE2'),
        ('NVIDIA Corporation', 'NVIDIA GeForce RTX 3080/PCIe/SSE2'),
        ('NVIDIA Corporation', 'NVIDIA GeForce RTX 4070/PCIe/SSE2'),
        ('NVIDIA Corporation', 'NVIDIA GeForce RTX 4090/PCIe/SSE2')
    ]

    return context_args, {
        "cores": random.choice([4, 8, 12, 16]),
        "memory": random.choice([8, 16, 32]),
        "platform": platform,
        "gpu": random.choice(gpu_list)
    }

def get_stealth_script(hardware_info):
    cores = hardware_info["cores"]
    memory = hardware_info["memory"]
    platform = hardware_info["platform"]
    gpu_vendor, gpu_renderer = hardware_info["gpu"]
    
    return f"""
    try {{
        // 1. Продвинутая подмена toString
        const originalToString = Function.prototype.toString;
        Function.prototype.toString = function() {{
            if (this.__isStealthProxy) {{
                return `function ${{this.name || ''}}() {{ [native code] }}`;
            }}
            return originalToString.apply(this, arguments);
        }};

        function createStealthProxy(target, handler) {{
            const proxy = new Proxy(target, handler);
            proxy.__isStealthProxy = true;
            return proxy;
        }}

        // 2. Базовое железо
        Object.defineProperty(navigator, 'hardwareConcurrency', {{ get: () => {cores} }});
        Object.defineProperty(navigator, 'deviceMemory', {{ get: () => {memory} }});
        Object.defineProperty(navigator, 'platform', {{ get: () => '{platform}' }});

        // 3. Подмена Шрифтов (защищенная)
        const fonts = { "['Segoe UI', 'Tahoma', 'Verdana']" if "Linux" in platform else "['Helvetica Neue', 'Helvetica']" };
        document.fonts.check = createStealthProxy(document.fonts.check, {{
            apply: (target, thisArg, args) => {{
                try {{
                    if (args[0] && typeof args[0] === 'string' && fonts.some(f => args[0].includes(f))) {{
                        return true;
                    }}
                }} catch (e) {{}}
                return Reflect.apply(target, thisArg, args);
            }}
        }});

        // 4. Безопасный шум Canvas
        HTMLCanvasElement.prototype.toDataURL = createStealthProxy(HTMLCanvasElement.prototype.toDataURL, {{
            apply: (target, thisArg, args) => {{
                const ctx = thisArg.getContext('2d');
                if (ctx && thisArg.width > 0 && thisArg.height > 0) {{
                    ctx.fillStyle = `rgba(${{Math.floor(Math.random() * 255)}}, ${{Math.floor(Math.random() * 255)}}, ${{Math.floor(Math.random() * 255)}}, 0.01)`;
                    ctx.fillRect(0, 0, 1, 1);
                }}
                return Reflect.apply(target, thisArg, args);
            }}
        }});

        // 5. Безопасный WebGL (WebGL 1 и 2)
        WebGLRenderingContext.prototype.getParameter = createStealthProxy(WebGLRenderingContext.prototype.getParameter, {{
            apply: (target, thisArg, args) => {{
                if (args[0] === 37445) return '{gpu_vendor}';
                if (args[0] === 37446) return '{gpu_renderer}';
                return Reflect.apply(target, thisArg, args);
            }}
        }});
        WebGL2RenderingContext.prototype.getParameter = createStealthProxy(WebGL2RenderingContext.prototype.getParameter, {{
            apply: (target, thisArg, args) => {{
                if (args[0] === 37445) return '{gpu_vendor}';
                if (args[0] === 37446) return '{gpu_renderer}';
                return Reflect.apply(target, thisArg, args);
            }}
        }});
    }} catch(e) {{}}
    """

def init_page(context, show_cursor=False):
    page = context.new_page()
    cursor = HumanCursor(page, show=show_cursor)
    return page, cursor
