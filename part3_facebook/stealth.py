"""
Facebook Automation — Stealth & Anti-Detection Module
=====================================================

Applies browser patches to minimize automation detection signals.
Used for legitimate testing with the operator's own Facebook account
as part of a job assessment for Amazing Properties Wisconsin LLC.

These techniques demonstrate knowledge of browser fingerprinting
and detection evasion — core skills for web automation roles.
"""

import random
from typing import Any


# ---------------------------------------------------------------------------
# Realistic User-Agent Pool (Chrome on Windows/Mac, 2025-2026 builds)
# ---------------------------------------------------------------------------
USER_AGENTS: list[str] = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]

# ---------------------------------------------------------------------------
# Realistic viewport dimensions (common screen resolutions)
# ---------------------------------------------------------------------------
VIEWPORTS: list[dict[str, int]] = [
    {"width": 1920, "height": 1080},
    {"width": 1366, "height": 768},
    {"width": 1536, "height": 864},
    {"width": 1440, "height": 900},
    {"width": 1680, "height": 1050},
    {"width": 2560, "height": 1440},
    {"width": 1280, "height": 720},
    {"width": 1600, "height": 900},
]


def get_random_user_agent() -> str:
    """Return a random realistic Chrome User-Agent string."""
    return random.choice(USER_AGENTS)


def get_random_viewport() -> dict[str, int]:
    """Return a random realistic viewport dimension."""
    return random.choice(VIEWPORTS)


async def apply_stealth(page: Any) -> None:
    """
    Apply stealth patches to a Playwright page to reduce automation signals.

    Each patch addresses a specific detection vector that platforms use to
    identify headless/automated browsers. Comments explain the rationale.

    Args:
        page: A Playwright Page object.
    """

    # -----------------------------------------------------------------------
    # 1. Remove navigator.webdriver flag
    #    Automation frameworks set navigator.webdriver = true by default.
    #    Real browsers never have this flag set to true.
    # -----------------------------------------------------------------------
    await page.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined,
        });
    """)

    # -----------------------------------------------------------------------
    # 2. Override navigator.plugins
    #    Headless Chrome reports an empty plugins array.
    #    Real Chrome always has at least these core plugins.
    # -----------------------------------------------------------------------
    await page.add_init_script("""
        Object.defineProperty(navigator, 'plugins', {
            get: () => {
                const plugins = [
                    {
                        name: 'Chrome PDF Plugin',
                        description: 'Portable Document Format',
                        filename: 'internal-pdf-viewer',
                        length: 1,
                    },
                    {
                        name: 'Chrome PDF Viewer',
                        description: '',
                        filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai',
                        length: 1,
                    },
                    {
                        name: 'Native Client',
                        description: '',
                        filename: 'internal-nacl-plugin',
                        length: 2,
                    },
                ];
                // Make it behave like a real PluginArray
                plugins.refresh = () => {};
                plugins.item = (i) => plugins[i] || null;
                plugins.namedItem = (name) => plugins.find(p => p.name === name) || null;
                return plugins;
            },
        });
    """)

    # -----------------------------------------------------------------------
    # 3. Override navigator.languages
    #    Headless mode may return an empty or inconsistent languages array.
    #    Setting it to a common US English config looks natural.
    # -----------------------------------------------------------------------
    await page.add_init_script("""
        Object.defineProperty(navigator, 'languages', {
            get: () => ['en-US', 'en'],
        });
    """)

    # -----------------------------------------------------------------------
    # 4. Override navigator.hardwareConcurrency
    #    Headless environments sometimes report 1 or 2 cores.
    #    Real machines typically have 4-16 cores.
    # -----------------------------------------------------------------------
    core_count = random.choice([4, 6, 8, 12, 16])
    await page.add_init_script(f"""
        Object.defineProperty(navigator, 'hardwareConcurrency', {{
            get: () => {core_count},
        }});
    """)

    # -----------------------------------------------------------------------
    # 5. Override navigator.deviceMemory
    #    Low memory values can signal a VM or headless environment.
    #    Real machines report 4-16 GB typically.
    # -----------------------------------------------------------------------
    memory_gb = random.choice([4, 8, 16])
    await page.add_init_script(f"""
        Object.defineProperty(navigator, 'deviceMemory', {{
            get: () => {memory_gb},
        }});
    """)

    # -----------------------------------------------------------------------
    # 6. Patch chrome.runtime
    #    Real Chrome browsers expose the chrome.runtime object.
    #    Automation environments often lack this or expose inconsistencies.
    # -----------------------------------------------------------------------
    await page.add_init_script("""
        window.chrome = window.chrome || {};
        window.chrome.runtime = window.chrome.runtime || {
            onConnect: undefined,
            onMessage: undefined,
            connect: function() {},
            sendMessage: function() {},
        };
    """)

    # -----------------------------------------------------------------------
    # 7. Override Permissions API
    #    Headless Chrome may return 'denied' for notification permissions.
    #    Real browsers return 'default' or 'prompt' before user interaction.
    # -----------------------------------------------------------------------
    await page.add_init_script("""
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) => {
            if (parameters.name === 'notifications') {
                return Promise.resolve({ state: Notification.permission });
            }
            return originalQuery(parameters);
        };
    """)

    # -----------------------------------------------------------------------
    # 8. Mask WebGL renderer/vendor
    #    Detection scripts check WebGL for "SwiftShader" (headless GPU).
    #    We override to report a realistic NVIDIA/Intel GPU.
    # -----------------------------------------------------------------------
    gpu_configs = [
        ("NVIDIA Corporation", "NVIDIA GeForce RTX 3060/PCIe/SSE2"),
        ("NVIDIA Corporation", "NVIDIA GeForce GTX 1660 Ti/PCIe/SSE2"),
        ("Intel Inc.", "Intel(R) UHD Graphics 630"),
        ("Intel Inc.", "Intel(R) Iris(R) Xe Graphics"),
        ("ATI Technologies Inc.", "AMD Radeon RX 580"),
    ]
    vendor, renderer = random.choice(gpu_configs)

    await page.add_init_script(f"""
        const getParameter = WebGLRenderingContext.prototype.getParameter;
        WebGLRenderingContext.prototype.getParameter = function(parameter) {{
            // UNMASKED_VENDOR_WEBGL
            if (parameter === 37445) return '{vendor}';
            // UNMASKED_RENDERER_WEBGL
            if (parameter === 37446) return '{renderer}';
            return getParameter.call(this, parameter);
        }};

        // Also patch WebGL2 context
        if (typeof WebGL2RenderingContext !== 'undefined') {{
            const getParameter2 = WebGL2RenderingContext.prototype.getParameter;
            WebGL2RenderingContext.prototype.getParameter = function(parameter) {{
                if (parameter === 37445) return '{vendor}';
                if (parameter === 37446) return '{renderer}';
                return getParameter2.call(this, parameter);
            }};
        }}
    """)

    # -----------------------------------------------------------------------
    # 9. Prevent canvas fingerprint detection
    #    Some detection scripts draw to a canvas and hash the result.
    #    We add subtle noise to make each session look unique but natural.
    # -----------------------------------------------------------------------
    await page.add_init_script("""
        const originalToDataURL = HTMLCanvasElement.prototype.toDataURL;
        HTMLCanvasElement.prototype.toDataURL = function(type) {
            if (type === 'image/png' || type === undefined) {
                const context = this.getContext('2d');
                if (context) {
                    const imageData = context.getImageData(0, 0, this.width, this.height);
                    // Add subtle noise to a few random pixels
                    for (let i = 0; i < 10; i++) {
                        const idx = Math.floor(Math.random() * imageData.data.length);
                        imageData.data[idx] = imageData.data[idx] ^ 1;
                    }
                    context.putImageData(imageData, 0, 0);
                }
            }
            return originalToDataURL.apply(this, arguments);
        };
    """)

    # -----------------------------------------------------------------------
    # 10. Override connection info
    #     Bots on servers often have unusual connection types.
    #     Setting to '4g' / 'wifi' looks like a normal user.
    # -----------------------------------------------------------------------
    await page.add_init_script("""
        Object.defineProperty(navigator, 'connection', {
            get: () => ({
                effectiveType: '4g',
                rtt: 50,
                downlink: 10,
                saveData: false,
            }),
        });
    """)
