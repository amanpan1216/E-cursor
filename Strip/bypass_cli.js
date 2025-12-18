#!/usr/bin/env node

/**
 * CLI Wrapper for bypass.js to work with bbb.py
 * Usage: node bypass_cli.js <url> [method] [headers_json] [body]
 */

const https = require('https');
const http = require('http');
const { URL } = require('url');
const crypto = require('crypto');
const zlib = require('zlib');

// Import bypass.js logic (simplified version for CLI use)
const USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Safari/605.1.15'
];

function randomUA() {
    return USER_AGENTS[Math.floor(Math.random() * USER_AGENTS.length)];
}

function randomBase64(length) {
    return Buffer.from(crypto.randomBytes(Math.ceil(length * 3/4)))
        .toString('base64')
        .replace(/=/g, '')
        .slice(0, length);
}

function randomHex(length) {
    return crypto.randomBytes(Math.ceil(length/2))
        .toString('hex')
        .slice(0, length);
}

function generateAdvancedCookies(hostname) {
    const timestamp = Date.now();
    const cookies = {
        cf_clearance: randomBase64(43) + '.' + randomHex(8) + '-' + Math.floor(timestamp/1000) + '-' + randomHex(8),
        __cf_bm: randomBase64(43) + '=',
        _cfuvid: randomHex(32) + '.' + Math.floor(timestamp/1000),
        ak_bmsc: randomBase64(88),
        _abck: randomBase64(144) + '~0~' + randomBase64(64) + '~0~-1',
        bm_mi: randomHex(32) + '~' + randomHex(16),
        bm_sv: randomBase64(100) + '~' + randomHex(8) + '~' + Date.now(),
        sessionid: randomHex(32),
        csrftoken: randomBase64(64)
    };

    return Object.entries(cookies)
        .map(([k, v]) => `${k}=${v}`)
        .join('; ');
}

function makeRequest(url, method = 'GET', extraHeaders = {}, body = null) {
    return new Promise((resolve, reject) => {
        const parsedUrl = new URL(url);
        const isHttps = parsedUrl.protocol === 'https:';
        
        const headers = {
            'User-Agent': randomUA(),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
            'Sec-Ch-Ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"Windows"',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Upgrade-Insecure-Requests': '1',
            'Cookie': generateAdvancedCookies(parsedUrl.hostname),
            ...extraHeaders
        };

        if (method === 'POST' && body) {
            headers['Content-Type'] = extraHeaders['Content-Type'] || 'application/x-www-form-urlencoded';
            headers['Content-Length'] = Buffer.byteLength(body);
        }

        const options = {
            hostname: parsedUrl.hostname,
            port: isHttps ? 443 : 80,
            path: parsedUrl.pathname + parsedUrl.search,
            method: method,
            headers: headers,
            rejectUnauthorized: false
        };

        if (isHttps) {
            options.ciphers = 'TLS_AES_128_GCM_SHA256:TLS_AES_256_GCM_SHA384:TLS_CHACHA20_POLY1305_SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-RSA-AES256-GCM-SHA384';
            options.minVersion = 'TLSv1.2';
            options.maxVersion = 'TLSv1.3';
            options.ecdhCurve = 'x25519:secp256r1:secp384r1';
        }

        const client = isHttps ? https : http;
        const req = client.request(options, (res) => {
            const chunks = [];

            res.on('data', (chunk) => {
                chunks.push(chunk);
            });

            res.on('end', () => {
                let buffer = Buffer.concat(chunks);
                let data = '';
                
                // Handle gzip/deflate/br compression
                const encoding = res.headers['content-encoding'];
                try {
                    if (encoding === 'gzip') {
                        data = zlib.gunzipSync(buffer).toString('utf-8');
                    } else if (encoding === 'deflate') {
                        data = zlib.inflateSync(buffer).toString('utf-8');
                    } else if (encoding === 'br') {
                        data = zlib.brotliDecompressSync(buffer).toString('utf-8');
                    } else {
                        data = buffer.toString('utf-8');
                    }
                } catch (e) {
                    // If decompression fails, try as plain text
                    data = buffer.toString('utf-8');
                }
                
                const cookies = res.headers['set-cookie'] || [];
                resolve({
                    status: res.statusCode,
                    headers: res.headers,
                    body: data,
                    cookies: cookies
                });
            });
        });

        req.on('error', (err) => {
            reject({
                error: err.message,
                status: 0,
                body: '',
                headers: {},
                cookies: []
            });
        });

        req.setTimeout(30000, () => {
            req.destroy();
            reject({
                error: 'Request timeout',
                status: 0,
                body: '',
                headers: {},
                cookies: []
            });
        });

        if (method === 'POST' && body) {
            req.write(body);
        }

        req.end();
    });
}

// CLI interface
async function main() {
    const args = process.argv.slice(2);
    
    if (args.length === 0) {
        let stdinData = '';
        process.stdin.setEncoding('utf-8');
        
        for await (const chunk of process.stdin) {
            stdinData += chunk;
        }
        
        if (stdinData.trim()) {
            try {
                const requestData = JSON.parse(stdinData);
                const url = requestData.url;
                const method = requestData.method || 'GET';
                const extraHeaders = requestData.headers || {};
                const body = requestData.body || null;
                
                const result = await makeRequest(url, method, extraHeaders, body);
                console.log(JSON.stringify(result));
                return;
            } catch (err) {
                console.error(JSON.stringify({
                    error: err.message,
                    status: 0
                }));
                process.exit(1);
            }
        }
        
        console.error(JSON.stringify({
            error: 'Usage: node bypass_cli.js <url> [method] [headers_json] [body] OR pipe JSON to stdin',
            status: 0
        }));
        process.exit(1);
    }

    const url = args[0];
    const method = args[1] || 'GET';
    const headersJson = args[2] || '{}';
    const body = args[3] || null;

    let extraHeaders = {};
    try {
        extraHeaders = JSON.parse(headersJson);
    } catch (e) {
        // Ignore invalid JSON
    }

    try {
        const result = await makeRequest(url, method, extraHeaders, body);
        console.log(JSON.stringify(result));
    } catch (err) {
        console.error(JSON.stringify(err));
        process.exit(1);
    }
}

if (require.main === module) {
    main();
}

module.exports = { makeRequest, generateAdvancedCookies, randomUA };
