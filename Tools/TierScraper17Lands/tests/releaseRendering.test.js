/** @jest-environment jsdom */
const fs = require('fs');
const path = require('path');

const source = fs.readFileSync(path.join(__dirname, '../../../server/templates/app.js'), 'utf8');
let render;
let start;

beforeEach(() => {
    document.body.innerHTML = '<div id="releases-list"></div>';
    const listener = jest.spyOn(document, 'addEventListener').mockImplementation((name, callback) => {
        if (name === 'DOMContentLoaded') start = callback;
    });
    render = new Function('document', 'fetch', source + '\nreturn {formatMarkdown, renderAssets};')(document, (...args) => global.fetch(...args));
    listener.mockRestore();
});

function expectSafe(container) {
    expect(container.querySelector('script, img, svg, iframe, object')).toBeNull();
    for (const node of container.querySelectorAll('*')) {
        for (const attr of node.attributes) expect(attr.name).not.toMatch(/^on/i);
    }
    for (const link of container.querySelectorAll('a')) {
        expect(link.getAttribute('href')).toMatch(/^(https?:\/\/|#)/);
    }
}

test.each([
    '<img src=x onerror="alert(1)">',
    '<svg onload=alert(1)><script>alert(1)</script></svg>',
    '[link](javascript:alert%281%29)',
    '[link](data:text/html,evil)',
    '[link](java\tscript:evil)',
    '[link](javascript&#58;evil)',
    '[link](https://example.com/" onmouseover="evil)',
    '[`nested`](javascript:evil)',
])('release Markdown rejects executable content: %s', input => {
    const container = document.createElement('div');
    container.innerHTML = render.formatMarkdown(input);
    expectSafe(container);
});

test('ordinary Markdown and HTTPS links still render', () => {
    const container = document.createElement('div');
    container.innerHTML = render.formatMarkdown('## Changes\n**Fixed** *cards* `code`\n- [Details](https://example.com/?a=1&b=2)');
    expect(container.querySelector('h2').textContent).toBe('Changes');
    expect(container.querySelector('strong').textContent).toBe('Fixed');
    expect(container.querySelector('code').textContent).toBe('code');
    const link = container.querySelector('a');
    expect(link.href).toBe('https://example.com/?a=1&b=2');
    expect(link.rel).toBe('noopener noreferrer');
});

test('release fields and asset attributes are escaped in the actual page', async () => {
    const release = {
        name: '<img src=x onerror=evil>', tag_name: '<svg onload=evil>',
        published_at: '2026-10-06', html_url: 'javascript:evil',
        body: '<img src=x onerror=evil>',
        assets: [{name: '\" onmouseover=evil><img src=x>.exe', browser_download_url: 'javascript:evil', size: 1024}],
    };
    global.fetch = jest.fn().mockResolvedValue({json: async () => [release, release]});
    start();
    // Flush the fetch and JSON promise chain.
    for (let i = 0; i < 5; i++) await Promise.resolve();
    const container = document.getElementById('releases-list');
    expect(container.querySelectorAll('a').length).toBeGreaterThan(0);
    expect(container.textContent).toContain(release.name);
    expectSafe(container);
    delete global.fetch;
});
