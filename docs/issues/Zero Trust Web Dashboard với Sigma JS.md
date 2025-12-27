Research API and data for dashboard

Read [](file:///home/zero-trust-netwoking/control-plane/api/v1)

Read [](file:///home/zero-trust-netwoking/control-plane/database/models.py#1-1), lines 1 to 200

Read [](file:///home/zero-trust-netwoking/web-ui)

Searched for files matching `**/.env*`, 2 matches

Read [](file:///home/zero-trust-netwoking/control-plane/database/models.py#200-200), lines 200 to 450

Read [](file:///home/zero-trust-netwoking/control-plane/api/v1/admin.py#1-1), lines 1 to 200

Read [](file:///home/zero-trust-netwoking/control-plane/api/v1/agent.py#1-1), lines 1 to 200

Read [](file:///home/zero-trust-netwoking/control-plane/api/v1/client.py#1-1), lines 1 to 200

Read [](file:///home/zero-trust-netwoking/control-plane/database/models.py#450-450), lines 450 to 692

Read [](file:///home/zero-trust-netwoking/control-plane/api/v1/admin.py#200-200), lines 200 to 400

Read [](file:///home/zero-trust-netwoking/control-plane/api/v1/endpoints.py)

Read [](file:///home/zero-trust-netwoking/control-plane/api/v1/user_policy.py#1-1), lines 1 to 200

Read [](file:///home/zero-trust-netwoking/control-plane/api/v1/websocket.py#1-1), lines 1 to 200

Read [](file:///home/zero-trust-netwoking/control-plane/api/v1/admin.py#400-400), lines 400 to 848

Read [](file:///home/zero-trust-netwoking/control-plane/api/v1/user_policy.py#200-200), lines 200 to 486

Read [](file:///home/zero-trust-netwoking/.env.example)

Read [](file:///home/zero-trust-netwoking/web-ui/index.html)

Read [](file:///home/zero-trust-netwoking/control-plane/config.py#1-1), lines 1 to 100

Read [](file:///home/zero-trust-netwoking/web-ui/public)

Read [](file:///home/zero-trust-netwoking/control-plane/api/v1/websocket.py#200-200), lines 200 to 337

Read [](file:///home/zero-trust-netwoking/control-plane/main.py#1-1), lines 1 to 100

Read [](file:///home/zero-trust-netwoking/control-plane/main.py#100-100), lines 100 to 262

Read [](file:///home/zero-trust-netwoking/control-plane/schemas/node.py#1-1), lines 1 to 200

Read [](file:///home/zero-trust-netwoking/control-plane/schemas/node.py#200-200), lines 200 to 342

Read [](file:///home/zero-trust-netwoking/control-plane/schemas/user_policy.py#1-1), lines 1 to 150

Searched for regex `trust_score|TrustHistory` (`**/control-plane/core/**`), 20 results

Read [](file:///home/zero-trust-netwoking/control-plane/core/domain_events.py#1-1), lines 1 to 100

Read [](file:///home/zero-trust-netwoking/control-plane/schemas/user_policy.py#150-150), lines 150 to 256

## Plan: Zero Trust Web Dashboard với Sigma.js

Thiết kế một dashboard React/TypeScript sử dụng Sigma.js để hiển thị network topology với real-time updates qua WebSocket.

### TL;DR
Dashboard React + Vite + TypeScript với graph visualization (Sigma.js) hiển thị nodes, clients, policies trong Zero Trust Network. Real-time updates qua WebSocket, responsive với TailwindCSS.

### Steps

1. **Initialize project structure** tại web-ui
   - `npm create vite@latest` với React + TypeScript template
   - Install dependencies: `@react-sigma/core`, `graphology`, `tailwindcss`, `axios`, `react-router-dom`, `@tanstack/react-query`

2. **Setup Tailwind và project config**
   - Configure tailwind.config.js, postcss.config.js
   - Setup API client với `X-Admin-Token` authentication
   - Environment config cho `VITE_API_URL`, `VITE_WS_URL`

3. **Create core components**
   - NetworkGraph.tsx - Sigma.js graph container
   - GraphControls.tsx - Zoom, filter, layout controls
   - NodeDetails.tsx - Sidebar panel khi click node
   - MetricsCards.tsx - Dashboard KPI cards

4. **Implement pages/routes**
   - DashboardPage.tsx - Main graph view + metrics
   - NodesPage.tsx - Table list với actions
   - ClientsPage.tsx - VPN clients management
   - PoliciesPage.tsx - Access policies CRUD

5. **WebSocket integration cho real-time**
   - useWebSocket.ts hook for live updates
   - Auto-reconnect, event handlers for `NodeRegistered`, `TrustScoreChanged`, etc.

6. **Build và deploy configuration**
   - Dockerfile cho production build
   - Caddy/nginx reverse proxy config
   - CORS đã sẵn sàng với `["http://localhost:3000"]`

### Further Considerations

1. **Graph Layout Algorithm?** ForceAtlas2 (dynamic) vs Fixed layout (manual positions) - Recommend ForceAtlas2 for auto-clustering by role
2. **Authentication method?** Hiện tại dùng `X-Admin-Token` hardcoded - Cần thêm login page với session/JWT cho production?
3. **Mobile responsive?** Sigma.js touch support tốt, nhưng có cần mobile-first design hay desktop-only admin dashboard?

Bạn muốn tôi implement plan này không?