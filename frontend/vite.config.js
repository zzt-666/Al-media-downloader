import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

function normalizeSiteUrl(raw) {
  const value = (raw || 'https://example.com').trim()
  return value.replace(/\/+$/, '') || 'https://example.com'
}

function buildRobotsTxt(siteUrl) {
  return [`User-agent: *`, `Allow: /`, ``, `Sitemap: ${siteUrl}/sitemap.xml`, ``].join(
    '\n',
  )
}

function buildSitemapXml(siteUrl) {
  const lastmod = new Date().toISOString().slice(0, 10)
  return [
    `<?xml version="1.0" encoding="UTF-8"?>`,
    `<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">`,
    `  <url>`,
    `    <loc>${siteUrl}/</loc>`,
    `    <lastmod>${lastmod}</lastmod>`,
    `    <changefreq>weekly</changefreq>`,
    `    <priority>1.0</priority>`,
    `  </url>`,
    `</urlset>`,
    ``,
  ].join('\n')
}

function buildLlmsTxt(siteUrl, siteName) {
  return [
    `# ${siteName}`,
    `> 面向学习与个人备份的在线视频下载与 AI 总结工具。`,
    ``,
    `产品主页: ${siteUrl}/`,
    `品牌: ${siteName}`,
    ``,
    `## 能力`,
    `- 粘贴公开视频链接，解析元数据与多清晰度选项并免费下载到本地`,
    `- AI 总结：普通用户体验 3 次，VIP 无限次；可导出 Markdown / 思维导图`,
    ``,
    `## 限制`,
    `- 仅供学习与个人备份；禁止未授权商用与传播`,
    `- 不引导绕过 DRM、破解会员或盗取账号`,
    `- 视频下载免费；AI 总结免费 3 次，VIP 无限`,
    `- 引擎能力以 yt-dlp 为准`,
    ``,
    `## 技术`,
    `- 前端 Web 单页；解析与下载委托 yt-dlp`,
    `- 规范链接: ${siteUrl}/`,
    ``,
  ].join('\n')
}

/**
 * Ensure SEO placeholders resolve even when .env is missing,
 * and emit robots.txt / sitemap.xml / llms.txt from VITE_SITE_URL.
 */
function seoPublicFilesPlugin({ siteUrl, siteName }) {
  const robots = buildRobotsTxt(siteUrl)
  const sitemap = buildSitemapXml(siteUrl)
  const llms = buildLlmsTxt(siteUrl, siteName)

  return {
    name: 'seo-public-files',
    transformIndexHtml(html) {
      return html
        .replaceAll('%VITE_SITE_URL%', siteUrl)
        .replaceAll('%VITE_SITE_NAME%', siteName)
    },
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        const url = req.url?.split('?')[0]
        if (url === '/robots.txt') {
          res.setHeader('Content-Type', 'text/plain; charset=utf-8')
          res.end(robots)
          return
        }
        if (url === '/sitemap.xml') {
          res.setHeader('Content-Type', 'application/xml; charset=utf-8')
          res.end(sitemap)
          return
        }
        if (url === '/llms.txt') {
          res.setHeader('Content-Type', 'text/plain; charset=utf-8')
          res.end(llms)
          return
        }
        next()
      })
    },
    writeBundle(outputOptions) {
      const outDir = outputOptions.dir || path.resolve(__dirname, 'dist')
      fs.mkdirSync(outDir, { recursive: true })
      fs.writeFileSync(path.join(outDir, 'robots.txt'), robots, 'utf8')
      fs.writeFileSync(path.join(outDir, 'sitemap.xml'), sitemap, 'utf8')
      fs.writeFileSync(path.join(outDir, 'llms.txt'), llms, 'utf8')
    },
  }
}

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, __dirname, 'VITE_')
  const siteUrl = normalizeSiteUrl(env.VITE_SITE_URL)
  const siteName = (env.VITE_SITE_NAME || 'Linkora').trim() || 'Linkora'

  return {
    plugins: [vue(), tailwindcss(), seoPublicFilesPlugin({ siteUrl, siteName })],
    server: {
      proxy: {
        // Keep /api prefix — FastAPI routes are mounted under /api
        '/api': {
          target: 'http://127.0.0.1:8000',
          changeOrigin: true,
          // Keep SSE / long summarize streams from buffering or timing out
          timeout: 0,
          proxyTimeout: 0,
        },
      },
    },
  }
})
