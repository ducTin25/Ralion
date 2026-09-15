import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";

const withNextIntl = createNextIntlPlugin("./src/i18n/request.ts");

/**
 * Backend thật mà Next proxy tới. Chỉ đọc ở phía server (không có tiền tố
 * `NEXT_PUBLIC_`) nên URL này không bị nhúng vào bundle trình duyệt.
 */
const API_UPSTREAM_URL = process.env.API_UPSTREAM_URL ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  experimental: {
    // Repository scan uploads are filtered client-side and capped at 100 MiB by FastAPI.
    // Keep the same-origin Next proxy above that limit (multipart adds a small envelope),
    // otherwise Next returns 500 before the request ever reaches the backend.
    proxyClientMaxBodySize: "110mb",
    // Policy ingestion performs chunking and embedding before returning. Next's rewrite
    // proxy otherwise closes the upstream socket after its 30-second default timeout.
    proxyTimeout: 300_000,
  },
  /**
   * Đưa API về cùng origin với trang web.
   *
   * Cookie phiên do FastAPI cấp là `SameSite=Lax` + host-only. Khi frontend ở
   * `*.vercel.app` mà API ở domain khác thì mọi lời gọi `fetch` là cross-site:
   * trình duyệt bỏ luôn `Set-Cookie`, đăng nhập trả 200 nhưng không có phiên. Kể cả
   * khi nới thành `SameSite=None`, cookie vẫn thuộc host của API nên `proxy.ts`
   * — nó đọc cookie trên host của Next — không bao giờ thấy và sẽ đá về `/login`.
   *
   * Proxy qua chính domain Next làm cookie trở thành first-party: `SameSite=Lax` giữ
   * nguyên, middleware đọc được, và trình duyệt không cần CORS. Local dev cũng đi
   * cùng một đường nên hành vi cookie giống hệt staging.
   */
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${API_UPSTREAM_URL}/api/:path*`,
      },
    ];
  },
};

export default withNextIntl(nextConfig);
